---
name: research-setup
description: Interactively install or upgrade a local research workspace for Claude Code and Codex, including task tools, private rules, optional components and session context.
---
# Research setup

Use the same skill for first installation and upgrades. Run scripts from this
skill's directory; locate the kit root through the resolved skill path.
Requirements: Linux or macOS, Python 3.9+, Git, POSIX sh and jq.
When a requirement is missing, install it with the package manager named in `~/.claude/local.md` (a user-level one if none is named yet), append it to the install log named there (default `~/.config/research/installs.log`; date, command, reason, uninstall command) and list it under **Installed:** in the installation summary; hand anything that needs an administrator password to the user.

## 1. Ask once

Collect these choices together; reuse confirmed choices on subsequent runs:
- Installation directory (default `~/research`, or the saved install-dir).
- Environment, saved to `~/.config/research/env`: `cli-herdr` (terminal CLI, herdr recommended), `cli-plain` (terminal, no multiplexer) or `app` (Claude app / Codex app); Claude Code, Codex, or both. On upgrade, reuse the saved value unless the user changes it.
- Role: dispatcher or ordinary executor, saved to `~/.config/research/role`; reuse the saved value on upgrade.
- Board: Notion (recommended; local board is also kept) or local only as the fallback.
- Optional components: herdr, ponytail, caveman, claude-hud, skills-library.
- User-owned private rules repository URL, or none.

Recommend herdr for terminal CLI users, but install it only if `cli-herdr` is chosen.
Desktop applications (`app`) do not need herdr; they use their own sessions and projects. claude-hud is Claude Code only.
Explain that optional plugins may enable upstream hooks; keep selection explicit.
Never ask for secrets in chat. Notion credentials belong in the local config file.

## 2. Prepare and measure

Create the selected directory and `~/.config/research`.
Run `scripts/hardware` and show its actual output. Draft `~/.claude/local.md`
using that output and `templates/local.md.example`; preserve existing user facts.
Ask the user to confirm this concrete draft before writing it. Do not infer GPUs,
service exclusions, permissions or safe workload limits from CPU/RAM alone.
Save an existing differing local.md as local.md.before-agenthelm before writing.

## 3. Install or upgrade the kit

Run `scripts/deploy <directory> --role dispatcher|executor --env cli-herdr|cli-plain|app`.
On upgrade omit `--role` and `--env` to reuse the values saved in
`~/.config/research/role` and `~/.config/research/env`; pass them only on first
install or to change a saved choice.
Use `--rules-remote <URL>` when selected, or `--rules-remote ''` for no private sync.
The script copies bin, templates and this skill, then runs install-rules.
It saves the directory and role under `~/.config/research` and registers the same
skill directory for both agents. Other workspace files are retained.
Existing global rule files are backed up before replacement.

Private rules are shallow-cloned to `~/.local/share/research-rules`; their rules/
and templates/ overlay the kit. Edit private rules in that checkout, not the
rendered installation. If already present, run installed `bin/rules-pull` to
rebase with autostash and apply updates. Failed pulls retain local commits; resolve
reported conflicts or a changed remote URL before pushing.
Without a private repository, use the shipped templates.
Run `bin/kb sync-agents` after any confirmed local.md change.

## 4. Install selected components

From the installed kit, run `bin/install-component <component>` only for selected
components. For ponytail/caveman pass `--agent claude|codex|both` matching the choice.
For claude-hud pass `--agent claude`; then run `/reload-plugins` and
`/claude-hud:setup` inside Claude Code. If running in Codex, report that activation
step as pending rather than claiming the HUD is active.
Use `bin/install-component herdr --dry-run` to preview the latest-release URL.
Already installed binaries/plugins are skipped; copied Codex and library skills
are refreshed from shallow temporary checkouts, which are deleted afterward.
The library is cataloged under skills-library/CATALOG.md. Generate routers only
when the user supplies local `~/.config/research/routers.toml`; run
`bin/build-routers` without configuration to see its schema. No classification
table is shipped.
Individual scientific skill dependencies remain user-selected.

For Notion, have the user configure `~/.config/research/notion.env` locally with
NOTION_DB and NOTION_TOKEN, restrict it to the user, and share the database with
the integration. Use a dedicated single-source database with Name (title) and
Status, Summary, Cost, Conclusion (rich text) properties. See the kit README.
Do not write credentials into the kit or echo them. Without configuration, status
updates stay local. Optionally save this machine's identity in
`~/.config/research/machine`; it is written only when the database already has a
Machine property (select or rich text). A completed task replaces the entire page
body with its latest conclusion; use dedicated pages. Selecting local-only on an upgrade requires disabling an
existing notion.env (rename it locally after explaining the effect).

## 5. Merge the Claude SessionStart hook

Run `scripts/merge-hooks` to display the proposed settings JSON. Explain that
this affects Claude Code; Codex uses generated AGENTS.md and the board command.
Show the diff against `~/.claude/settings.json` and ask for confirmation before
running `scripts/merge-hooks --apply`. This helper uses jq, backs up existing
settings before a change, preserves other settings/hooks and adds no duplicates.
The hook injects the board for dispatchers and task context at task roots;
no persistent watcher is started. If declined, leave settings untouched.
Codex-only users should manually run `bin/lead-reload <task-dir>` at session start.

## 5b. Weekly sync (only with a private rules repository)

Ask whether to enable the weekly user-level cron job (default yes; no sudo). `bin/install-rules`
registers `bin/rules-sync` idempotently (marker comment `# research-rules-sync`, minute offset
derived from the hostname); set `RULES_CRON=0` to skip (the choice is saved in `~/.config/research/rules-cron`). A HOME under `/tmp` skips cron unless `RULES_CRON=1` is explicitly supplied.
Cron needs non-interactive git auth:
run `gh auth setup-git` (or configure a credential helper/SSH key) and confirm a push works
without prompts. On failure rules-sync pushes nothing and writes one line to
`~/.local/state/rules-sync.status`, which the session-start hook displays.

## 5c. Optional role setup (every question skippable; skipped = write nothing)

Start from `templates/roles.toml.example` and propose a local
`~/.config/research/roles.toml`. Reuse an existing configuration on upgrade.
Ask each item; omitted answers leave existing choices unchanged, and skipping
role setup entirely writes nothing:
1. Available providers and their on/off switches in `[providers]`.
2. Each provider's command `template`, optional `research_flags` and optional
   `check` under `[commands.<provider>]`. Supported command placeholders are
   `{model}`, `{effort}`, `{research_flags}`. All CLI names come from these templates.
3. For each role (lead, lead_important, hard, fact, chore, writing, visual, review,
   simplify, aesthetic), confirm description, tier, candidate priority
   (`provider:model[:effort]`), mode (`first` or `all`) and research setting
   (`true`, `false` or `"split"`). Replace every example model for the user's environment.
4. Aesthetic work may use a dedicated model, a user-selected design skill, or be skipped.

Write only confirmed configuration; remove unchosen example roles/providers.
Edit `roles.toml`, then run `bin/models` to validate it, generate the local
`~/.config/research/models.md`, and run `bin/kb sync-agents` automatically.
`bin/models get <role>` displays the selected candidate; `bin/models check`
checks configured provider commands. A command template containing `{effort}`
requires an effort value in every candidate that uses it.
Legacy `~/.config/research/roles` (kind/model/effort) remains usable for Lead
launches when roles.toml does not exist or omits the requested lead or
lead_important role. Without either selection, spawn-lead defaults to Claude.
Neither file belongs in a repository.
On Python 3.9/3.10, configuration supports strings, booleans, integers, arrays
and TOML tables; use Python 3.11+ for other TOML syntax.

## 5d. Optional private scan terms

Ask whether the user wants a local `~/.config/research/scrub-terms.txt` (one
regular expression per line) for names, hosts and other private terms. They
edit this locally; never collect private terms in chat or copy them into the
kit. Skipping writes nothing. Without a list, scrub-check warns and checks
built-in secret patterns only. Run `bin/scrub-check <installation-directory>`.

## 6. Verify and report

Run installed `bin/kb index`, `bin/kb lint`, `bin/board`, and
`python3 skills/research-setup/scripts/smoke.py` from the kit root.
Smoke tests use a temporary HOME, not the user's configuration.
Report installation location, selected components, completed checks and any
pending activation/configuration. Never report unrun checks as passed.
Stop after two failed attempts at a step or when a design decision is needed.
