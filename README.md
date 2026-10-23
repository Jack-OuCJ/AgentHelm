# AgentHelm：本地优先的多智能体工作区

维护者：[Jack-OuCJ](https://github.com/Jack-OuCJ)。项目仓库：[Jack-OuCJ/AgentHelm](https://github.com/Jack-OuCJ/AgentHelm)。

基于 [blankhoney/agentlord](https://github.com/blankhoney/agentlord) 的 `main` 分支快照 `8c96addde0a35230bed7ff9db45affd1c31bf051` 创建。本分支包含工作区范围适配，不应直接照搬上游的全局部署教程。

配置范围限定在当前 checkout，根目录由工具自身位置识别。全局 AGENTS.md、CLAUDE.md、skills、Claude/Codex 设置、账号、代理和 Herdr 钩子均不由本项目管理。项目会话仍会读取用户级规则及可发现的 skills；本适配实现配置分域，不提供操作系统级安全隔离。

## 开始使用

首次使用从父目录进入 checkout（目录名按实际位置调整），初始化后进入 Herdr：

```sh
cd AgentHelm
python3 skills/research-setup/scripts/deploy "$PWD" --role dispatcher --env cli-herdr
herdr
```

在 Herdr 内的终端启动主会话：

```sh
./bin/dispatch
```

Codex 主会话可用 `./bin/dispatch --kind codex`。部署不会自动启动或连接现有会话。

向主会话描述任务即可。需要独立 Lead 时，把 `templates/task-card.md` 格式的任务卡作为标准输入交给 `bin/new-task`，正文直接保存到新任务 README；不另建通用 cards 归档。将下例的任务卡路径替换为实际文件：

```bash
./bin/new-task my-task < /path/to/task-card.md
```

任务目录会编号为 `experiments/001-my-task/`，Herdr 在该目录创建独立 Lead 会话。该命令会真正启动模型，需在任务授权范围内使用；安装自检使用替身，不调用模型。

没有 Herdr 时将 `.agenthelm/config/env` 改为 `cli-plain`，`spawn-lead` 会打印交接提示而不创建会话。

## 在 Codex Desktop 或 CCD 中使用

App 协议与 Herdr 可以共存，已有会话按自身 entry/session 绑定恢复，不必改整个工作区的 env。先由当前聊天的智能体核对原生会话 ID 和项目路径，再将用户指定的聊天注册为唯一 Dispatcher：

```sh
./bin/dispatch --entry app.codex --session REAL_SESSION_ID
```

`--print` 只读预览，不注册、不启动 CLI。已有 App 主控时，根目录 CLI 主控也会报冲突；通过显式 release/claim 交接。CCD 使用 `app.ccd`，但当前原生 create 能力尚未确认，自动创建应明确报缺口。

按角色编辑项目 `roles.toml` 的 App 模型/强度后，用 `bin/models resolve lead --entry app.codex` 查看请求绑定。default 需要目标 App 默认来源；当前 Dispatcher 的模型不等于新聊天默认。没有可靠默认证据时应报告缺口，或由用户配置显式角色 model/effort。

获准创建 Lead 后，智能体运行 `new-task` 或 `spawn-lead` 并传 `--session`、必要 `--app-params`，取得结构化请求；接着调用原生工具创建同项目 local 独立聊天，验证可见性、任务实际动作和生效参数，再用 `app-session result` 回写。脚本本身不会调用聊天工具。完整步骤与回执见 [App 宿主协议](skills/agenthelm-workflow/references/app-host.md)。

Lead 委派使用原生子代理；`run-executor --print` 只输出不可执行的预览，不保存待执行请求。`codex-session-evidence` 只读精确会话及轮次的实际模型/强度，不能证明可见性、任务动作或默认来源。读取、等待、追加均按请求/回执执行；人工调整后先重新观察。

已结束任务收到新的继续授权时，当前 Dispatcher 或原绑定 Lead 用 `bin/app-session resume --session OWN_ID --task ABS_TASK --reason "用户本次授权"` 恢复原绑定，Lead 再用 `bin/status running` 更新状态。恢复不创建聊天，保留模型与历史；并发上限、未决请求和宿主核验仍有效。

本地协议与离线验收已实现；[宿主能力记录](docs/validation/2026-10-22-app-host-capabilities.md) 单列真实验证和缺口。当前 Codex 独立 Lead 创建闭环仍待真实验收；不能把离线测试通过称为已接通。完成后停止活跃跟踪并保留聊天，没有常驻 watcher。

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

启动与上下文恢复先按实际 session 绑定选择 entry；App 使用 `rules/env-app.md`，无绑定的 CLI 再按 `.agenthelm/config/env` 注入对应 `rules/env-*.md` 正文。手动开启的会话通过工作流入口按相同映射读取；配置文件不存在时使用 `cli-plain`，未知值会报错，生效说明缺失会提示运行 `bin/install-rules`。Dispatcher 分派任务、Lead 分层执行时读取 `rules/claude-global.md`；Executor 读取 `rules/executor-agents.md`。

## 模型分配

首次配置中，Claude 负责主会话、Lead、fact/chore/writing/visual/aesthetic；Codex 负责 hard/simplify。所有候选均为 `default`，复用各 CLI 的现有模型、账号与权限。因此目前分角色，但尚未按价格档位分配不同模型。

编辑 `.agenthelm/config/roles.toml` 后运行：

```sh
./bin/models
./bin/models check
```

`review` 条目只是能力映射；不能覆盖用户的代码审查规则。`bin/run-executor` 不提供 review 模式。CLI 的模型标识和 effort 需按实际服务配置填写。

## 领域 skills 路由

本仓库不预装领域 skills。使用 `research-setup` 初始化或安装领域技能时，先确认三个独立选择：安装范围（跳过、指定技能、全库）、注册方式（领域路由、逐技能注册、仅入库）、注册目标（Claude、Codex、两者）。选择领域路由还需确定用户分类或自动按用途分组。已有明确选择会复用；“全部安装”只确定范围，不代表选择逐技能注册。

先看目录，再预览和安装选中的技能：

```sh
./bin/install-component skills-library --list
./bin/install-component skills-library --skill scientific-writing --agent both --dry-run
./bin/install-component skills-library --skill scientific-writing --agent both
```

默认从 [K-Dense Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills) 下载。输出包含实际来源提交；`--ref <提交/标签/分支>` 可固定版本。明确安装全库使用 `--all`；不带选择参数只列目录。离线库使用 `--source <本地目录>`，需包含 SKILL.md 和根 LICENSE 文件。

技能文件及附属资源复制到本工作区 `skills-library/<名称>/`，许可证和 `CATALOG.md` 一并保留。安装时必须显式选择 `--agent`：`codex` 在项目 `.agents/skills/` 注册逐技能链接，`claude` 在项目 `.claude/skills/` 注册，`both` 注册两处，`none` 仅入库。源版本和文件哈希记录在 `.agenthelm/state/skills-library.json`；下载临时目录也位于该工作区，退出后清理。安装不执行技能代码、不安装依赖、不启动 agent，也不修改 HOME 中的配置或技能。

再次选择同一技能可更新其来源内容；本地修改、未受管理的同名目录或已有注册冲突会在写入技能前报错。未选中的已安装技能保留。CLI 没有刷新发现列表时，在本工作区新开会话验证。

需要领域路由时，安装选 `--agent none` 仅入库，然后完成分组、生成和注册。已经安装的技能直接复用。`bin/build-routers` 根据配置中的用途分组和每个 skill 的 metadata 生成路由与 SKILL.md 索引；分组由用户指定或明确授权 Agent 按用途整理。

示例存为 `.agenthelm/config/routers.toml`：

```toml
library = "../../skills-library"
output = "../../.agenthelm/routers"
prefix = "route-"
[routers.example]
title = "示例任务"
description = "在处理对应领域任务时使用。"
skills = ["example-skill"]
```

库中的每个 skill 必须恰好归一个路由，library/output 必须在工作区。预览并向两个项目 CLI 注册路由：

```sh
./bin/build-routers --agent both --dry-run
./bin/build-routers --agent both
```

生成的路由和目录使用文档相对链接：路由中的路径相对于该 SKILL.md 的真实所在目录（先解析项目入口符号链接），目录中的路径相对于 CATALOG.md；与终端启动目录无关。项目注册链接也为相对链接，整体移动工作区后无需重新生成这些引用。

从逐技能注册切换为路由时，两个命令都增加 `--replace-leaf-links`。它先检查全部输出和入口冲突，只移除安装清单管理且精确指向本工作区技能库的逐技能链接，保留技能文件和其他项目入口。`--agent none` 本身不移除旧链接。已有手写 skill 不会被同名生成覆盖。重新生成时会清理已退役的生成路由及其对应项目链接。

## 自检与维护

```sh
python3 skills/research-setup/scripts/smoke.py
./bin/kb lint
```

如需核对全局规则、配置和 skills 是否变化，先运行 `bin/global-config-check --record` 建立本机基线，后续运行 `bin/global-config-check` 只读比对。基线保存在 `.agenthelm/state/`，不会随 Git 克隆；后续你自己改了全局配置会正常报告变化，不会自动回滚。

重复部署：

```sh
python3 skills/research-setup/scripts/deploy "$PWD" --role dispatcher --env cli-herdr
```

本机配置、任务过程和原始证据默认被 Git 忽略；明确公开的任务成品使用精确路径例外。长期项目文档在 `docs/`，任务报告和 HTML 在对应任务 `artifacts/`，调查与证据在任务 `findings/`；不再用 claudedocs、通用 cards 或根 reports 归档。Matt 工单保留 `.scratch/<feature>/issues/`，架构决策保留 `docs/adr/`。导航见 [文档入口](docs/README.md)。

项目经验在根 `memory/`，本任务恢复决定在任务 `memory/`。笔记是维护源，`MEMORY.md` 是 `bin/kb index` 生成的短目录；使用与校验见[工作记忆说明](docs/memory.md)。Dispatcher/Lead 启动只读适用目录，按主题显式读取正文；动态状态和权限仍实时核验。规则入口编辑 `templates/workspace-*.md` 后运行 `bin/kb sync-agents`；不要直接改生成的入口。

协作、执行者、环境和研究规则的来源在 templates。修改模板后运行 `bin/install-rules`，更新本工作区的 `rules/claude-global.md`、`rules/executor-agents.md`、三份 `rules/env-*.md`、`rules/research-workflow.md` 和根目录 `rules-extra.md`，并同步根目录入口。初始化时生成全部环境说明，运行时按会话绑定优先、无绑定再按 env 选择一份；修改模板后须同步才会影响后续加载。配置示例初始化、任务卡生成、规则校验和测试仍可读取 templates。

整体移动 checkout 后，脚本通过自身位置、项目 SessionStart 钩子通过会话项目目录识别新根目录，配置与技能链接保留相对关系。`.agenthelm/config/install-dir` 相对于该配置文件所在目录。委派提示中的绝对路径在运行时重新计算，不固化到入口配置。全局配置基线和历史恢复快照属于原始证据，保留其中的历史路径；第三方技能中的容器、系统工具路径按各自平台语义使用。

全局组件安装、私有规则覆盖、自动 push/cron 已禁用；领域 skills 可按上述流程安装到本工作区。任务看板需在本机单独配置；未配置时只维护本地状态。合并上游更新时应逐项检查是否重新引入全局行为，不能直接重置或强制覆盖本地适配。

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
../../bin/status running "正在验证"
../../bin/status done "验证完成"
```

从工作区根目录补同步全部任务：

```sh
./bin/board-sync --all
```

自动化测试使用替身 CLI，不连接真实飞书服务。目标表及 profile 必须在本机明确配置并授权；原工作区的配置和验收记录不会随代码迁入新项目。

## 许可

AgentHelm 采用 [MIT License](LICENSE)。所包含的上游代码的原始版权与完整许可见 [NOTICE](NOTICE)。
