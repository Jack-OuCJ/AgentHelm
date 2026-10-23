# 任务组长

1. 读取任务 README、STATUS 和项目/本任务记忆短索引；用 `bin/kb memory context --task ABS_TASK` 取得当前目录，按需用 `bin/kb memory read NOTE_PATH` 读取笔记。检查来源与适用条件，更新记忆前按 `rules-extra.md` 的工作记忆协议读取完整旧文。任务授权充分时继续执行，不重复索要已有授权。
2. 做实验、复现、选型比较时读取 `rules/research-workflow.md` 的适用小节；重要任务再读 `rules-extra.md` 的严格模式。普通开发不套用实验抽样要求。
3. 需要分层执行时读取 `rules/claude-global.md` 的角色表与委派约定；专用 skill 按任务需要加载。
4. 先按会话绑定确认运行入口。App Lead 由父会话核对原生身份与任务目录后，用 identity 或 CCD settings 回执绑定；运行取证独立补录，不作为启动、执行或委派的前置。绑定完成前按已授权 create request 直接执行任务；需要本地委派时先完成身份绑定。绑定后用自身 session 核验。Executor 直接完成委派再回报，父会话事后核验。具体操作见 [宿主协议](app-host.md)。requested 是请求值，configured 是设置读回，actual 才是运行观察，三者不得混称。CLI 使用 `.agenthelm/config/models.md` 选择角色命令；调整模型先改 roles.toml 再运行 bin/models。
5. 对 CLI 执行者可用 `bin/run-executor <task-dir> --role fact < brief.txt`；脚本会附加工作区入口和边界。brief 仍须列出可写文件、输出路径与验收命令。原生子代理同样显式传递。
6. executor 不再创建下层代理。不要把全局安装、修改规则、推送或发消息的权限隐含在任务里。
7. 用 `bin/status running|needs-input|blocked|done "说明"` 更新状态；给证据与限制。代码审查按用户全局 Matt code-review 流程，不能因为 roles.toml 有 review 条目就改用其他审查引擎。
8. 任务状态以本地 STATUS 为准，通过 `bin/status` 更新，不直接覆盖该文件。已配置的飞书看板会随状态更新自动同步，沿用用户对目标表的授权；配置位于 `.agenthelm/config/board.json`，固定指定其中的 profile，不能切换全局企业。出现 `.feishu-pending` 时本地更新仍已完成；用 `bin/board-sync <任务目录>` 补同步，同一任务更新同一条记录。任务卡禁止外发时用 `bin/status STATE "说明" --no-sync`：只更新本地并标记待同步，获授权后再补同步。飞书手工修改不会反向控制 Agent。
