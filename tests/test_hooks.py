import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / "runs" / "demo"
        (self.run / "artifacts").mkdir(parents=True)
        self.plan = self.run / "artifacts" / "daily-plan.md"
        self.plan.write_text("# Event plan\nConfirmed draft\n", encoding="utf-8")
        self.state_path = self.run / "workflow-state.json"
        self.state = {
            "run_id": "demo",
            "artifact_paths": {"daily_plan": "artifacts/daily-plan.md"},
            "final_output": "event-plan.html",
            "approval": {
                "status": "not_requested",
                "approved_plan_sha256": None,
                "confirmation": None,
                "revision": 0,
            },
        }
        self.save_state()
        self.output = self.run / "event-plan.html"
        self.transcript_path = self.root / "transcript.jsonl"

    def write_transcript(self, role, content):
        entry = {
            "type": role,
            "message": {"role": role, "content": [{"type": "text", "text": content}]},
        }
        self.transcript_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def save_state(self):
        self.state_path.write_text(json.dumps(self.state), encoding="utf-8")

    def invoke(self, script, payload):
        return subprocess.run(
            [sys.executable, str(HOOKS / script)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=self.root,
            env=os.environ.copy(),
            check=False,
        )

    def approval_event(self):
        return {
            "tool_name": "Write",
            "transcript_path": str(self.transcript_path),
            "tool_input": {"file_path": str(self.output), "content": "<h1>Event</h1>"},
        }

    def test_final_html_is_blocked_without_explicit_approval(self):
        result = self.invoke("approval_gate.py", self.approval_event())
        self.assertEqual(result.returncode, 2)
        self.assertIn("explicit approval", result.stderr)

    def test_final_html_is_allowed_for_exact_current_plan_hash(self):
        digest = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        confirmation = f"APPROVE {digest}"
        self.state["approval"].update(
            status="approved",
            approved_plan_sha256=digest,
            confirmation=confirmation,
            approved_at="2026-10-09T12:00:00+00:00",
        )
        self.save_state()
        self.write_transcript("user", confirmation)
        result = self.invoke("approval_gate.py", self.approval_event())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_state_only_approval_is_blocked_without_user_transcript(self):
        digest = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        self.state["approval"].update(
            status="approved",
            approved_plan_sha256=digest,
            confirmation=f"APPROVE {digest}",
        )
        self.save_state()
        result = self.invoke("approval_gate.py", self.approval_event())
        self.assertEqual(result.returncode, 2)
        self.assertIn("transcript", result.stderr)

    def test_assistant_message_does_not_count_as_user_approval(self):
        digest = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        confirmation = f"APPROVE {digest}"
        self.state["approval"].update(
            status="approved",
            approved_plan_sha256=digest,
            confirmation=confirmation,
        )
        self.save_state()
        self.write_transcript("assistant", confirmation)
        result = self.invoke("approval_gate.py", self.approval_event())
        self.assertEqual(result.returncode, 2)
        self.assertIn("no exact user approval", result.stderr)

    def test_changed_draft_invalidates_previous_approval(self):
        digest = hashlib.sha256(self.plan.read_bytes()).hexdigest()
        self.state["approval"].update(
            status="approved", approved_plan_sha256=digest, confirmation=f"APPROVE {digest}"
        )
        self.save_state()
        self.plan.write_text("# Revised plan\n", encoding="utf-8")
        result = self.invoke("approval_gate.py", self.approval_event())
        self.assertEqual(result.returncode, 2)

    def test_no_leak_guard_blocks_internal_names_in_html(self):
        event = {"tool_name": "Write", "tool_input": {"file_path": str(self.output), "content": "See artifacts/daily-plan.md"}}
        result = self.invoke("no_leak_guard.py", event)
        self.assertEqual(result.returncode, 2)
        self.assertIn("internal artifact", result.stderr)

    def test_no_leak_guard_allows_clean_user_facing_html(self):
        event = {"tool_name": "Write", "tool_input": {"file_path": str(self.output), "content": "<h1>Community celebration</h1>"}}
        result = self.invoke("no_leak_guard.py", event)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_leak_guard_blocks_other_internal_artifact_names(self):
        event = {"tool_name": "Write", "tool_input": {"file_path": str(self.output), "content": "Details are in venue.md"}}
        result = self.invoke("no_leak_guard.py", event)
        self.assertEqual(result.returncode, 2)

    def test_post_write_hook_persists_artifact_hash(self):
        artifact = self.run / "artifacts" / "venue.md"
        artifact.write_text("# Venue\n", encoding="utf-8")
        event = {"tool_name": "Write", "tool_input": {"file_path": str(artifact), "content": "# Venue\n"}}
        result = self.invoke("post_write_state.py", event)
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(self.state_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.assertEqual(updated["written_artifacts"]["artifacts/venue.md"]["sha256"], digest)
        self.assertIn("updated_at", updated)

    def test_concurrent_post_write_hooks_preserve_all_artifact_hashes(self):
        events = []
        expected = {}
        for index in range(8):
            artifact = self.run / "artifacts" / f"artifact-{index}.md"
            content = f"# Artifact {index}\n"
            artifact.write_text(content, encoding="utf-8")
            expected[f"artifacts/artifact-{index}.md"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
            events.append({"tool_input": {"file_path": str(artifact)}})

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda event: self.invoke("post_write_state.py", event), events))

        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(self.state_path.read_text(encoding="utf-8"))
        actual = {key: entry["sha256"] for key, entry in updated["written_artifacts"].items()}
        self.assertEqual(actual, expected)

    def test_post_write_hook_ignores_files_outside_live_runs(self):
        outside = self.root / "notes.md"
        outside.write_text("note", encoding="utf-8")
        before = self.state_path.read_bytes()
        result = self.invoke("post_write_state.py", {"tool_input": {"file_path": str(outside)}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
