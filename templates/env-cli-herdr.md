## Runtime environment: terminal CLI with herdr

- Open a task with `bin/new-task <slug> [--important] < card.md`; it calls `bin/spawn-lead`, which creates a herdr tab and starts the Lead there (model from `bin/models get lead` or `lead_important`; if `roles.toml` has no such role, from the legacy `.agenthelm/config/roles`, else plain claude). When `--kind` differs from the role's provider, no model is passed and that harness uses its default. At most `RESEARCH_MAX_LEADS` Leads (default 10) run at once.
- Dispatcher and Leads message each other: within one harness use its built-in cross-session messaging; when Claude and Codex are mixed, send with `herdr agent prompt <agent> "<message>"` and read replies with `herdr agent read <agent>`.
- Notify the user through STATUS plus the dispatcher; push channels, if any, are named in `local.md`.
- On finish, close the herdr tab and confirm no process is left.
