## Runtime environment: desktop app

- 运行入口是 `app.codex` 或 `app.ccd`，以当前真实 session 绑定优先；工作区 env 仅是无绑定时的默认选择。
- 创建、读取、等待、追加、交接与原生 Executor 操作前，读取 `skills/agenthelm-workflow/references/app-host.md`，按 prepare、原生工具、result 顺序执行。项目脚本只生成请求与验证回执，不会调用聊天内工具。
- 未注册根会话不自动成为 Dispatcher。原生核对身份后，用户指定的主控用 `bin/dispatch --entry ENTRY --session ID` 注册；`--print` 仅预览。
- 缺少工具、目标 App 默认来源、实际模型或执行证据时，明确报告缺口并保留待处理状态；不能回退 CLI 或把提示、排队标识当成启动成功。
- Lead 用 `bin/status` 更新任务状态；会话空闲不等于任务验收完成。按需读取和有界等待，没有常驻 watcher。结束活跃跟踪时保留聊天。
