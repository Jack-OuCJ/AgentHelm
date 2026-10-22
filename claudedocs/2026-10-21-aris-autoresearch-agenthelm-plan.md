# AgentHelm 自动研究流程改造方案

日期：2026-10-21。状态：设计提案，未实施。

## 1. 建议与范围

保留 AgentHelm 的 Dispatcher、Lead、Executor、领域 skill 路由和本地文件交接方式。借鉴 ARIS 的证据与审核契约、autoresearch 的受控实验循环，增加一个供现有角色调用的研究执行模块。

建议按三阶段交付：

1. **P0：自动生成运行证据，完成前校验证据完整性。**
2. **P1：把结论绑定到证据，落实独立复核与严格模式。**
3. **P2：增加有预算的持续优化循环，记录每次保留或放弃的理由。**

首版只做本机、串行、显式选择加入的计算实验。远端 GPU 调度、论文生成、研究知识图谱、常驻服务和自动 Git 提交不进入首版。它们不是这次解决证据遗漏问题的前提。

本方案中的命令、文件格式和改动清单均为拟议设计，不代表当前已存在的功能。预算数字和真实效果要在实施后的 pilot 中确定。

## 2. 调查依据与证据范围

### 2.1 固定的外部版本

| 项目 | 本次读取版本 | 重点读取 |
|---|---|---|
| ARIS | `6564cab43dd9df3dbab85e459af0202ff0830a35` | Agent Guide、assurance 契约、experiment-plan/bridge/audit、result-to-claim、实验队列实现、审核验证脚本及相关测试 |
| autoresearch | `228791fb499afffb54b46200aca536f79142f117` | README、program.md、prepare.py、train.py |

本次是官方源码静态调查。没有执行外部项目、训练模型、调用评审模型，也没有测量改造收益。没有完整审计 ARIS 全部宿主、桥接器与审核调用链。

### 2.2 AgentHelm 本地基线

分支：`feat-domain-skills`。HEAD：`dd119ff1e264726a48ccd9fd57a07cef7a36317f`。

工作区已有未提交修改，本方案以当前文件内容为准，不将 HEAD 当成所有现状的完整快照。本次只新增此方案文档，保留原有修改。

已确认的现状：

| 位置 | 已有能力 | 本次确认的缺口 |
|---|---|---|
| [任务卡](/Users/jack/Projects/AgentHelm/templates/task-card.md:45) | 目标、指标、基线、停止条件、可写文件与验收命令 | 冻结版本是 Markdown，程序不校验其完整性 |
| [实验规则](/Users/jack/Projects/AgentHelm/rules/research-workflow.md:9) | pilot、规模与预算、公平比较、真实结果日志 | 多数要求由 Lead 执行，尚无统一实验运行器 |
| [严格模式](/Users/jack/Projects/AgentHelm/rules-extra.md:3) | 多种子、评价脚本与 gold 哈希、留出集、负对照、独立复算 | 没有将这些要求接入完成状态的检查 |
| [run-executor](/Users/jack/Projects/AgentHelm/bin/run-executor:14) | 角色与模型选择、任务目录、规则提示、关闭 stdin | 只要求 brief 非空；不采集实验指标，不持久记录实验状态，也未给子进程设置 timeout |
| [status](/Users/jack/Projects/AgentHelm/bin/status:21) | 原子替换 STATUS，刷新看板与索引，尝试同步远端 | 写入 done 之前不检查验收；刷新派生视图与远端同步不是跨文件事务 |
| [kb lint](/Users/jack/Projects/AgentHelm/bin/kb:115) | 结果行 JSON 可解析，并存在 command/exit_code/artifact 字段 | 不检查类型、产物存在性、指标来源或是否符合实验协议 |
| [lead-reload](/Users/jack/Projects/AgentHelm/bin/lead-reload:14) | 恢复 STATUS、索引结论和任务记忆 | 不恢复尚未完成的实验、当前基线和剩余运行预算 |
| [工作区测试](/Users/jack/Projects/AgentHelm/tests/test_workspace.py:166) | 覆盖索引、结果字段和完成状态 | 现有 fixture 引用未创建的 log.txt 也能过 lint；没有覆盖证据验收 |

另外，[install-rules](/Users/jack/Projects/AgentHelm/bin/install-rules:9) 从模板生成研究规则；`rules/`、`rules-extra.md`、`experiments/` 等被 Git 忽略。实施时应改跟踪的模板和真实 skill 源文件，不能只改生成后的规则。

## 3. 从两个项目借什么，调整什么

### 3.1 ARIS：审核结果可检查，结论与数字分开判断

ARIS 的价值不只在于跨模型讨论，而在于明确交接产物和审核责任：

- experiment-plan 先明确要验证的主张、排除的替代解释与最小证据，再安排实验。
- result-to-claim 先检查引用的证据是否存在，再判断证据是否支持主张。数字存在不等于推论成立。
- assurance 把投入深度与审核强度分开，规定审核必须显式输出结果。
- 外部 verifier 检查审核 JSON、声明的输入哈希、trace 和审查独立性元数据；子审核记录结果，由汇总者决定是否阻止收尾。

来源：[experiment-plan](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/6564cab43dd9df3dbab85e459af0202ff0830a35/skills/experiment-plan/SKILL.md)、[result-to-claim](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/6564cab43dd9df3dbab85e459af0202ff0830a35/skills/result-to-claim/SKILL.md)、[assurance 契约](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/6564cab43dd9df3dbab85e459af0202ff0830a35/skills/shared-references/assurance-contract.md)、[verifier 实现](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/6564cab43dd9df3dbab85e459af0202ff0830a35/tools/verify_paper_audits.sh)。

对 AgentHelm 的调整：

1. 不搬入论文专用的五层审查和整套安装体系，先覆盖实验与选型结论。
2. 代码审查继续走 Matt code-review；实验完整性复核单独定义，不能替代代码审查。
3. 保留实际模型与上下文隔离的证据，不把 Claude/Codex 命令名当成模型家族。无法证明时记录 unknown，不声称已通过跨模型审核。
4. 不能只看 verifier 退出码：ARIS 的 provisional 也可能返回 0；必须读取结构化验收状态。
5. 必须由协议生成“应检查哪些输入”，再检查覆盖范围。ARIS 已读 verifier 重算的是审核产物自己列出的哈希；不能把这一点当成它自动证明了输入覆盖完整。

ARIS 的审核等级、WARN 与 provisional 规则有特定语义。本方案采用其“显式结果、输入绑定、统一汇总”的结构，不照搬所有通过条件。

两个实现细节也影响取舍：result-to-claim 的证据预检查在 helper 不可用时允许警告后继续；实验队列的 job_status_check 优先按 expected_output 是否存在判定 completed。前者不能被我们当作“所有检查必然已执行”，后者也不能替代退出状态、指标和本轮来源检查。因此借其产物契约，不整体移植调度器。[预检查实现约定](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/6564cab43dd9df3dbab85e459af0202ff0830a35/skills/result-to-claim/SKILL.md#L58)、[队列完成判断](https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/6564cab43dd9df3dbab85e459af0202ff0830a35/skills/experiment-queue/scripts/queue_manager.py#L266)

### 3.2 autoresearch：优化对象与评价协议分开

autoresearch 用一个轻量指令文件组织循环：建立基线、修改候选、运行、读取指标、记录成功或失败、保留或丢弃。允许修改的训练文件与固定的数据/评价文件明确分离。[program.md](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md)

代码把训练预算设为 300 秒，并在训练循环中累计稳定步骤耗时；启动、编译预热和最终评价不等于这 300 秒。整个进程的超时是另一层约束。[prepare.py](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/prepare.py#L30)、[train.py](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L538)

对 AgentHelm 的调整：

- 将“固定评价协议、先基线、失败也记录、逐次决定”落实为命令行为。
- 不采用无限循环；沿用 pilot 后确定的有限运行次数、时间和失败上限。
- 不自动 commit/reset；候选在任务专属目录保存，保留/放弃只改变选择记录。
- 不把崩溃的指标记成 0。失败指标为 null，并保留原因，避免最小化目标误选失败试验。
- 不根据一次验证集进步就宣布结论。搜索结果与最终确认分开，保留已有的独立样本、噪声分析和严格模式。
- “只读评价文件”先用执行前后哈希检查；这只能发现部分变更，不能替代进程隔离。指标的计算语义仍需检查。

## 4. 目标结构：一个研究模块，供现有角色调用

新增一个 CLI `bin/research`，内部逻辑集中在 `bin/_research.py`，复用 `_workspace.py` 的目录约束。先用标准库 JSON 与现有 unittest，不引入框架、数据库或新的模型后端。

Lead 仍负责协议、假设和结论；Executor 仍负责授权范围的实现与实验。`bin/research` 负责校验、执行计算命令、记录证据和生成检查报告，不负责创建 Agent。

任务内拟议布局：

```text
experiments/NNN-topic/
  README.md                  用户问题、授权、说明与最终结论，沿用现有格式
  STATUS                     沿用现有四种状态
  research.json              机器可读的研究协议，Lead 维护
  research.lock.json         冻结协议、评价输入清单和哈希，工具生成
  results.jsonl              每次实际运行一行，工具追加
  verification.json          可重新生成的检查报告，工具生成
  candidates/<candidate-id>/
    candidate.json           本方案的执行描述与源码清单，执行者准备
  runs/<run-id>/
    receipt.json             本次运行状态、命令、时间、来源和产物哈希
    inputs/                  本次声明的候选源码与配置快照
    stdout.log
    stderr.log
    metrics.json             约定评价命令的输出
  claims.json                P1：冻结的主张、适用条件与最低证据，Lead 维护
  audits/<audit-id>.json      P1：证据引用、主张判断与独立复核结果
  decisions.jsonl            P2：候选保留/放弃记录，工具追加
```

数据所有权：协议由 Lead 定义，运行记录由工具写入，复核由独立执行者产出，README 由 Lead 解释。`verification.json` 和看板都是派生视图，不新增第二套任务状态源。

### 4.1 不混用四种含义

| 含义 | 拟议取值 | 说明 |
|---|---|---|
| 任务状态 | running / needs-input / blocked / done | 保留现有 STATUS 和飞书映射 |
| 单次运行状态 | running / succeeded / failed / timeout / interrupted / invalid | 程序执行与产物是否有效 |
| 主张结论 | supported / refuted / inconclusive | 研究问题的证据结论，P1 引入 |
| 检查结果 | PASS / WARN / FAIL / BLOCKED / ERROR / NOT_APPLICABLE | 检查是否完成及发现什么；freshness 另记 current/stale |

`done` 不要求假设成立，也不要求指标提高。它要求任务按声明范围完成收尾，并准确披露证据与限制。预算耗尽、方法无效、没有显著差异均可以产生有效结论。

## 5. P0：协议、运行证据和完成检查

### 5.1 协议只放程序需要读取的字段

建议 `research.json` 首版包含以下字段组。README 不再重复维护一套机器字段；冻结时把协议摘要呈现给人看，用户原话与授权记录仍保留在 README。

| 字段组 | 必须表达的内容 |
|---|---|
| identity | schema_version、task_id、kind（reproduce/compare/optimize）、question |
| authorization | 已确认的可执行命令、可写候选目录、禁止改动的评价路径；引用授权记录位置 |
| candidates | baseline_id、候选根目录、允许的执行接口与改动范围；各 candidate.json 提供具体 argv 与源码/配置清单 |
| evaluation | evaluator argv、数据版本或内容清单、split、预处理、指标名称/方向/单位、有效输出规则 |
| comparison | 资源条件、每次工作负载预算、样本或种子方案、可比较条件；baseline 引用 candidates.baseline_id |
| budget | max_runs、每次完整进程超时、累计运行时间上限、允许的重试；由 pilot 确定 |
| evidence | 需保存的日志、预测或其他原始产物、候选输入文件清单 |
| assurance | exploratory / strict；与运行规模独立 |

模板不能用虚构样本量、预算或阈值充当默认值。未确定项写 null；正式 freeze 时缺少必填字段就报错。P0 的 pilot 沿用现有流程，在 pilot/ 内使用单独的有限预算并保存证据；正式运行器在 pilot 后启用，不把 pilot 数据计入正式比较，也不追认它为运行器自动采集的记录。任务总预算需同时披露 pilot 与正式运行，不能隐藏 pilot 开销。

`freeze` 在 pilot 与授权完成后生成锁文件：保存规范化协议、完整输入清单、评价与数据清单哈希及比较条件。运行器从锁文件读取，不接受绕过协议的任意命令参数。

首版不在已有正式运行的协议上原地换评价器、数据或指标。需要改变时新建关联任务，并标明替代关系；避免一开始引入复杂的多版本协议管理。

候选是协议允许变化的研究对象。新增 candidate.json 无需改冻结协议，但必须通过其路径、命令和文件范围检查；首次运行时将描述与输入一起归档。这样后续优化能增加候选，同时保持评价条件不变。

### 5.2 命令契约

以下为拟议接口，当前不可执行：

```text
bin/research freeze <task-dir>
bin/research run <task-dir> --candidate <id> --phase <baseline|search|confirm> --key <request-key> [--seed <seed>]
bin/research recover <task-dir> --run <run-id>
bin/research verify <task-dir> [--check]
bin/research show <task-dir>
```

- **freeze**：检查协议与授权字段，生成锁文件。已有结果时拒绝覆盖。授权字段是执行前提，不会给命令增加用户未授予的权限。
- **run**：执行已登记候选与评价命令，记录来源和结果；拒绝未登记候选、协议漂移、预算不足和同任务并发。同一个 request-key 只返回已有 receipt，不重新运行；相同键携带不同参数则报错。重试或有意重复测量必须用新键，分配新的 run_id，单独消耗预算。
- **recover**：核对异常退出留下的 running receipt。只有确认原运行已结束才能记为 interrupted；无法判断则保持 BLOCKED，不把 PID 或日志时间当成充分存活证据。
- **verify**：重新计算结构、来源和哈希检查，生成报告；`--check` 只读、不启动模型、不运行实验、不写报告。
- **show**：只读展示预算、基线、有效/失败运行、未收尾记录及当前检查范围，供恢复提示使用。

退出码建议：0 表示本命令完成且满足它声明的条件，1 表示实验/验收未满足，2 表示参数或协议错误。消费者还必须读取 JSON 的检查范围与 verdict；不能把 0 翻译为“科研主张已证实”。

候选可由 Executor 事先准备在任务内的独占目录。run 不复制整个源码库、不自动建分支或 worktree，也不安装依赖。首版要求计算工作目录与持久产物在本工作区；外部数据只读来源由协议显式声明。

评价命令统一输出 metrics.json：`schema_version`、`metrics`（指标名称到有限数值）、`sample_count`、`seed`、`split`、`data_id`。指标名称、单位和元数据必须与协议匹配。输出路径由运行器分配；argv 只支持预定义的 run_dir、metrics_path、seed 参数替换，不执行任意模板表达式。任务特有的指标计算仍由其评价脚本负责。

### 5.3 自动留证据的顺序

1. 获取同任务独占锁，核对协议、预算、候选输入与评价输入。
2. 分配不可复用的 run_id；原子写 running receipt，建立独占日志与输出目录，保存声明的候选源码和配置快照。候选一旦运行就不原地改写，下一方案另建 candidate；基线证据引用归档快照，不因新候选正常修改而失效。
3. 以 argv 数组执行工作负载及评价命令，不启用 shell 字符串求值。完整进程超时包含启动和评价，工作负载自身预算另记。
4. 超时或取消时终止自己启动的进程组，收集已知退出信息。首版明确支持 macOS/Linux；不声称已实现 Windows 进程树管理。
5. 分别记录工作负载与评价的退出码；只有两者成功且产物有效才能记录有效指标。检查必需产物、JSON 类型、有限数值、样本/种子与指标元数据；评价指标不能由 Agent 手抄日志得到。
6. 重算冻结输入与候选输入哈希，检查执行期间变化；生成终态 receipt 并记录每个原始产物的哈希。
7. 按 run_id 幂等投影到 results.jsonl。恢复时补齐 receipt 已终态但日志投影缺失的记录，禁止重复计数。

receipt 是每次运行的权威记录，results.jsonl 是兼容现有工具的追加投影。写锁、临时文件加原子替换、fsync 与恢复流程集中在同一模块，避免各入口分别实现。

结果 v2 保留现有 `command`、`exit_code`、`artifact`，增加 run_id、phase、candidate、seed、argv、cwd、协议与比较标识、输入哈希、状态、指标、耗时与产物哈希。command 是人读的显示字符串，实际执行以 argv 为准。

未知退出码用 null，失败或无法验证的指标用 null。失败、超时和重试都消耗实际预算，不能只统计成功运行；每轮超时上限取单次上限与剩余累计运行预算的较小值。计费无法由已有 CLI 提供时写 unknown；首版不得承诺精确限制全部 LLM 费用。

冻结输入清单要覆盖评价代码、预处理、指标配置、数据版本和切分。外部大数据用不可变版本与清单；无法证明一致时不得标为严格可比较。只记录 Git SHA 不足以描述脏工作区，需同时记录声明的源码文件哈希。

### 5.4 完成状态如何接入

采用 `new-task --research` 显式创建研究任务；任务 README 的机器标记与 research.json 双向校验，避免仅因配置文件意外丢失就退回普通任务。既有普通任务保留原行为；手工修改标记不视为受控迁移。

对研究任务，`bin/status done` 必须在写 STATUS **之前**调用同一个只读 verify 逻辑：

- 协议与锁匹配；所有已启动运行有终态且已入账。
- 声称有效的结果确有产物，指标与来源对应；失败运行没有进入有效聚合。
- 没有被引用的过期证据、缺失产物或无法解释的协议漂移。
- P0 只发出 `evidence-checked`，明确标注“研究推论尚未独立复核”。strict 研究任务在 P1 就绪前返回 BLOCKED，不降级通过。

检查失败时，STATUS、索引、看板及远端调用均不发生。通过后沿用已有本地更新与远端失败待同步行为。研究检查本身不依赖飞书可用性。

已有 done 后文件再变，不自动联网改状态；kb lint、research show 与下一次同步前检查应显示 stale。对研究任务，board-sync 补同步前复用同一检查，避免将已过期结论重新发布为当前有效。

kb index 对研究结论附带 legacy/provisional/evidence-checked/reviewed/stale 标签；普通结论格式保留。Lead 恢复与知识复用时必须看到标签，不能因为结论已写进 README 就当作验收通过。P0 不生成 reviewed 标签。

## 6. P1：结论与证据、独立复核和严格模式

### 6.1 先记录主张，再判断支持程度

正式 freeze 前建立 claims.json，给主张稳定 ID。每条包含 statement、适用条件、需排除的替代解释和最低证据要求，并纳入锁文件。不能看过正式结果再悄悄改初始主张；新发现可以标为事后探索，或建立新协议。

运行后的支持/反对证据引用、outcome、局限与复核结论写入关联 claim_id 的审核产物，由 verification.json 汇总。这样不需要为了更新结论而改写冻结的主张文件。

证据引用必须精确到 run_id、产物路径、metric_key 或样本输出；聚合值必须记录输入 run_id 集合和计算方法。不能用“某日志里出现过这个数字”作为匹配规则。

典型区分：

| 层次 | 示例 | 由谁检查 |
|---|---|---|
| 记录真实且可追溯 | 某次运行的 latency_p50 来自指定 metrics.json | 工具重算来源与哈希 |
| 统计比较可成立 | 同一数据、资源与测量方法下，差异超过噪声 | 固定分析脚本与独立复算 |
| 推论范围合理 | 能否从单场景推到所有用户或所有任务 | Lead 与独立证据复核 |

工具不能仅凭文件和数字一致就给最后一层 PASS。探索性结论可以保留 provisional；严格主张缺少所需复核时不得宣称已验证。

### 6.2 最少的审核机制

每个需要的审核都写 JSON，使用前述六种 verdict。NOT_APPLICABLE 必须解释为什么不适用；缺依赖是 BLOCKED，执行失败是 ERROR。freshness 与 verdict 分开。

审核产物记录实际检查范围、输入清单、输入哈希、复算命令/输出、问题与理由。模型复核另记 requested_model、实际可证明的模型、来源证据、上下文隔离情况与原始回复路径。身份不明就写 unknown。

verify 从协议推导必需审核及输入集合，检查审核的输入覆盖，而非完全相信审核者自报的列表。改了结果、主张或被检查的源码后，对应审核自动 stale。

先落实已有严格模式的独立复算与反证要求，不默认接入 ARIS 的 MCP，也不强行指定跨模型后端。若某任务明确要求跨家族审查，身份无法证明时该项 BLOCKED。不同模型的赞同本身仍不是科研正确性的证明。

### 6.3 严格模式的可检查部分

- 按任务适用性检查样本/种子覆盖、固定评价器、留出数据使用记录、负对照和独立复算产物。
- 统计分析与具体方法仍由相应领域 skill 指导，不把固定样本量或任意阈值写进通用运行器。
- 留出集不提供给迭代候选，只由最终评价步骤消费；P1 第一版若仅记录“未使用”的自报，不能称为强隔离，必须显式披露。
- FAIL、BLOCKED、ERROR、stale、缺必需审核均阻止严格验收；WARN 只有事先定义为非关键的问题才可通过，并在结论列出。不得由执行者临时调低等级来过关。
- 负结果与 inconclusive 可以验收通过，前提是过程和结论真实、有限范围已完成、没有将不满足的条件包装成正面主张。全部运行失败也可报告可追溯的“未能完成实验”，不能伪造比较数值。

## 7. P2：有预算的优化循环

适用范围：有可信指标、有限可改范围、可重跑评价的优化任务。文献综述、开放构思、没有稳定评价器的任务不强套这一循环。

新增 playbook，由 Lead 在已授权预算内执行；不新增常驻调度器：

1. 确定可重复的工作负载、主指标、护栏和噪声阈值，固定评价协议。
2. 运行 baseline，完成适配器与评价敏感性检查。
3. 提出一条有机制解释的假设，给 Executor 独立候选目录和明确范围。
4. 用 research run 留下完整结果，执行护栏检查。
5. 用拟议 `research decide <task-dir> --runs <id,...> --decision keep|discard --reason <text>` 记录决定。工具先检查候选及重复测量覆盖、可比较条件、最低改善要求和护栏，拒绝非法 keep；Lead 负责科学与复杂度判断。
6. 保留只更新最佳候选指针，不移动、覆盖或 reset 用户代码。discard 不删除原始证据。
7. 在运行次数、时间或失败上限到达时停止。没有进步也是结果，不能临时换指标。
8. 最佳搜索候选用未参与搜索的确认样本验证，再形成最终结论。

确认前锁定候选、数据和整批重复测量计划。严格模式将留出集使用记为不可撤销事件，不根据中间确认结果更换候选。确认失败后，不得继续用同一留出集调参再声称独立确认；需保留失败记录，并重新设计获授权的验证。

decisions.jsonl 记录 hypothesis、parent_candidate、run_ids、before/after、guardrails、decision、reason。保留原始 baseline 和当前 best 两个标识，防止只报告相对最近候选的改善。

比较指纹至少覆盖评价/数据/预处理/指标、切分、工作负载预算口径和资源条件。候选源码不同是研究变量，不能因此一律判不可比较；评价条件不同则必须分组。

确认失败时保留搜索结果，但撤销“已验证改善”的标签。持续窥看验证集产生的选择偏差要在报告中说明。单次数字略好只能算待确认候选。

## 8. 改动文件与交付顺序

| 阶段 | 拟修改/新增文件 | 具体责任 |
|---|---|---|
| P0 | 新增 bin/research、bin/_research.py | 协议、执行、证据、锁、恢复、统一检查 |
| P0 | 新增 templates/research-task.json；修改 templates/task-card.md、bin/new-task | 显式研究标记、协议模板、原有命令兼容 |
| P0 | 修改 bin/status、bin/kb、bin/lead-reload | 完成前检查、v1/v2 日志校验、恢复摘要 |
| P0 | 修改 bin/board-sync | 研究任务补同步前检查证据仍有效，不改远端字段或企业选择 |
| P0 | 修改 templates/research-AGENTS.md、templates/research-extra.md、现有角色 references | 将运行、冻结、恢复与检查方式写入唯一规则位置 |
| P0 | 修改 tests/test_workspace.py、tests/test_feishu_board.py、tests/test_portability.py；新增 tests/test_research.py | 黑盒验收、兼容与失败路径；stub 外部服务 |
| P1 | 新增 claims 模板；扩展 _research.py、test_research.py、严格模式模板 | 证据引用、审核覆盖与新鲜度、独立复算 |
| P2 | 新增 skills/agenthelm-workflow/references/optimize.md；扩展 research CLI 和测试 | 有界循环、选择记录与最终确认 |
| 各阶段 | README.md、相关部署/自检覆盖 | 更新使用说明，确认新文件可随 checkout 移动与部署 |

`bin/run-executor` 第一阶段不重构成调度框架。它的授权提示保留，Executor 按 brief 调用 research run。后续若需要限制模型执行者自身耗时，再单独增加 timeout；计算运行超时不能冒充完整 Agent 成本上限。

不新增共享全局 skills，不更换模型配置，不改变 code-review 路由。文档与 skill 的实施修改应遵循用户既有配置规则；生成规则通过既有部署链更新。

### 兼容策略

1. 普通任务无研究标记，继续现有行为。旧 results.jsonl 按 v1 读取，不能补标成 v2 已验证。
2. 旧任务选择迁移时先生成协议；历史运行记录作为 legacy 证据导入，缺少的 provenance 记为 unknown，不回填成已执行的检查。
3. `new-task --important` 现有 Lead 选择语义保留；与 --research 同用时建议模板选择 strict，并显式显示。不能在功能未就绪时自动降级。
4. STATUS 保持四种状态和现有分隔格式，飞书不新增字段；验证范围放在现有说明/结论中。
5. 规则源更新 templates，部署测试核对生成文件。已有未提交修改需在实施前重新检查并合并，不能覆盖。
6. 读取和持久化路径优先任务/工作区相对路径；外部数据用声明的 source ID 配置解析，不把当前机器绝对路径固化到可迁移协议。

## 9. 必须通过的验收用例

所有工程验收先用本地确定性小程序与 CLI 替身；不为验证工作流启动真实模型、GPU 或飞书写入。

| 用例 | 必须观察到的行为 |
|---|---|
| 正常基线与候选运行 | 自动生成日志、receipt、指标与结果行，来源完整，重复调用不重复计数 |
| exit 0 但无指标文件 | invalid，不能进入有效聚合，也不能因为有日志就通过 |
| 指标类型错误/NaN/Infinity | invalid；不接受 Python JSON 默认允许的非有限浮点数 |
| 失败却留下旧的 metrics.json | 独占 run 目录及产物来源检查阻止旧文件被当成本次成功 |
| 评价脚本/数据清单在运行前或运行中变化 | 拒绝启动或标记 invalid；不能沿用原比较组 |
| 当前源码脏但文件清单完整 | 记录内容哈希；不强制提交，也不只记 HEAD |
| 超时、取消与进程后代 | 本轮进程组被收尾，失败计入预算，指标不伪造 |
| receipt 终态后控制器崩溃 | 恢复只补一次 results 投影，不重复执行实验 |
| 控制器被 SIGKILL、无法确认原进程 | 不自动报成功、不盲目重跑；recover 给出明确状态或 BLOCKED |
| 同任务并发/部分 JSONL 尾行 | 不损坏台账；损坏证据显式报错，不静默跳过 |
| 达到运行或时间预算 | 拒绝下一轮；失败与重试都计入；未知费用明确显示 |
| done 前检查失败 | STATUS、看板、索引和远端调用记录均不变化 |
| 本地检查通过、远端离线 | 保留本地完成与待同步标记，沿用现有故障语义 |
| done 后结果被改，随后补同步 | 检出 stale，不把旧验证结论当成当前证据重新发布 |
| 旧普通任务与 v1 结果 | 现有行为通过，历史数据不被虚构升级 |
| P1：引用错 run/metric、选择性漏掉必需输入 | 明确失败；单纯出现相同数字不能通过 |
| P1：审核输入变化或复核不可用 | stale/BLOCKED，不能当成 NOT_APPLICABLE |
| P1：有充分证据的负结果 | 可以完成，结论为 refuted/inconclusive，非 supported |
| P2：指标更好但护栏失败/协议不同 | 拒绝 keep；记录放弃理由 |
| P2：确认样本没有复现搜索改善 | 保留记录，撤销已验证改善标签 |
| 工作区移动与全局配置 | 新根目录正确解析；既有 HOME 配置快照保持一致 |

拟议工程检查命令：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`，以及现有 smoke、自检和 kb lint。测试范围随各阶段实现补齐；本次未运行这些测试。

工程检查通过后，再用当前流程与改进流程做有限 pilot，固定任务、模型、资源与评价条件。比较：证据缺失、错误完成、异常恢复是否成功，以及额外时间/调用成本。先确定要识别的差距再决定样本量，不预先宣称成功率提升。

## 10. 实施时需要保持的判断边界

- 本地文件和哈希用于可追溯与新鲜度检查，不是对恶意代码的安全隔离或不可伪造证明。
- 自报指标、匹配的数字、绿色测试、不同模型赞同，分别只能证明它们实际覆盖的范围。
- 首版没有 GPU 队列、远端后端或精确计费能力，不承诺这些能力。
- 发现 evaluator 语义错误时，保留旧记录、撤回相关结论，建立新协议；不静默修改评价器后混用结果。
- 原始证据保留策略优先满足复算。清理时可删下载数据和缓存，不删除被 claims/audits 引用且无法重建的预测与检查输出。

推荐先完成 P0 的一个端到端切片：创建研究任务、冻结、基线、候选、失败、恢复、verify、done 拒绝/通过、离线待同步。这个切片跑通后进入 P1，再根据实际优化任务决定是否做 P2。
