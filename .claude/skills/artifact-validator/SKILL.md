---
name: artifact-validator
description: Apply the common artifact structure, citation checks, and event-planning quality gates to workflow artifacts.
---

# Artifact validator

Apply this skill whenever an agent creates or revises an artifact and before a dependent stage begins.

## Required structure
Each Markdown artifact must contain:

1. `# <Artifact title>` and the workflow run ID.
2. `## Status` — `complete`, `blocked`, or `needs-revision`.
3. `## Inputs` — confirmed requirement/artifact paths used.
4. `## Findings` — concise, sourced results or explicit `Not applicable`.
5. `## Recommendations` — ranked action(s), owners, and relevant estimates.
6. `## Costs` — amount, confirmed currency, estimate/quote status, and assumptions; use `Not applicable` if none.
7. `## Sources` — direct URLs with publisher/title and checked date; write `No external sources used` only for non-factual artifacts.
8. `## Open questions and assumptions` — unresolved decisions; use `None` when clear.

## Per-artifact checks
- All required sections are present and internally consistent.
- Factual recommendations and claims have working direct source links; don't cite search result pages as the only evidence.
- Prices are explicitly estimates or sourced quotes, use the confirmed currency, and state date/tax/fee caveats.
- User constraints are carried forward; unknowns remain visible rather than invented.
- Dependencies are complete and valid before downstream work starts.

## Cross-artifact event gates
Validator must report PASS/FAIL and evidence for each: budget including contingency within the confirmed limit; schedule has no overlaps, meaningful activity in each period, and setup/transition buffers; no duplicate recommendations; venue matches capacity/date/location/accessibility needs; transport and service preferences match; dietary and accessibility constraints are addressed; each external recommendation has a real source page; artifacts agree on headcount, time, currency, and costs. A failed gate blocks synthesis/output. Map each finding to the responsible agent and downstream artifacts that must be invalidated. Coordinator retries only that scope, at most three times.

## Output
Produce `artifacts/quality-gate.md` with an overall `PASS` or `FAIL`, one row per gate, evidence, affected artifact, owner, and downstream invalidation list. Do not fix upstream artifacts. A passing gate does not equal human approval.
