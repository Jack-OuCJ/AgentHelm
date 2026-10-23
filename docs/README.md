# AgentHelm 文档

长期维护的项目文档保存在这里；任务的报告和 HTML 成品保存在对应任务的 `artifacts/`。调查材料、执行日志和原始证据留在任务 `findings/`，不再复制到另一份报告目录。

| 入口 | 用途 |
|---|---|
| [项目设计](design/) | 项目规格、设计与跨任务规范 |
| [架构决策](adr/) | 已接受的决定与取舍，沿用 Matt domain-modeling 约定 |
| [验证记录](validation/) | 项目级验收和宿主能力记录；历史证据包不代表当前运行状态 |
| [工作记忆](memory.md) | 项目、任务记忆的使用入口；完整协议以生效规则为准 |
| [工作区索引](../INDEX.md) | 生成的任务结论、文档、成品与记忆导航 |

项目规则源在 `templates/`，生效副本通过 `bin/install-rules` 刷新。根 `AGENTS.md`、`CLAUDE.md` 和各层 `MEMORY.md` 是生成入口，不直接编辑。

Matt 的本地工单保留 `.scratch/<feature>/issues/`，任务 README 链接对应工单；ADR 保留 `docs/adr/`。创建工具不改变文档的内容归属。
