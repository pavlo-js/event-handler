import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "examples" / "runs"
RUNS = ("01-community-fundraiser", "02-budget-retry", "03-resume-approval")
REQUIRED_SECTIONS = (
    "## Status", "## Inputs", "## Findings", "## Recommendations", "## Costs", "## Sources", "## Open questions and assumptions"
)


class ExampleRunTests(unittest.TestCase):
    def test_each_example_has_input_state_and_structured_artifacts(self):
        for run_id in RUNS:
            with self.subTest(run=run_id):
                run = ROOT / run_id
                self.assertTrue((run / "input.md").is_file())
                state = json.loads((run / "workflow-state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["run_id"], run_id)
                artifacts = list((run / "artifacts").glob("*.md"))
                self.assertGreaterEqual(len(artifacts), 3)
                for artifact in artifacts:
                    text = artifact.read_text(encoding="utf-8")
                    for section in REQUIRED_SECTIONS:
                        self.assertIn(section, text, f"{artifact} missing {section}")

    def test_approved_examples_match_current_plan_and_output(self):
        for run_id in ("01-community-fundraiser", "03-resume-approval"):
            with self.subTest(run=run_id):
                run = ROOT / run_id
                state = json.loads((run / "workflow-state.json").read_text(encoding="utf-8"))
                plan = run / state["artifact_paths"]["daily_plan"]
                digest = hashlib.sha256(plan.read_bytes()).hexdigest()
                self.assertEqual(state["approval"]["status"], "approved")
                self.assertEqual(state["approval"]["approved_plan_sha256"], digest)
                self.assertEqual(state["approval"]["confirmation"], f"APPROVE {digest}")
                self.assertTrue((run / state["final_output"]).is_file())

    def test_mcp_server_command_uses_its_project_directory(self):
        config = json.loads((ROOT.parents[1] / ".mcp.json").read_text(encoding="utf-8"))
        args = config["mcpServers"]["event-research"]["args"]
        directory_index = args.index("--directory")
        self.assertEqual(args[directory_index + 1], "mcp/event-research")
        self.assertEqual(args[directory_index + 2], "server.py")

    def test_retry_and_resume_scenarios_are_recorded(self):
        retry = json.loads((ROOT / RUNS[1] / "workflow-state.json").read_text(encoding="utf-8"))
        self.assertEqual(retry["status"], "awaiting_approval")
        self.assertEqual(retry["attempts"]["venue-planner"], 2)
        self.assertTrue(any(item.get("result") == "FAIL" for item in retry["history"]))
        resumed = json.loads((ROOT / RUNS[2] / "workflow-state.json").read_text(encoding="utf-8"))
        self.assertTrue(any(item.get("event") == "interruption" for item in resumed["history"]))
        self.assertTrue(any(item.get("result") == "REVISE" for item in resumed["history"]))


if __name__ == "__main__":
    unittest.main()
