## Runtime environment: desktop app (Claude app or Codex app)

- The app already provides sessions and projects; do not install herdr. `bin/new-task <slug> < card.md` (or `bin/spawn-lead <task-dir>` for an existing task) only prints the start prompt: create a new session or project pointing at the task directory and paste it (use a worktree if you want isolation).
- No dependence on cross-session messaging: a Lead writes STATUS with `bin/status`; the dispatcher reads `bin/board` or `BOARD.md`.
- Questions to the user go in the Lead's own session; the app provides notifications.
- Capabilities of background or sub-sessions depend on the app; when unsure, fall back to STATUS plus manual steps.
