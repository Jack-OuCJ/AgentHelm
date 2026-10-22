---
name: research-setup
description: 初始化或调整当前 AgentHelm 工作区、选择和安装领域 skills 时使用。管理项目配置和领域技能，保留用户全局配置与 skills。
---

# 配置工作区

本仓库为 workspace-only 适配。不要使用上游全局安装步骤。

1. 核对当前工作区和用户指定目录一致，检查 Git 改动，保留已有文件。
   首次初始化时按下方流程一次询问领域技能的安装范围、注册方式和注册目标。复用用户已明确选择的范围；升级时保留已安装技能，不默认扩大全库。用户只要求安装领域技能或切换注册方式时直接进入下方流程，无需重新部署。
2. 在工作区根目录运行 `python3 skills/research-setup/scripts/deploy <当前工作区绝对路径> --role dispatcher --env cli-herdr`。其他位置需先独立克隆；不复制或重写现有全局 skills。
3. 配置保存在 `.agenthelm/config/`。编辑 roles.toml 后运行 `bin/models`；default 沿用各 CLI 默认设置，分档模型需用户另行指定。
4. 本地入口 AGENTS.md/CLAUDE.md 来自 `templates/workspace-*.md`。修改入口模板再运行 `bin/kb sync-agents`；已有非本工具生成的入口文件必须手动合并。协作、执行者、环境和研究规则由 `bin/install-rules` 从 templates 生成到生效位置；修改这些模板后运行该命令同步。运行时读取 `rules/` 下的生效文件及根目录 `rules-extra.md`；配置示例初始化和任务卡生成仍读取 templates。
5. `.claude/settings.json` 的 SessionStart 钩子只属于本工作区；`skills/research-setup/scripts/merge-hooks` 保留其他本地设置、不写 HOME，并将旧的固定绝对路径钩子迁移为运行时定位。脚本按自身位置、钩子按会话项目目录识别根目录；安装记录和配置引用使用相对路径，整体移动 checkout 后无需重装。全局配置基线与历史快照中的路径保留原始证据。
6. 验证 `python3 skills/research-setup/scripts/smoke.py`、`bin/kb lint`、`bin/models check`。有基线时运行 `bin/global-config-check`。
7. 不配置 cron、全局插件、私有规则远端或外部通知；按需加载全局已有 skills。不要以隔离环境为由修改 HOME、CODEX_HOME 或用户已有配置。

安装不会启动 agent。领域技能只按明确选择安装，不自动安装依赖、插件或全局 skills。

## 选择和安装领域 skills

以下命令在当前 checkout 根目录执行。默认来源是 `K-Dense-AI/scientific-agent-skills`；脚本下载到 `.agenthelm/state/` 内的临时目录，退出时清理。只复制技能资源和许可证，不执行下载内容。

1. 安装前先确认三个独立选择，合并成一次提问；复用本次对话中已明确的选择，不重复索要授权：
   - 范围：跳过、指定技能、整个技能库。
   - 注册方式：**领域路由、逐技能注册、仅入库**。不能把“全部安装”推断为逐技能注册。
   - 注册目标：Claude、Codex 或两者；仅入库无需注册目标。不能默认注册到两者。
   选择领域路由时，同时确认由用户指定分类还是按用途自动分组；用户已授权自动分组时直接执行。缺少注册方式或目标时，先列目录和候选，保持问题待答，不执行安装。
2. 用户选择跳过时，不下载或安装。尚未确定技能名称时运行 `bin/install-component skills-library --list`，根据实际目录和用户任务给出候选名称和用途；查看目录不代表安装全库。输出包含来源提交，可用 `--ref <提交>` 固定后续预览和安装版本。
3. 按已选择的注册方式预览并安装。逐技能注册使用 `--agent claude|codex|both`；领域路由或仅入库使用 `--agent none`。CLI 安装时必须显式传 `--agent`。例如为领域路由下载两个技能：

   ```sh
   ./bin/install-component skills-library --skill scientific-writing --skill scientific-visualization --agent none --dry-run
   ```

   展示具体安装清单与项目注册位置。已有明确安装授权且预览无冲突时，使用相同参数去掉 `--dry-run` 执行，不重复索要确认。只有用户明确选择全库时才使用 `--all`。未给选择参数只列目录，不安装。切换已有技能的注册方式时，复用已安装文件，跳过下载。
4. **选择领域路由时必须完成分组和注册，不能在入库后结束。** 根据已安装技能用途维护 `.agenthelm/config/routers.toml`，每个库内技能恰好归一个路由；保留现有用户分类，将新增技能补入匹配分组。建议 `library = "../../skills-library"`、`output = "../../.agenthelm/routers"`、`prefix = "route-"`，路径相对于配置文件，所有输出必须在当前工作区。路由使用中文用途描述，以文档相对链接指向技能的完整 SKILL.md，并注明相对于路由文件的真实目录（先解析符号链接），不依赖启动目录或机器绝对路径；不复制或改写技能文件。
   按已选择的目标运行，例如注册两者：

   ```sh
   ./bin/build-routers --agent both --dry-run
   ./bin/build-routers --agent both
   ```

   用户选择将已有逐技能注册切换成路由时，以上两个命令均增加 `--replace-leaf-links`。该选项只移除安装清单管理、且仍精确指向本工作区技能库的项目链接；先检查全部冲突，再生成和注册路由，最后移除旧链接。`--agent none` 本身不会移除旧链接。
5. 技能资源位于 `skills-library/<名称>/`，许可证和目录位于 `skills-library/`；来源、版本和文件哈希保存在 `.agenthelm/state/skills-library.json`。Claude 项目入口为 `.claude/skills/`，Codex 为 `.agents/skills/`。仅入库不创建入口；领域路由只暴露路由入口，按需读取叶子技能。已有手写目录、注册冲突或技能本地修改先报告并保留，不强制覆盖。离线来源使用 `--source <本地库目录>`，只读来源，需包含技能及根 LICENSE 文件。
6. 验证库中技能文件哈希、分类完整且不重复、项目入口精确指向本工作区。切换路由时确认本次旧链接已移除、其他项目入口保留。运行 `bin/kb lint`；有全局配置基线时运行 `bin/global-config-check`。报告技能数、路由数、实际注册方式和未安装依赖，不把预览或仅入库报告为路由注册完成。CLI 未刷新技能发现列表时，在本工作区新开会话验证。
