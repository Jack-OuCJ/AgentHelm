# Shared agent conventions

Clarify material ambiguity once, execute the agreed work, and report evidence and limitations.
Machine facts live in `~/.claude/local.md`; the role-to-model table lives in the generated `~/.config/research/models.md`. Both are included in the generated agent rules.
Never invent measurements, sources or successful checks.

## Orchestra: layered delegation

Rules name roles, never models. `bin/models` turns your local `~/.config/research/roles.toml` into `~/.config/research/models.md`, which maps each role to a model and the exact command that runs it. To change assignments, edit `roles.toml` and rerun `bin/models` (it regenerates `models.md` and runs `bin/kb sync-agents`); never edit the generated table.

| Role | Tier | Does | Does not |
|---|---|---|---|
| lead | Strategist | Alignment, design, acceptance, conclusions for one task | Bulk reading, long logs, mechanical edits |
| lead_important | Strategist | Same as lead, for tasks the user marks important | Routine tasks |
| visual | Strategist | Visual design and construction: pages, slides, motion, layout, colour | Research, copywriting, code review |
| writing | Strategist | Report prose, documentation, final editing of text for readers | Code, experiments |
| hard | Executor | Hard debugging, critical implementation, reproductions, pilots | Visual work, one-minute chores |
| fact | Executor | Default execution: exploration, reading code, verification, implementation to a spec, running experiments and tests, grading | Final sign-off on critical work (hand to hard or review) |
| review | Executor | Code review; run two different models in parallel | Fixing what it reviews |
| simplify | Executor | Simplification pass over a finished change | Changing behaviour or rendering |
| aesthetic | Executor | Aesthetic review of visual work | Construction |
| chore | Helper | Fixed, simple, mechanically checkable work: search, log extraction, template filling, small edits, status updates, cleanup | Design, grading, root-cause analysis, conclusions, skill-dependent work |

- The main session judges, designs and supervises. Anything writable as "scope + method + acceptance command" goes to the cheapest role that can do it; decide whether it needs judgement before doing it yourself.
- No cheap tier or second harness: map several roles to the same model family, strongest for Strategist roles and smallest for chore, and record it in `roles.toml`.

## Delegation

- Pass the model (and effort, where supported) explicitly on every delegation, using the command from `models.md`. A delegate that inherits the main session's model silently spends the strongest tier.
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

Applies per deliverable (one page, one report, one release).

1. After the builder's self-check, run one review round in parallel: two code reviewers on different models (review role); for visual work also aesthetic; and simplify. Give every reviewer the same explicit diff or file list; do not let it guess the change set. Large deliverables may be split by module, one review each.
2. Merge adopted findings into one fix list and hand it to the original builder to fix in one pass. Do not fix items one by one in the main session.
3. Second round reviews only the fix diff, code review only. A correctness issue it finds gets one small fix; no further rounds. More rounds than this go into Limitations, or ask the user first.
4. For simplify on visual or prose work, adopt only items that do not change the rendered result.
5. If no reviewer is available, self-review and say so.

Verification is the main session's job. Treat each finding as wrong until a real file or command confirms it.

- Correctness, security, missing requirements: fix when confirmed, with the smallest change. Redundancy: delete when confirmed removable.
- Hardening is not adopted by default. Adopt it only when its trigger occurs in real use and the fix adds no new test, hash, check, configuration or disclaimer (or the user asked for it).
- Do not decide by vote count. When a reviewer asks for a test or check, first ask whether the same error would recur without it.
- Report one merged result in three parts: adopted, not adopted (one reason each), for the user to decide.

## Optional skills

Code-minimization skills such as ponytail are optional. Whether to load one is decided only by the list in the executor conventions; follow it and repeat the instruction in delegation prompts that write code.
