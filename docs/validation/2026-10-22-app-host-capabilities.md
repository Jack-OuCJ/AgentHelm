# App 原生能力核查

日期：2026-10-22。范围：当前 Codex Desktop 工具核查、本机运行证据 helper 及隔离离线测试。未创建额外用户 Lead 聊天、未发送跨聊天任务；实现工作流中的原生 Executor 用于授权代码开发，不能替代独立 Lead 端到端验收。未更改全局模型或配置。

## Codex Desktop

| 能力 | 当前证据 | 结论 |
|---|---|---|
| 关联工作区项目 | list_projects 实际返回 AgentHelm 项目，路径匹配当前根目录，local，Git 仓库 | 已实测读取 |
| 列出可见独立聊天 | list_threads 实际返回当前聊天及同工作区其他聊天，含会话 ID、cwd、状态 | 已实测读取 |
| 读取聊天 | read_thread 实际返回当前聊天标题、cwd、状态及消息 | 已实测读取 |
| 创建独立聊天并首次执行 | create_thread 工具存在，支持 project/local、prompt、model、thinking；可能返回排队标识 | 接口存在，未实测创建 |
| 追加任务 | send_message_to_thread 工具存在；省略 model/thinking 保留当前设置 | 接口存在，未发送 |
| 等待完成或需输入 | wait_threads 工具存在，支持 afterCursor；新用户输入提前唤醒 | 接口存在，未实测其他 Lead |
| 配置模型及强度 | create_thread、send_message_to_thread 参数支持；只可用宿主声明的模型组合 | 接口存在，未验证生效 |
| 查询新会话默认模型与强度 | 当前公开工具中未发现专用查询能力 | 能力未确认 |
| 读取独立聊天实际模型与强度 | list_threads/read_thread 当前实测返回不含对应字段；随后精确定位当前聊天本机 rollout，session_meta 确认 Codex Desktop 与会话 ID，最新 turn_context 含 model/effort | 公开工具缺字段；本机运行记录可只读验证本地会话，仍需校验 ID、来源、目录与轮次 |
| 原生 Executor | 当前宿主提供 collaboration 子代理工具；子代理与独立用户聊天是不同边界 | 工具可用；不能冒充独立 Lead |

结论：当前宿主具备创建、读取、等待、追加和模型输入的工具边界，但尚未完成 AH 原生创建闭环。本机运行记录可以补充实际参数证据；App 默认值的完整配置优先级仍需核验。项目必须在无法取得证据处明确报错或保留待验证状态，不能伪造成功。

### 本机记录补充核查

仅匹配当前聊天精确 ID 的 rollout 文件，提取 session_meta 的 id/cwd/originator/source/cli_version，以及最新 turn_context 的 turn_id/cwd/model/effort。实测来源为 Codex Desktop，客户端版本 0.163.0-alpha.10.2，当前轮实际 model=gpt-6.1-sol、effort=high。未读取或输出消息正文、工具参数、其他聊天内容及凭据。

只读提取全局配置顶层 model/model_reasoning_effort 得到相同值；这是配置证据，不足以单独证明目标 App 新会话采用该默认，也不能替代子代理实际轮次证据。已实现 `bin/codex-session-evidence`，按精确会话 ID 和当前轮次输出白名单字段。来源不匹配、无轮次、歧义记录、截断日志、缺字段或目录越界均明确报错；完整行为由隔离 `tests/test_codex_evidence.py` 验证。

### 实现及验收边界

- helper 已在本轮真实 Desktop 会话与原生 Executor 上进行只读核查。独立 Lead 使用 `--session ID --turn TURN_ID`；Executor 另用 `--kind executor --parent-session LEAD_ID`，必须从精确子代理 ID 的原生 `read_thread` 独立取得当前 turn，防止将 fork 父历史当成自身运行。
- 输出只包括会话/轮次、runtime cwd、model/effort、来源及快照定位。runtime cwd 可以为工作区根；created 回执的任务 cwd 则必须来自 workdir=任务目录的真实任务动作及实际 stdout。helper 不证明 visible、executed，也不证明默认模型来源。
- 宿主操作步骤已收敛到 [App 宿主协议](../../skills/agenthelm-workflow/references/app-host.md)。创建、读取、等待、追加、交接和完成均保留请求与观察证据；未决结果阻止盲目重试。
- 尚未验收：Codex 原生 create_thread 创建独立可见 Lead、首个任务动作、实际角色模型/强度、读取/等待与人工介入后的追加、完整回执闭环。只读参数核查与离线替身均不关闭这些项目。
- 仍有缺口：目标 App 新会话默认模型及所选模型默认强度的可靠完整取源。角色显式 model/effort 可以避免默认解析，但不能省略实际参数验证。

## CCD

当前 Codex 聊天未提供 CCD 会话工具。设计记录的 CCD 调查报告说明 start_session 未开放，不能据此证明可自动创建 Lead。CCD 的创建、默认模型、有效模型及强度读取均需在 CCD 宿主内重新核查；本轮不得标为接通。

## 验收记录约定

宿主执行者必须保存工具名、请求标识、原生返回会话标识与状态、工作区关联、任务目录实际执行证据、有效模型和强度证据。准备提示、工具参数、排队 ID、会话空闲以及离线测试均不能替代真实执行和验收。
