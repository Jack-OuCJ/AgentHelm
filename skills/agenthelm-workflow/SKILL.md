---
name: agenthelm-workflow
description: 在 AgentHelm 工作区创建或调度研究任务、启动 Lead、委派执行、更新 STATUS 或恢复任务上下文时使用。按 dispatcher、lead、executor 角色逐层读取规则；不用于其他项目的一般开发任务。
---

# AgentHelm 工作流入口

先读取工作区根目录的 AGENTS.md。用户的全局规则、明确授权和当前宿主限制继续有效。

开始任务或恢复上下文时读取 `.agenthelm/config/env`，按其值只加载一份环境说明；启动提示已包含该说明正文时无需重复读取。配置文件不存在时使用 `cli-plain`；值不在下表中时，报告配置错误并停止启动，不猜测环境，也不改写配置。生效规则缺失时，报告缺失路径并提示运行 `bin/install-rules`，停止启动，不回退读取模板。

| env | 环境说明 |
|---|---|
| `cli-herdr` | `rules/env-cli-herdr.md` |
| `cli-plain` | `rules/env-cli-plain.md` |
| `app` | `rules/env-app.md` |

仅加载当前需要的一项：

| 当前任务 | 读取 |
|---|---|
| 根目录主会话，建任务、看进度、交接 | [dispatcher](references/dispatcher.md) |
| 负责一个任务的组长，设计、验收、结论 | [lead](references/lead.md) |
| 接到明确范围的调查、实现、验证任务 | [executor](references/executor.md) |
| 模型分配、机器限制、运行环境 | `.agenthelm/config/models.md`、`.agenthelm/config/local.md` |
| 严格实验、长任务、上下文恢复、结论冲突 | `rules-extra.md`，只读相关小节 |

路径相对于本工作区根目录。切换角色时再加载对应 reference，不要预读全部文件。
本入口不会批量加载全局 skills，也不会屏蔽它们；任务需要专用 skill 时按用户现有规则加载。
