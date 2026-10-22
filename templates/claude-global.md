# Shared agent conventions

Clarify material ambiguity once, execute the agreed work, and report evidence and limitations.
Machine facts live in `.agenthelm/config/local.md`; the role-to-model table lives in the generated `.agenthelm/config/models.md`. Both are included in the generated agent rules.
Never invent measurements, sources or successful checks.

## Orchestra: layered delegation

Rules name roles, never models. `bin/models` turns your local `.agenthelm/config/roles.toml` into `.agenthelm/config/models.md`, which maps each role to a model and the exact command that runs it. To change assignments, edit `roles.toml` and rerun `bin/models` (it regenerates `models.md` and runs `bin/kb sync-agents`); never edit the generated table.

| Role | Tier | Does | Does not |
|---|---|---|---|
| lead | Strategist | Alignment, design, acceptance, conclusions for one task | Bulk reading, long logs, mechanical edits |
| lead_important | Strategist | Same as lead, for tasks the user marks important | Routine tasks |
| visual | Strategist | Visual design and construction: pages, slides, motion, layout, colour | Research, copywriting, code review |
| writing | Strategist | Report prose, documentation, final editing of text for readers | Code, experiments |
| hard | Executor | Hard debugging, critical implementation, reproductions, pilots | Visual work, one-minute chores |
| fact | Executor | Default execution: exploration, reading code, verification, implementation to a spec, running experiments and tests, grading | Final sign-off on critical work (hand to hard or review) |
| review | Executor | Code review capability; workflow follows user rules | Fixing what it reviews |
| simplify | Executor | Simplification pass over a finished change | Changing behaviour or rendering |
| aesthetic | Executor | Aesthetic review of visual work | Construction |
| chore | Helper | Fixed, simple, mechanically checkable work: search, log extraction, template filling, small edits, status updates, cleanup | Design, grading, root-cause analysis, conclusions, skill-dependent work |

- The main session judges, designs and supervises. Anything writable as "scope + method + acceptance command" goes to the cheapest role that can do it; decide whether it needs judgement before doing it yourself.
- No cheap tier or second harness: map several roles to the same model family, strongest for Strategist roles and smallest for chore, and record it in `roles.toml`.

## Delegation

- Use the selected command in `.agenthelm/config/models.md`. A `default` candidate deliberately inherits that CLI's configured model. Set explicit models only in the project roles.toml when needed.
- Brief each delegate with scope, method, output path, acceptance command and a reply length limit. Read-only work says "do not modify files"; file-changing work runs the acceptance command and reports its output verbatim. When the work depends on a skill, tell the delegate to load it by name; cheap models rarely load skills unprompted.
- A delegate whose brief would be very long belongs one role up (chore → fact).
- Delegates cannot spawn delegates; the main session splits multi-step work and runs the steps in sequence.
- One-shot background runs: start the command itself as a background job; its completion notice means it is done. Write output to an agreed file and reply with one line (path + conclusion). When you must wait, poll the PID, not a process-name pattern that can match the waiting shell.
- Exploration and investigation are delegated, not done in the main session. Each delegate writes its findings to `findings/<topic>-<executor>.md` in the task directory, citing `file:line` or a URL for every claim. The main session reads only the summaries. When two findings conflict, send one more independent check against the cited lines and write it back to the same file.
- Read-only delegations have no fixed fan-out; a large survey may run many sub-agents in one session. Gate tests, builds and browsers by the memory measure in `local.md`.
- After delegating, read the acceptance output and spot-check the change. Do not redo the work.
- Stop and report after two failed acceptance runs or when a design trade-off appears.
- Keep artifacts that must survive a restart in the task directory; temporary files follow the storage tiers in `local.md`.

## Review

Follow the user's existing code-review routing and authorization. For Jack, Matt's code-review skill is the default; do not substitute or append a different review engine. A roles.toml entry maps capability, not authorization to run that CLI as a reviewer. Confirm findings against real files and actual check output. Report limitations when review cannot run under the current host constraints.

## Optional skills

Code-minimization skills such as ponytail are optional. Whether to load one is decided only by the list in the executor conventions; follow it and repeat the instruction in delegation prompts that write code.
