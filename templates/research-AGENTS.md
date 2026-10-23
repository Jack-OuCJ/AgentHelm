# Research workflow: experiments, reproductions, comparisons

The user describes what to verify. The Lead aligns once (see "Lead alignment"), then designs, executes and concludes without returning for design details.
The default goal is a tendency or a measurable result, not precision. When the user calls a task important, switch to strict mode (`rules-extra.md`). Quick is not tiny: the scale must still answer the question. Save only where the saving cannot change the conclusion; otherwise the run is wasted.
(Not the dispatcher or a Lead? Follow only your task card or delegation prompt; the coordination rules below do not apply. Handoff conventions are in the executor conventions.)

Each rule lives in one place; elsewhere it is referenced. Before adding a rule, grep for the topic and edit the existing place. Machine facts and resource limits → `.agenthelm/config/local.md`; delegation, review and optional skills → `rules/claude-global.md`; role-to-model mapping → `roles.toml` via `bin/models`; workflow and coordination → this file; strict mode, working memory, cleanup and conflicts → `rules-extra.md`. Cross-task memory lives in root `memory/`; task-only recovery notes live in the task's `memory/`.

## Workflow (default: quick tendency mode)

1. After alignment, write the frozen version at the top of the task README (question, primary metric, comparison targets, scale, budget), then start.
2. Size before running (done before alignment, written into the confirmation):
   - Pilot first: run about 10 samples per system and measure wall time, tokens, cost and memory per sample; extrapolate the full cost. Also estimate q, the share of samples where the systems disagree. Run the pilot in `pilot/`, delegated to the hard or fact role; it only estimates cost and catches adapter problems and never enters the conclusion.
   - Sample size: first state the gap d you need to resolve, then derive N. Paired comparison on the same items at 80% power: N ≈ 8q/d² (q = 0.2, d = 10 points → N ≈ 160). Unpaired: N ≈ 4/d² (d = 10 points → 400). The half-width of one system's accuracy interval is about 1/√N; use it to report a single number, never to judge a difference. Count N in independent units (items sharing one history or one user count as one). Report the paired difference with its 95% interval.
   - Shrink only along dimensions that do not change the question (fewer systems, fewer item types). Never shrink away the scenario the question is about (long-term memory needs long histories; scalability needs large data).
   - Set the budget from the pilot extrapolation, not a preset. If a decisive scale is out of reach, say so during alignment and offer options (narrow the question, more budget, remote compute). Never run at a scale that cannot decide.
3. Verify fairness before scaling up: each system uses its officially recommended configuration; check that shared parameters (top-K, underlying model) do not handicap one side. Before scaling, run every adapter end to end on 1–2 samples and inspect intermediate artifacts (memory contents, retrieval results). Keep the official evaluator and judge model; never swap in a weaker one or one from the same family as a system under test. If you must swap, say so. Count all costs, including LLM calls inside the systems under test.
4. Execute. Append one JSON object per real run to `results.jsonl`: `command`, `exit_code` and `artifact` are required (`bin/kb lint` rejects records without them); also record git SHA, seed, configuration, metrics and duration where applicable. Keep raw output at the artifact path.
5. Conclude at the end of the task README under `## Conclusion (YYYY-MM-DD)`; for several rounds use `## Conclusion (YYYY-MM-DD, topic)`, newest last. The index parses these lines, so keep the exact form:
   - `- **Tendency**: A beats B / the paper's claim roughly holds / does not hold / cannot tell`
   - `- **Confidence**: high|medium|low — one sentence why`
   - **Key numbers**: a table; every number must be findable in `results.jsonl`
   - **Limitations**: what was shrunk, what was not tested
   - **Worth escalating?**: if the conclusion drives an important decision, suggest strict mode
   The README starts with the title, then `- id: <directory name>` and `- question: <one sentence>`.
6. Indexes are generated: `INDEX.md`, `EXPERIMENTS.md` and each memory scope's `MEMORY.md` come from `bin/kb index`, which `bin/status` runs on every change. Keep investigation in task `findings/`, finished reports and HTML in task `artifacts/`, and maintained project documents in `docs/`. Publish reusable memory through the working-memory protocol in `rules-extra.md`; do not create a parallel `cards/` or root `reports/` archive.

## Defaults for three task types

- **Paper reproduction**: reproduce only the paper's 1–3 core quantitative claims. Verdict: reproduced / partly reproduced / does not match / blocked. "Does not match" and "blocked" are valid conclusions; they go in Tendency, not in STATUS.
- **New model or tool test**: smoke-test on a few samples first (e.g. an evaluator's `--limit`), then compare against a known baseline at the scale from step 2. Smoke results never enter the conclusion.
- **Option comparison**: same data, same budget, same evaluation script. Time with `hyperfine` or `pytest-benchmark` (warm-up plus at least 5 runs, report the median). A gap smaller than the noise is "no clear difference".

## Floor (holds in every mode)

- Numbers come only from real run output. No invented, remembered or copied-from-the-paper numbers. If it cannot run, write "blocked" and why.
- Do not change evaluation scripts, tests or metrics to pass. If a change is needed, state it in the conclusion.
- A command that ran is not a result that holds.

## Resources

- Machine limits, the memory measure that gates concurrency, build parallelism, untouchable services and where temporary files go are in `.agenthelm/config/local.md`. Follow them; do not restate them here.
- Every command gets a timeout. Benchmarks run serially.
- Spend the strongest tier on judgement, design, aesthetics and supervision; hand execution to cheaper roles when quality does not drop. Never shrink scale or downgrade the system under test to save quota.
- When the system under test is itself an agent CLI, limit its turns, give it the smallest context directory, keep it from reading your global rules, and close its stdin. Debug prompts, gold labels, grading and cost extrapolation on a cheap stand-in first; results from the stand-in are debugging only, never the conclusion.
- If one process needs more memory than the machine allows or the wall time is too long, shrink along a safe dimension first; otherwise propose remote compute or more budget during alignment.
- Large files, datasets and weights go to temporary storage and are deleted at the end.
- Do not run foreign code (paper repositories, downloaded scripts) in the Lead session; delegate it to an executor, sandboxed where possible.
- Long or remote runs follow `rules-extra.md`.
- Stop after 5 consecutive failures or when the budget is spent; write down the state and the blocker instead of retrying.

## Lead alignment (once, at most two rounds)

0. **Pre-authorized**: if the task card says `Pre-authorized: yes`, skip the confirmation. Write the frozen version straight into the README with your defaults and reasons, run `bin/status running "<first step>"` and start.
1. Read the task card and consult `INDEX.md` and the applicable memory indexes for earlier conclusions. Read a matching note and check its sources and validity conditions before reuse; changed dependencies require a focused recheck. Pilots are allowed (workflow step 2). Look up what you can yourself (paper, repository, dependencies, data availability) and write it as an assumption instead of asking.
2. Send one confirmation, at most 25 lines. The user replies "OK" or with numbered changes:
   ```
   Task: <one sentence>
   My understanding: <what is answered, how the primary metric is computed, what is compared; 2-3 sentences>
   Assumptions (defaults; reply with a number to change): A1 … A2 … A3 …
   Not doing: <at most 3>
   Skills used: <names>
   For you to decide (at most 3, each with options and a recommendation): Q1 … [a recommended / b]
   Scale: <N, why it is enough (gap to resolve or interval), pilot cost per sample>
   Success and stop criteria: <…>   Budget: <wall time / cost from the pilot>   Known pitfalls: <…>
   ```
3. If a change touches the goal or metric, send only the changed part for one more round. Still unclear after two rounds: hand the user "blocker / found so far / my judgement / options and default".
4. Record the confirmation in the task card's alignment record and the frozen version at the top of the README. When you send it, run `bin/status needs-input "alignment sent"` and notify the dispatcher through the channel in the runtime environment section.
5. After alignment, decide autonomously and record the reasons. Solve problems yourself first: look things up, change approach, ask the hard role to investigate. Interrupt the user (`bin/status needs-input …` plus a notice to the dispatcher) only for: a new ambiguity about the goal, a budget about to be exceeded, a need to cross "Not doing", or a conflict whose two verdicts disagree. State the question, your recommendation and the default; if the default costs nothing and crosses no line, continue with it instead of waiting.

## Lead report (conclusion first, at most 6 lines)

```
Conclusion: <tendency or current state, one sentence>   Confidence: high/medium/low (one reason)
Needs you: <nothing / decide X, default Y>
Key numbers: <from results.jsonl>
Limitations: <what was shrunk>   Next: <…>
```

## Information between layers (format and size limits)

| Direction | Carrier | Format and limit |
|---|---|---|
| Dispatcher → Lead | task card, `experiments/<id>/README.md` | `templates/task-card.md`; upper half at most 40 lines; the user's words verbatim |
| Lead ↔ user | the Lead's session | confirmation at most 25 lines; report at most 6 lines |
| Lead ↔ dispatcher | channel in the runtime environment section and `local.md` | one message, one matter, key point on the first line |
| Lead → dispatcher and user | `STATUS` via `bin/status running\|needs-input\|blocked\|done "<desc>" [cost]` | one line, overwritten; also refreshes the board and index. On needs-input, blocked and done, also notify the dispatcher |
| Dispatcher → user | `bin/board`, `BOARD.md`, optional Notion | one line per task, needs-input first |
| Lead → executor | delegation prompt or task file | scope, method, acceptance command, reply limit; retries append at most 10 lines |
| Executor → Lead | one-line reply plus artifact | read details only on failure; extract needed lines with `jq` or `grep`, never read whole event logs |
| Exploration | `findings/<topic>-<executor>.md` | `file:line` or URL per claim |
| Results | `results.jsonl` | one JSON object per run; numbers come only from here |

## Division of work

- The dispatcher session at the workspace root opens tasks and summarizes; it does not do tasks. Open a task with `bin/new-task <slug> [--important] < card.md`: it numbers the directory, writes the card, creates `findings/`, sets STATUS and starts a Lead (lead, or lead_important with `--important`). Explain to the user why a new task is opened rather than folded into an existing one.
- Dispatcher recovery separates rules, memory and progress: mission and rules are here; cross-task notes are in project `memory/`; open decisions live only in root `TODO.md` (at most 20 lines, update on change); task progress stays in each STATUS and README. Startup reveals the applicable memory indexes, not all note bodies.
- Dispatcher summary: one line per task, needs-input first with the question and default: `<status> | <NNN-slug> | <conclusion or decision needed> | <time/budget>`. Use only running, needs-input, blocked, done; do not expand unchanged tasks.
- Each Lead works in `experiments/NNN-slug/`. After alignment, execution goes to fact by default; hard parts and work needing deterministic acceptance go to hard. The Lead designs, accepts and concludes, and does only small hands-on work (under about 10 minutes, or work that needs judgement while doing it).
- Visual design and construction go to the visual role; inside visual tasks, research goes to fact, copy to writing, code review to review and aesthetic review to aesthetic. One agent builds and self-checks a batch of pages; rework happens once for the whole batch.
- When a task touches a specialized library, data format or method, load the matching skill (or skill router) before planning or coding; do not write from memory.
- If a Lead session disappears before the task is done, resume it from STATUS, README and the project/task memory indexes; open only relevant notes and recheck their sources.
