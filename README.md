# AgentHelm：本地优先的多智能体工作区

维护者：[Jack-OuCJ](https://github.com/Jack-OuCJ)。项目仓库：[Jack-OuCJ/AgentHelm](https://github.com/Jack-OuCJ/AgentHelm)。

基于 [blankhoney/agentlord](https://github.com/blankhoney/agentlord) 的 `main` 分支快照 `8c96addde0a35230bed7ff9db45affd1c31bf051` 创建。本分支包含工作区范围适配，不应直接照搬上游的全局部署教程。

配置范围限定在 `/Users/jack/Projects/AgentHelm`。全局 AGENTS.md、CLAUDE.md、skills、Claude/Codex 设置、账号、代理和 Herdr 钩子均不由本项目管理。项目会话仍会读取用户级规则及可发现的 skills；本适配实现配置分域，不提供操作系统级安全隔离。

## 开始使用

首次使用先初始化当前 checkout，再进入 Herdr：

```sh
cd /Users/jack/Projects/AgentHelm
python3 skills/research-setup/scripts/deploy "$PWD" --role dispatcher --env cli-herdr
herdr
```

在 Herdr 内的终端启动主会话：

```sh
./bin/dispatch
```

Codex 主会话可用 `./bin/dispatch --kind codex`。部署不会自动启动或连接现有会话。

向主会话描述任务即可。需要独立 Lead 时，先准备 `templates/task-card.md` 格式的任务卡，再运行：

```sh
./bin/new-task my-task < /path/to/card.md
```

任务目录会编号为 `experiments/001-my-task/`，Herdr 在该目录创建独立 Lead 会话。该命令会真正启动模型，需在任务授权范围内使用；安装自检使用替身，不调用模型。

没有 Herdr 时将 `.agenthelm/config/env` 改为 `cli-plain`，`spawn-lead` 会打印交接提示而不创建会话。

## 会话与规则如何组合

主会话 → 任务卡 → Lead → 明确范围的 executor → 验收与结论。文件是持久交接载体，Herdr 提供会话容器。每个角色仍需按需加载 skill，不会自动继承父会话所有上下文。

- 根入口：`AGENTS.md`；Claude 的项目 `CLAUDE.md` 引用它。
- 本地路由：`skills/agenthelm-workflow/SKILL.md`，按角色读取 references。
- 注册位置：`.agents/skills/`（Codex）和 `.claude/skills/`（Claude），均链接到本仓库真实 skill，未注册到全局。
- 实验方法：`rules/research-workflow.md`、`rules-extra.md`，仅在需要时读取。
- 模型映射、机器约定：`.agenthelm/config/roles.toml`、`models.md`、`local.md`。
- Claude 项目 SessionStart：`.claude/settings.json`；恢复主会话和任务上下文，不联网同步规则。
- 既有全局 skills 仍可用，不覆盖、不搬移；代码审查继续按 Jack 的 Matt code-review 规则。

`bin/spawn-lead`、`bin/dispatch` 和 `bin/run-executor` 都会显式传递根规则、路由和角色路径。原生子代理也需在委派中写出这些信息；仅在项目目录启动不代表 skill 正文已加载。

## 模型分配

首次配置中，Claude 负责主会话、Lead、fact/chore/writing/visual/aesthetic；Codex 负责 hard/simplify。所有候选均为 `default`，复用各 CLI 的现有模型、账号与权限。因此目前分角色，但尚未按价格档位分配不同模型。

编辑 `.agenthelm/config/roles.toml` 后运行：

```sh
./bin/models
./bin/models check
```

`review` 条目只是能力映射；不能覆盖用户的代码审查规则。`bin/run-executor` 不提供 review 模式。CLI 的模型标识和 effort 需按实际服务配置填写。

## 领域 skills 路由

本仓库不预装领域 skills。`bin/build-routers` 根据手写 TOML 分组和每个 skill 的 metadata 生成目录与指向 SKILL.md 的索引；不会自行训练路由模型或替你决定分类。

示例存为 `.agenthelm/config/routers.toml`：

```toml
library = "../../skills-library"
output = "../../skills"
prefix = "route-"
[routers.example]
title = "示例任务"
description = "在处理对应领域任务时使用。"
skills = ["example-skill"]
```

库中的每个 skill 必须恰好归一个路由。library/output 必须在工作区；生成后在项目 `.agents/skills` 和 `.claude/skills` 注册需要的路由。已有手写 skill 不会被同名生成覆盖。

## 自检与维护

```sh
python3 skills/research-setup/scripts/smoke.py
./bin/kb lint
```

如需核对全局规则、配置和 skills 是否变化，先运行 `bin/global-config-check --record` 建立本机基线，后续运行 `bin/global-config-check` 只读比对。基线保存在 `.agenthelm/state/`，不会随 Git 克隆；后续你自己改了全局配置会正常报告变化，不会自动回滚。

重复部署：

```sh
python3 skills/research-setup/scripts/deploy /Users/jack/Projects/AgentHelm --role dispatcher --env cli-herdr
```

工作区配置和任务内容被 Git 忽略。规则入口编辑 `templates/workspace-*.md` 后运行 `bin/kb sync-agents`；不要直接改生成的入口。

全局组件安装、私有规则覆盖、自动 push/cron 已禁用。任务看板需在本机单独配置；未配置时只维护本地状态。合并上游更新时应逐项检查是否重新引入全局行为，不能直接重置或强制覆盖本地适配。

## 飞书任务观测

配置飞书看板后，每次调用 `bin/status`，先原子更新本地 STATUS、看板和索引，再运行 `bin/board-sync` 同步到飞书。同步固定使用 `board.json` 指定的 profile 和用户身份，保留既有 lark-cli 全局企业选择。

目标表、视图、稳定字段 ID、中文状态映射及工作区标识保存在 `.agenthelm/config/board.json`，其中不保存账号密钥。实际凭据由既有 lark-cli 管理；授权到期时需重新授权原 profile。

- 同一个工作区标识加任务编号对应同一条记录。同步先精确查找再创建或更新；并发写入在工作区内串行，遇到重复标识会停止同步。
- 四种状态映射：running → 进行中，needs-input → 待输入，blocked → 阻塞，done → 完成。
- 同步字段包括任务名称、编号、状态、进展、Lead 标签、更新时间、结论、成本及工作区。Lead 是会话命名约定，不是进程存活证明；成本仅同步手工传入的值，不自动计算。
- 读取飞书记录使用 NDJSON 文件；写入后按字段 ID 回读校验。若远端写入结果不明，下次先查询标识，避免盲目重复创建。
- 网络、权限或字段错误不覆盖本地状态，也不让本地状态更新失败；任务目录留下 `.feishu-pending`，本地看板和主会话恢复提示会显示待同步。
- 这是一向观测同步。飞书编辑不会触发本地 Agent，也没有常驻轮询、心跳或定时任务。状态变化由 Lead 主动调用命令报告。

在任务目录报告进展：

```sh
/Users/jack/Projects/AgentHelm/bin/status running "正在验证"
/Users/jack/Projects/AgentHelm/bin/status done "验证完成"
```

从工作区根目录补同步全部任务：

```sh
./bin/board-sync --all
```

自动化测试使用替身 CLI，不连接真实飞书服务。目标表及 profile 必须在本机明确配置并授权；原工作区的配置和验收记录不会随代码迁入新项目。

## 许可

AgentHelm 采用 [MIT License](LICENSE)。所包含的上游代码的原始版权与完整许可见 [NOTICE](NOTICE)。
