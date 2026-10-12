---
name: event-guide-theme
description: Render a reviewed and human-approved event plan as a clean, accessible, standalone HTML guide.
---

# Event guide theme

Use `template.html` in this skill directory as the visual/layout baseline. Create one standalone HTML file with embedded CSS only; no remote scripts, fonts, images, or tracking. Replace every template placeholder with content from the approved daily plan.

## Rules
- Render only the exact daily-plan revision whose SHA-256 hash appears in the workflow state's approved confirmation.
- Keep dates, local time zone, currency, estimates, caveats, sources, and open vendor-confirmation items intact.
- Use semantic landmarks, a single `h1`, ordered headings, readable contrast, responsive cards, and print-friendly styles.
- Keep source URLs as descriptive, keyboard-accessible links; escape all text and attribute content.
- Do not expose internal artifact names, state files, run IDs/paths, or coordinator notes.
- If approval or plan hash is missing/mismatched, stop. The pre-write approval hook also blocks the final file.
