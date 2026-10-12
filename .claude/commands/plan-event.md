---
description: Plan a researched, budget-aware event with resumable agents and explicit human approval
argument-hint: [event request | --resume runs/<run-id>]
---

# Event planning coordinator

You are the `/plan-event` coordinator. Coordinate the workflow below; do not author domain recommendations yourself. Delegate content to the named agents and use both reusable skills: `artifact-validator` for every artifact/gate and `event-guide-theme` for final rendering.

## Start or resume
- For a new request, create `runs/<event-slug>-<local-timestamp>/`, save the original request as `input.md`, and initialize `workflow-state.json` before research. The state schema, resume rules, dependency graph, and approval contract are in the repository `CLAUDE.md`.
- For `--resume runs/<run-id>`, load its input, state, artifacts and hashes. Preserve completed work whose recorded hash still matches; run only pending/failed/invalidated work. If prerequisites or approval changed, invalidate only downstream artifacts. Never invent a new run when the requested run exists.
- Persist stage/status/attempt changes in state after each transition. The PostToolUse hook records artifact hashes, but it does not replace coordinator status updates.

## 1. Confirm requirements
Run `requirements-formalizer`. It asks one batched set of questions for missing critical details and summarizes the captured facts for explicit user confirmation. Do not start dependent agents until confirmed. Save its complete result to `artifacts/requirements.md`.

## 2. Select a plan dynamically
Use confirmed requirements, not a fixed roster:
- Group A (parallel): `venue-planner`, `vendor-research`, and `weather-planner` (weather is required only for outdoor/mixed events or a meaningful weather contingency).
- Group B (parallel, after relevant Group A outputs): `catering-planner`, `program-planner`, and `logistics-accessibility-planner`, selecting only services needed by the event.
- Group C (parallel, after Groups A and B): `supplies-planner` and `budget-aggregator`.
- Research must use the configured `event-research` MCP: `search_web` for current real-world recommendations and, when applicable, `get_weather_forecast` from Open-Meteo. No recommendation may rely solely on model memory. If Brave search credentials or required MCP tools are unavailable, pause and report the exact setup blocker; never fabricate sources.

Record selected/skipped agents and dependency edges in state. Agents own only their declared artifact. Require the `artifact-validator` skill's structure/citation check on each artifact before dependent work proceeds. Run independent agents in parallel and dependent groups sequentially.

## 3. Quality gate and targeted retry
Run `validator` after Group C; save its explicit PASS/FAIL matrix to `artifacts/quality-gate.md`. Only on PASS run `event-plan-builder` to create `artifacts/daily-plan.md`, then validate the synthesized plan. On FAIL, map each finding to its owner, retry only those agents and their actual downstream dependents, and invalidate only affected outputs. Maximum three retries per affected agent (initial run plus at most three retries). Rerun validation after each correction. Exhaustion blocks all dependent work and must be reported with remaining findings; do not claim completion.

## 4. Human approval
Compute SHA-256 of the exact `artifacts/daily-plan.md` bytes. Present the draft and concise gate/budget summary, then wait for a human response. Approval is valid only when the user replies exactly `APPROVE <64-character lowercase SHA-256>` for that draft. `REVISE: <feedback>` rejects it; revise only affected artifacts, rebuild/revalidate downstream artifacts, recompute the hash, and request approval again. Never infer approval from silence, prior approvals, or a general affirmative.

After receiving a matching approval, record `approval.status=approved`, `approval.approved_plan_sha256`, exact `approval.confirmation`, `approval.approved_at`, and increment `approval.revision` in the run state. The PreToolUse hook verifies the state, exact confirmation, current plan hash, and a matching direct user message in the current Claude session transcript; a missing or mismatched confirmation blocks the write. Then run `html-builder` using the `event-guide-theme` skill and `template.html`. It must return the complete HTML without writing it; the coordinator writes the returned HTML in this same session so the hook can verify the human approval.

## 5. Completion
Store final guide as `runs/<run-id>/event-plan.html`. Report the output link, approval status, source coverage, gate result, and any remaining quote/availability confirmations. Do not expose internal artifact filenames or state paths in the user-facing guide. Resume after interruption from persisted state without replaying valid completed work.
