# Executor conventions

## Handoff (applies when you are a delegated executor: a sub-agent, a background CLI run, a Codex task)

- Edit only the files named in the task or delegation prompt (appending to the install log is allowed); do not edit the task file itself.
- Do not edit generated indexes (`INDEX.md`, `EXPERIMENTS.md`), conclusion sections of task READMEs, or rule files (`AGENTS.md`, `rules-extra.md`, `rules/`); leave them to their owner.
- Write artifacts to the assigned paths. Reply with the artifact path and one sentence of findings, unless the prompt asks for another format (a review, for example, lists every finding).
- Run the agreed checks and report actual output. Stop after two failed attempts or when a design decision is needed.
- When you find a contradiction with an existing card or conclusion, add a line `conflict: <card or task id> <one sentence>` to your reply. Do not resolve it and do not edit the other file.

## Installing software

Applies to every session, on any platform.
- When a tool or dependency is missing, install it without asking, using the package manager and install location named in `local.md` (a user-level one if none is named). Agent skills and plugins follow their own rules below.
- Project dependencies still go into the project's virtual environment; they are removed with the project and need no log entry.
- For everything installed outside a project, append one line to the install log named in `local.md` (default `~/.config/research/installs.log`): date, install command, why (task), uninstall command.
- In your reply, list what you installed under a line starting with **Installed:**, with the uninstall command for each. A delegated executor puts this list in its reply; the main session passes it on to the user.
- Only operations that need an administrator password (sudo without passwordless access) are written as commands for the user to run.

## Research cards

A card starts with `# Title`, followed immediately by these lines, each as `- key: value`:
`id` (equals the kebab-case filename without extension), `topic`, `sources` (URL or `file:line`), `date`, `valid_for` (versions or conditions it holds for), `superseded_by` (empty until replaced).
Then the body, within 150 lines. Every factual claim cites a URL or `file:line`.

## Code-minimization skills (ponytail or similar; the only place this list lives)

Use such a skill only if installed; never install one just for a task.
- **Load it** before backend, script and logic work: construction, refactoring, bug fixes, and the simplification steps of a plan. When delegating such work, write "load <skill> before starting" into the prompt.
- **Do not load it** for exploration and research analysis, verification and review, plan or report prose, front-end and presentation work (pages, CSS, motion, HTML, slides) and their visual review, document rewriting, editing and uploading, or when you are the model under test. These favour quality; do not cut animation, hierarchy, colour or visual detail in the name of less code.
- In mixed tasks, apply it to the logic part only.

## Browser checks

Pick one browser automation tool per platform, run one browser at a time, and close it when done. The tool and its setup for this machine are named in `local.md`.

## Local data

Keep credentials and machine-specific facts out of shared rules; they belong in `~/.config/research/` and `~/.claude/local.md`.
