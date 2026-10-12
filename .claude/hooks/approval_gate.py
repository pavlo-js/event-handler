"""Block final guide writes unless the current draft has direct user approval."""

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Iterator


APPROVAL = re.compile(r"^APPROVE [0-9a-f]{64}$")


def user_message_texts(transcript_path: Path) -> Iterator[str]:
    with transcript_path.open(encoding="utf-8") as transcript:
        for line in transcript:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            message = entry.get("message")
            if isinstance(message, dict):
                role = message.get("role", entry.get("type"))
                content = message.get("content")
            else:
                role = entry.get("type")
                content = entry.get("content")
            if role != "user":
                continue
            if isinstance(content, str):
                yield content
            elif isinstance(content, list):
                text_parts = [
                    block["text"]
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") == "text"
                    and isinstance(block.get("text"), str)
                ]
                if text_parts:
                    yield "\n".join(text_parts)


def transcript_has_confirmation(transcript_path: Path, confirmation: str) -> bool:
    if not transcript_path.is_file():
        return False
    deadline = time.monotonic() + 2
    while True:
        if any(message.strip() == confirmation for message in user_message_texts(transcript_path)):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)


def block(message: str) -> int:
    print(f"Blocked: {message}", file=sys.stderr)
    return 2


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(event, dict):
        return 0
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    raw_path = tool_input.get("file_path") or tool_input.get("filePath")
    if not isinstance(raw_path, str) or not raw_path:
        return 0

    root = Path.cwd().resolve()
    target = Path(raw_path)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        relative = target.relative_to(root)
    except ValueError:
        return 0
    if len(relative.parts) < 3 or relative.parts[0].casefold() != "runs" or target.suffix.casefold() != ".html":
        return 0

    run_root = target.parent
    state_path = run_root / "workflow-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return block("final event guides require a valid workflow-state.json approval record.")
    if not isinstance(state, dict) or state.get("final_output") != "event-plan.html":
        return block("the run must declare event-plan.html as its final output.")

    try:
        if target != (run_root / "event-plan.html").resolve():
            return block("write only the declared final output after approval.")
        artifact_paths = state.get("artifact_paths")
        if not isinstance(artifact_paths, dict):
            raise ValueError("invalid artifact paths")
        daily_plan_path = artifact_paths.get("daily_plan")
        if not isinstance(daily_plan_path, str) or not daily_plan_path:
            raise ValueError("daily plan path must be a non-empty string")
        plan_relative = Path(daily_plan_path)
        if plan_relative.is_absolute():
            raise ValueError("daily plan path must be run-relative")
        plan_path = (run_root / plan_relative).resolve()
        plan_path.relative_to(run_root)
        plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    except (KeyError, OSError, ValueError):
        return block("the approved daily plan is missing, unreadable, or outside the run directory.")

    approval = state.get("approval")
    if not isinstance(approval, dict):
        return block("a valid approval record is required.")
    confirmation = approval.get("confirmation")
    if (
        approval.get("status") != "approved"
        or not isinstance(confirmation, str)
        or not APPROVAL.fullmatch(confirmation)
        or confirmation != f"APPROVE {plan_hash}"
        or approval.get("approved_plan_sha256") != plan_hash
    ):
        return block("explicit approval for the current daily-plan SHA-256 is required.")

    raw_transcript_path = event.get("transcript_path")
    if not isinstance(raw_transcript_path, str) or not raw_transcript_path:
        return block("the exact approval must be present in the current Claude session transcript.")
    transcript_path = Path(raw_transcript_path)
    if not transcript_path.is_absolute():
        transcript_path = root / transcript_path
    try:
        if not transcript_has_confirmation(transcript_path, confirmation):
            return block("the current Claude session transcript has no exact user approval for this draft.")
    except (OSError, UnicodeError):
        return block("the Claude session transcript is unavailable; approval cannot be verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
