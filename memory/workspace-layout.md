---
id: workspace-layout
scope: project
kind: decision
status: active
summary: 任务成品归任务，项目文档归 docs；不再以 claudedocs 或通用 cards 归档
verified_at: 2026-10-22
valid_when: 设计 AgentHelm 产物存放或迁移时读取；用户未另行改变该项目选择
sources: ["docs/README.md", "docs/memory.md"]
---

# 工作区归属选择

用户明确要求不再使用 `claudedocs/`，并授权迁移旧内容、补齐记忆和工作区规则。这里保存的是该项目选择，不是用户跨项目的默认偏好。

任务报告和 HTML 成品保存在对应任务 `artifacts/`，调查与证据保存在任务 `findings/`。长期项目设计及架构决定归 `docs/`。Matt 本地工单保留 `.scratch/<feature>/issues/`，ADR 保留 `docs/adr/`；按内容职责维护，不按创建工具建立另一套归档。

一个正文只有一个维护源。目录、任务 README 和记忆只提供导航，不复制另一份设计或决定。任务 STATUS、App 绑定与配置仍从各自真实来源读取。

如果以后改变目录协议，先核对消费脚本、宿主发现入口和历史证据的引用，不只改目录名。旧路径可以作为历史证据保留在迁移清单中，不代表继续使用旧归档入口。
