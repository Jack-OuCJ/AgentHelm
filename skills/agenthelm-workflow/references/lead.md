# 任务组长

1. 读取任务 README、STATUS 和 `memory/MEMORY.md`（存在时）。任务授权充分时继续执行；目标、指标或预算有关键缺失时才询问，不重复索要已有授权。
2. 做实验、复现、选型比较时读取 `rules/research-workflow.md` 的适用小节；重要任务再读 `rules-extra.md` 的严格模式。普通开发不套用实验抽样要求。
3. 需要分层执行时读取 `rules/claude-global.md` 的角色表与委派约定；专用 skill 按任务需要加载。
4. 先按会话绑定确认运行入口。App 首次创建尚未绑定时按 [宿主协议的绑定握手](app-host.md#首次创建的绑定握手) 完成首个授权动作；正式绑定后用自身 session 核验，并按该协议解析模型、委派原生 Executor。观察与追加由 Dispatcher 负责。默认值来自目标 App，实际参数单独核验。CLI 使用 `.agenthelm/config/models.md` 选择角色命令，默认模型是各 CLI 的现有默认；若要分价格档位，先在项目 roles.toml 明确配置，再运行 `bin/models`。
5. 对 CLI 执行者可用 `bin/run-executor <task-dir> --role fact < brief.txt`；脚本会附加工作区入口和边界。brief 仍须列出可写文件、输出路径与验收命令。原生子代理同样显式传递。
6. executor 不再创建下层代理。不要把全局安装、修改规则、推送或发消息的权限隐含在任务里。
7. 用 `bin/status running|needs-input|blocked|done "说明"` 更新状态；给证据与限制。代码审查按用户全局 Matt code-review 流程，不能因为 roles.toml 有 review 条目就改用其他审查引擎。
8. 任务状态以本地 STATUS 为准，通过 `bin/status` 更新，不直接覆盖该文件。已配置的飞书看板会随状态更新自动同步，沿用用户对目标表的授权；配置位于 `.agenthelm/config/board.json`，固定指定其中的 profile，不能切换全局企业。出现 `.feishu-pending` 时本地更新仍已完成；用 `bin/board-sync <任务目录>` 补同步，同一任务更新同一条记录。任务卡禁止外发时用 `bin/status STATE "说明" --no-sync`：只更新本地并标记待同步，获授权后再补同步。飞书手工修改不会反向控制 Agent。
