# Task: <task-id>
- id: <task-id>
- question: <user's original question, one sentence>
- superseded_by:

<!-- The dispatcher fills the upper half from the user's words. The Lead fills the alignment record. After confirmation the card is frozen; later changes are appended to the alignment record with a reason. -->

## Question (user's words, verbatim)
<the user's message>

## Type
<free text, e.g. reproduction / tool test / option comparison / survey / audit / design / maintenance / construction>

## Pre-authorized
<yes / no. yes = the user told the Lead to proceed with defaults; the Lead skips the confirmation round and writes the frozen version directly>

## User decisions
- <scope, targets, metrics and preferences the user stated; "none" if none>

## Open questions (the Lead turns these into assumptions with defaults, or questions)
- <key points the dispatcher noticed but the user did not state>

## Not doing
- <at most 3>

## Budget and resources
- Time and cost limits: <stated by the user, or "open: Lead confirms after the pilot">
- Hardware: see `~/.claude/local.md`. Network: <yes / no>. Lead role: <lead / lead_important>

## Existing evidence (grep INDEX.md; "none" if none)
- <card IDs or task IDs with line>

## Known pitfalls
- <traps, versions, data issues the user mentioned; "none" if none>

---

## Alignment record (Lead)

### Round 1 <date time>
<the confirmation as sent>

User reply: <verbatim>

### Frozen version
- Question:
- Primary metric (how computed):
- Comparison targets / baseline:
- Success and stop criteria ("does not match" and "blocked" are valid conclusions):
- Assumptions (confirmed): A1 … A2 …
- Authorized files and acceptance commands:
- Confirmed at: <time, or "pre-authorized">

## Execution
- Real runs go to `results.jsonl`; raw output stays at the recorded artifact paths.
- Delegated exploration writes `findings/<topic>-<executor>.md` with `file:line` or URL per claim.
- Long-lived notes (user decisions, pitfalls, conventions) go to `memory/`, one note per file, indexed in `memory/MEMORY.md`.

<!-- Conclusion: add "## Conclusion (YYYY-MM-DD)" with "- **Tendency**:" and "- **Confidence**:" lines when done (format in AGENTS.md, workflow step 5). -->
