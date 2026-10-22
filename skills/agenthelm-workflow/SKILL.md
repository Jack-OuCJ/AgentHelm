---
name: agenthelm-workflow
description: 在 AgentHelm 工作区创建或调度研究任务、启动 Lead、委派执行、更新 STATUS 或恢复任务上下文时使用。按 dispatcher、lead、executor 角色逐层读取规则；不用于其他项目的一般开发任务。
---

# AgentHelm 工作流入口

先读取工作区根目录的 AGENTS.md。用户的全局规则、明确授权和当前宿主限制继续有效。

开始或恢复时，先按宿主真实 session ID 查询 `.agenthelm/state/app-sessions.json` 的绑定；已绑定会话使用其 entry，显式 entry 必须与绑定一致。App 入口对应 `rules/env-app.md`，并在执行原生操作前读取 [App 宿主协议](references/app-host.md)。没有绑定时再读取 `.agenthelm/config/env`，按下表加载一份环境说明；缺文件使用 `cli-plain`。未知值报告错误，不改写配置。生效规则缺失时报告路径并提示运行 `bin/install-rules`，停止启动，不回退模板。启动提示已含对应说明时无需重复读取。

根目录与 `.agenthelm/config/role` 只是 CLI 历史约定，不授予 App 调度身份。App 的唯一 Dispatcher 以当前绑定为准；未注册会话先核验原生身份，再按用户授权注册或交接。旧主控只读恢复，不重新注册抢占。

| env | 环境说明 |
|---|---|
| `cli-herdr` | `rules/env-cli-herdr.md` |
| `cli-plain` | `rules/env-cli-plain.md` |
| `app` | `rules/env-app.md` |

仅加载当前需要的一项：

| 当前任务 | 读取 |
|---|---|
| 有效 Dispatcher，建任务、看进度、交接 | [dispatcher](references/dispatcher.md) |
| 负责一个任务的组长，设计、验收、结论 | [lead](references/lead.md) |
| 接到明确范围的调查、实现、验证任务 | [executor](references/executor.md) |
| 模型分配、机器限制、运行环境 | `.agenthelm/config/models.md`、`.agenthelm/config/local.md` |
| 严格实验、长任务、上下文恢复、结论冲突 | `rules-extra.md`，只读相关小节 |

路径相对于本工作区根目录。切换角色时再加载对应 reference，不要预读全部文件。
本入口不会批量加载全局 skills，也不会屏蔽它们；任务需要专用 skill 时按用户现有规则加载。
