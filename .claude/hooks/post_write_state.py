"""Persist hashes and timestamps for written artifacts in active event runs."""

import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def state_lock(run_root: Path):
    lock_path = run_root / ".workflow-state.lock"
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            while True:
                lock_file.seek(0)
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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
    if len(relative.parts) < 3 or relative.parts[0].casefold() != "runs" or relative.name == "workflow-state.json":
        return 0

    run_root = root.joinpath(*relative.parts[:2])
    state_path = run_root / "workflow-state.json"
    try:
        with state_lock(run_root):
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict) or not target.is_file():
                return 0
            artifact_key = target.relative_to(run_root).as_posix()
            timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
            written_artifacts = state.setdefault("written_artifacts", {})
            if not isinstance(written_artifacts, dict):
                raise ValueError("written_artifacts must be an object")
            written_artifacts[artifact_key] = {
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "updated_at": timestamp,
            }
            state["updated_at"] = timestamp
            fd, temp_name = tempfile.mkstemp(prefix="workflow-state-", suffix=".tmp", dir=run_root)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temp_file:
                    json.dump(state, temp_file, indent=2, ensure_ascii=False)
                    temp_file.write("\n")
                os.replace(temp_name, state_path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Could not update workflow artifact state: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
