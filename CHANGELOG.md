# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## 0.2.1 - 2026-10-21

### Changed

- Executor conventions gain an "Installing software" section for every platform: install missing tools and dependencies without asking, keep project dependencies in the project's virtual environment, log every install outside a project (date, command, reason, uninstall command) to the install log, list installs under **Installed:** in the reply, and hand only operations that need an administrator password to the user.
- `templates/local.md.example`: "Administrator access" is replaced by package manager, install location, passwordless sudo and install log; global tools may be installed if logged.
- `research-setup` installs missing requirements with a user-level package manager and logs them instead of refusing.

## 0.2.0 - 2026-10-20

### Added

- Research workflow in `templates/research-AGENTS.md`: frozen alignment written to the task README; sizing before running (pilot of about 10 samples, N ≈ 8q/d² paired or 4/d² unpaired, counted in independent units, never shrinking the scenario under test); fairness checks before scaling; defaults for reproductions, tool tests and option comparisons; a floor of rules that hold in every mode.
- Lead alignment layout (at most 25 lines, at most two rounds), four allowed reasons to interrupt the user afterwards, and a pre-authorized branch that skips confirmation.
- Lead report layout (at most 6 lines) and a table of carriers and size limits between dispatcher, Lead, executors and the user.
- `templates/research-extra.md`, installed as `rules-extra.md`: strict mode, long runs (`failures.jsonl`, stop after 3 consecutive failures, resume), Lead context handover through task `memory/`, cleanup checklist, and fixed markers for `confirmed by`, `overturned by`, `conflict:` and withdrawn conclusions.
- Ten named roles in three tiers (lead, lead_important, visual, writing, hard, fact, review, simplify, aesthetic, chore) with does/does-not columns in `templates/claude-global.md`.
- `bin/models` and `templates/roles.toml.example`: providers, command templates and role candidates in a local `~/.config/research/roles.toml`; renders `~/.config/research/models.md`, which `bin/kb sync-agents` adds to generated rules; running `bin/models` regenerates the table and syncs agent rules, `get <role>` prints one role and `check` probes providers. Change roles by editing `roles.toml`.
- `bin/new-task`: numbered task directory from a card on stdin, `findings/` created, initial STATUS, Lead started; Lead cap `RESEARCH_MAX_LEADS` under herdr.
- `bin/build-routers`: generates skill routers from a local `~/.config/research/routers.toml` and checks that every library skill belongs to exactly one router.
- `bin/lead-reload`: injects STATUS, conclusion lines and task memory after `/clear` or compaction, with a reminder after 3 compactions; the dispatcher's session start injects `TODO.md`, unfinished task STATUS and the last 3 finished tasks.
- Delegation rules: explicit model on every delegation, brief with scope, method, acceptance command and reply limit, one-shot background runs, exploration findings in `findings/<topic>-<executor>.md` with `file:line`, no fixed fan-out for read-only work.
- Bounded review loop: one parallel round (two code reviewers on different models, aesthetic for visual work, simplify), one merged fix list for the original builder, one re-review of the fix diff; verification and hardening rules; three-part merged result.
- Executor conventions: no edits to conclusion sections or rule files, a fixed `conflict:` line, citations on every card claim, and the single load/do-not-load list for code-minimization skills.
- `bin/kb lint`: errors for `bin/…` and `templates/…` paths in rule files that do not exist; warnings for size budgets and for finished task directories over 200 MB; `--brief` output.
- `templates/local.md.example` sections for machine, time, concurrency measure, storage tiers, browser checks, notifications and accounts, each with a recommended way to fill it.
- README sections "Customize for your environment", a command table, context after `/clear`, and an optional whole-workspace Git layout.

### Changed

- Task card: `Type` (free text), `Pre-authorized`, verbatim question, frozen version under the alignment record, and `findings/` and `memory/` in Execution. The card stays at `experiments/<id>/README.md`.
- Conclusions use `## Conclusion (YYYY-MM-DD[, topic])` with `- **Tendency**:` and `- **Confidence**:` lines, which `bin/kb index` parses.
- `bin/status` refreshes the board and index on every change, not only on `done`.
- `bin/spawn-lead` takes the Lead model from `bin/models`, falls back to the legacy `~/.config/research/roles` file and then to plain `claude`, passes no model when `--kind` differs from the role's provider, and prints a `Lead selection` line with the start prompt.
- `bin/rules-push` runs `bin/install-rules`, then `bin/kb lint` (only errors outside `experiments/` block), then `bin/scrub-check` before pushing and keeps the local commit when a rebase fails; `bin/rules-pull` warns instead of blocking and skips during a rebase.
- `bin/install-rules` does not install the weekly cron job when `HOME` is in a temporary directory (`/tmp` or the macOS temporary folder).
- Browser, timezone, notification and concurrency specifics moved out of the rules into `local.md`.

## 0.1.0 - 2026-10-18

### Added

- Initial release: dispatcher, Lead and executor workflow; three runtime environments (`cli-herdr`, `cli-plain`, `app`); `research-setup` skill with deploy, hardware probe, hook merge and offline smoke test; task board with optional Notion mirror; private rules overlay; `bin/scrub-check`; optional components.
