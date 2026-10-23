## Runtime environment: desktop app

- 运行入口是 `app.codex` 或 `app.ccd`，以当前真实 session 绑定优先；工作区 env 仅是无绑定时的默认选择。
- 创建、读取、等待、追加、交接与原生 Executor 操作前，读取 `skills/agenthelm-workflow/references/app-host.md`，按 prepare、原生工具、result 顺序执行。项目脚本只生成请求与验证回执，不会调用聊天内工具。
- 未注册根会话不自动成为 Dispatcher。原生核对身份后，用户指定的主控用 `bin/dispatch --entry ENTRY --session ID` 注册；`--print` 仅预览。
- Lead 身份绑定与运行取证分开：父会话确认原生 session、工作区、任务目录、可见性和独立性即可用 identity 回执绑定；CCD 可用 settings 回执保存设置读回。Lead 直接执行授权任务，运行证据通过后续 read 补录，不阻塞启动或执行。Executor 完成委派和验收后回报，父会话事后核验，无启动握手或等待本地绑定。排队或未知创建结果保留原请求，不重复创建或回退 CLI。
- Lead 用 `bin/status` 更新任务状态；会话空闲不等于任务验收完成。按需读取和有界等待，没有常驻 watcher。结束活跃跟踪时保留聊天。
