## Runtime environment: terminal CLI without a multiplexer

- `bin/new-task <slug> < card.md` (or `bin/spawn-lead <task-dir>` for an existing task) prints the start prompt and the task path; open the new session yourself (another terminal, tmux, a new `claude` or `codex` process in that directory) and paste it.
- No cross-session messaging: a Lead writes STATUS with `bin/status`; the dispatcher reads `bin/board`.
- When the Lead needs the user, it asks in its own session.
- Keep the number of simultaneous sessions within machine resources.
