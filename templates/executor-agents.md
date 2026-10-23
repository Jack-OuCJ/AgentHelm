# Executor conventions

## Handoff (applies when you are a delegated executor: a sub-agent, a background CLI run, a Codex task)

- Edit only the files named in the task or delegation prompt (appending to the install log is allowed); do not edit the task file itself.
- Do not edit generated indexes (`INDEX.md`, `EXPERIMENTS.md`, `MEMORY.md`), conclusion sections of task READMEs, or rule files (`AGENTS.md`, `rules-extra.md`, `rules/`); leave them to their owner.
- Write artifacts to the assigned paths. Reply with the artifact path and one sentence of findings, unless the prompt asks for another format (a review, for example, lists every finding).
- Run the agreed checks and report actual output. Stop after two failed attempts or when a design decision is needed.
- When you find a contradiction with an existing card or conclusion, add a line `conflict: <card or task id> <one sentence>` to your reply. Do not resolve it and do not edit the other file.

## Installing software

Install project dependencies only in this workspace or the task virtual environment. Do not install user-wide tools, skills or plugins without explicit authorization. Follow the user's existing shared rules.

## Research and memory candidates

Keep investigation and evidence in the assigned task `findings/`; put finished reports, HTML and other reader deliverables in task `artifacts/`. Long-lived project documents belong in `docs/`; Matt tickets and ADRs retain `.scratch/<feature>/issues/` and `docs/adr/`.

When a reusable lesson or recovery constraint emerges, include a memory candidate in the findings with its scope, applicability and sources. The Lead decides whether to publish it using the working-memory protocol in `rules-extra.md`. Read only the relevant notes named in the delegation and check their sources. Do not create a second knowledge-card archive or edit generated `MEMORY.md` indexes.

## Code-minimization skills (ponytail or similar; the only place this list lives)

Use such a skill only if installed; never install one just for a task.
- **Load it** before backend, script and logic work: construction, refactoring, bug fixes, and the simplification steps of a plan. When delegating such work, write "load <skill> before starting" into the prompt.
- **Do not load it** for exploration and research analysis, verification and review, plan or report prose, front-end and presentation work (pages, CSS, motion, HTML, slides) and their visual review, document rewriting, editing and uploading, or when you are the model under test. These favour quality; do not cut animation, hierarchy, colour or visual detail in the name of less code.
- In mixed tasks, apply it to the logic part only.

## Browser checks

Pick one browser automation tool per platform, run one browser at a time, and close it when done. The tool and its setup for this machine are named in `local.md`.

## Local data

Keep credentials and machine-specific facts out of shared rules; they belong in `.agenthelm/config/` and `.agenthelm/config/local.md`.
