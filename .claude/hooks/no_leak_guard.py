"""Prevent internal workflow paths and artifact filenames from leaking into final HTML."""

import json
import re
import sys
from pathlib import Path


INTERNAL = re.compile(
    r"(?:\.claude[/\\]|workflow-state\.json|"
    r"(?:^|[\s'\"<>])artifacts[/\\][^\s'\"<>]*|"
    r"(?:^|[\s'\"<>])runs[/\\][^\s'\"<>]*|"
    r"\b(?:input|requirements|research-summary|quality-gate|daily-plan|venue|"
    r"vendor-research|weather|catering|program|logistics-accessibility|supplies|budget)\.md\b)",
    re.IGNORECASE,
)


def strings(value, key=""):
    if key.casefold() in {"file_path", "filepath", "path", "file"}:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child_key, child in value.items():
            yield from strings(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    tool_input = event.get("tool_input", {})
    raw_path = tool_input.get("file_path") or tool_input.get("filePath")
    if not raw_path:
        return 0
    target = Path(raw_path)
    if not target.is_absolute():
        target = Path.cwd() / target
    try:
        relative = target.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return 0
    if len(relative.parts) < 3 or relative.parts[0].casefold() != "runs" or target.suffix.casefold() != ".html":
        return 0
    body = "\n".join(strings(tool_input))
    if INTERNAL.search(body):
        print("Blocked: remove internal artifact filenames and workflow paths from the user-facing guide.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
