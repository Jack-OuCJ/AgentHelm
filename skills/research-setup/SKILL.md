---
name: research-setup
description: 安装、检查或调整当前 AgentHelm 工作区的本地配置时使用。仅管理当前 checkout 的规则、路由 Skill、项目会话钩子和模型角色映射，保留用户全局配置与 skills。
---

# 配置工作区

本仓库为 workspace-only 适配。不要使用上游全局安装步骤。

1. 核对当前工作区和用户指定目录一致，检查 Git 改动，保留已有文件。
2. 使用当前 checkout 的 `scripts/deploy <当前工作区绝对路径> --role dispatcher --env cli-herdr`。其他位置需先独立克隆；不复制或重写现有全局 skills。
3. 配置保存在 `.agenthelm/config/`。编辑 roles.toml 后运行 `bin/models`；default 沿用各 CLI 默认设置，分档模型需用户另行指定。
4. 本地入口 AGENTS.md/CLAUDE.md 来自 `templates/workspace-*.md`。修改模板再运行 `bin/kb sync-agents`；已有非本工具生成的入口文件必须手动合并。
5. `.claude/settings.json` 的 SessionStart 钩子只属于本工作区；`scripts/merge-hooks` 保留其他本地设置，不写 HOME。
6. 验证 `scripts/smoke.py`、`bin/kb lint`、`bin/models check`。有基线时运行 `bin/global-config-check`。
7. 不配置 cron、全局插件、私有规则远端或外部通知；按需加载全局已有 skills。不要以隔离环境为由修改 HOME、CODEX_HOME 或用户已有配置。

安装不会启动 agent，也不自动安装科学 skills 库或生成几百个领域 skill。领域路由另用项目 `.agenthelm/config/routers.toml` 配置 `bin/build-routers`，library 和 output 都必须位于本工作区。
