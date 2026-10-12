# Claude Code workflow rules

This repository implements a resumable, model-driven Event Planner workflow. The `/plan-event` command is the coordinator and orchestration hub. It plans, dynamically selects and schedules subagents, validates their outputs, records durable state, and controls human approval; it does not write event recommendations itself.

## Rules of execution

1. **Clarify first.** Save the original input, ask one batched set of questions for missing critical requirements, and confirm the captured brief with the user. Do not plan around unresolved critical values. Distinguish constraints from preferences and assumptions.
2. **Plan dynamically.** Select only necessary agents from `.claude/agents/`. Record chosen/skipped agents, dependencies, attempts, artifacts, and statuses in the run's `workflow-state.json`. Group A research can run in parallel; Group B depends on relevant Group A outputs; Group C depends on Groups A and B. Never schedule a dependent agent before its inputs pass structural/citation checks.
3. **Use external sources.** Use `event-research.search_web` for current recommendations, providers, and public facts; use `event-research.get_weather_forecast` for outdoor dates within its forecast horizon. Search only the minimum event location/service context; never send guest names, contact details, or other attendee personal data to external sources. A run cannot claim current research if MCP is unavailable. Stop with a setup blocker instead of silently relying on model memory or inventing facts.
4. **Respect artifact ownership.** Each agent writes only its declared artifact. All artifacts use the structure and checks in `.claude/skills/artifact-validator/SKILL.md`. The validator reports gates and remediation; it does not edit domain artifacts. Synthesis reads only validated inputs. The HTML builder returns the rendered guide to the coordinator; the coordinator writes the final HTML in the same Claude session that received the user's approval, so the hook can verify the transcript.
5. **Gate and retry narrowly.** Validate artifacts before dependent work and run cross-artifact gates before synthesis. On failure, identify owner and downstream dependency closure, retry only failed owners and invalidate/rebuild only affected descendants. Maximum three retries per affected agent after the initial attempt. Re-run gates after correction. Exhausted failures stop dependent work; report gate, evidence, attempts, owner, and blocked stages.
6. **Persist continuously.** Create the run directory and `workflow-state.json` before work; update state after every stage/attempt/approval transition. The PostToolUse hook records written artifact hashes and timestamps. On resume, compare artifact hashes, preserve valid completed work, and schedule only pending/failed/invalidated work. Never treat a missing state/artifact as completed.
7. **Require exact approval.** After a passing gate, synthesize `artifacts/daily-plan.md`, compute SHA-256 over its exact bytes, and present it for review. Only the human's exact `APPROVE <64 lowercase hex SHA-256>` response approves that specific draft. `REVISE: ...` invalidates approval and requires targeted revision, validation, a new hash, and a new approval. Silence, vague agreement, and earlier approvals do not count. Persist `approval.status`, `approved_plan_sha256`, exact `confirmation`, `approved_at`, and `revision` in state. Before permitting final HTML, the approval PreToolUse hook recomputes the current plan hash and requires the exact confirmation in a direct user message in the current Claude session transcript. Therefore, the coordinator—not the HTML-builder subagent—must perform the final HTML write in the session that received approval.
8. **Keep output clean.** Final output is a standalone accessible `event-plan.html`. The no-leak hook blocks internal artifact names and run paths in user-facing HTML. Never include credentials or private attendee data in examples or user-facing output.

## Run layout and state

Live run directories are `runs/<slug>-<timestamp>/` (git-ignored). Store `input.md`, agent artifacts under `artifacts/`, the final `event-plan.html`, and `workflow-state.json` there. The coordinator initializes state with this shape and may add fields while retaining these keys:

```json
{
  "schema_version": 1,
  "run_id": "community-fundraiser-20270515",
  "status": "requirements",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "retry_limit": 3,
  "attempts": {},
  "agents": {},
  "dependencies": {},
  "artifact_paths": {
    "requirements": "artifacts/requirements.md",
    "daily_plan": "artifacts/daily-plan.md"
  },
  "written_artifacts": {},
  "approval": {
    "status": "not_requested",
    "approved_plan_sha256": null,
    "confirmation": null,
    "approved_at": null,
    "revision": 0
  },
  "final_output": "event-plan.html",
  "history": []
}
```

`agents` statuses are `pending`, `in_progress`, `completed`, `failed`, `blocked`, or `skipped`. `attempts` counts retries by agent (initial execution is attempt 1; allow at most 4 total attempts). `written_artifacts` is keyed by run-relative path with `sha256` and `updated_at`; the PostToolUse hook maintains it. State and output paths are run-local and relative. When a requirement changes, invalidate the precise downstream dependency closure, not unrelated completed work.

## Quality gates

The validator must explicitly report pass/fail with evidence for: total costs including taxes/fees/contingency at or below the confirmed cap; schedule has no overlaps and meaningful activities plus transitions; no duplicate recommendations; venue capacity, date constraints, location, and accessibility fit; transport and requested services/preferences match; dietary/allergy and accessibility needs are addressed; external recommendations link to real direct source pages; all artifacts agree on date/time zone, headcount, currency, and costs. Unknown costs, unverified availability, or vendor safety claims remain visible. A passing validator result is not human approval.

## Hooks and MCP

`.claude/settings.json` registers two PreToolUse guards for Write/Edit and a PostToolUse state updater. Approval must be checked before any HTML under `runs/` is written; the approval hook also checks the session transcript for a direct user message containing the exact current-plan confirmation. User-facing HTML must not reveal internal paths/artifact filenames. Hooks fail closed for missing, invalid, or unverifiable approval on a final output. `.mcp.json` registers the version-controlled custom `event-research` MCP server in `mcp/event-research/`; it exposes live Brave Search and Open-Meteo tools. The Brave key is supplied only through `BRAVE_API_KEY` in the environment.

Use `/plan-event <request>` for a new run and `/plan-event --resume runs/<run-id>` to recover. Follow `README.md` for prerequisites, setup, run examples, and checks. The `examples/runs/` directory contains illustrative tracked fixtures; never treat them as live state or verified vendor quotes.
