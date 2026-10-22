# App 原生能力核查

日期：2026-10-22。范围：当前 Codex Desktop 聊天可见工具；未创建额外用户聊天、未发送跨聊天消息、未更改任何模型或全局配置。

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

只读提取全局配置顶层 model/model_reasoning_effort 得到相同值；这是配置证据，不足以单独证明目标 App 新会话采用该默认，也不能替代子代理实际轮次证据。后续适配应提供按精确会话 ID 输出白名单字段的读取入口，并对来源不匹配、无轮次、重复记录、截断日志和缺字段明确报错。

## CCD

当前 Codex 聊天未提供 CCD 会话工具。设计记录的 CCD 调查报告说明 start_session 未开放，不能据此证明可自动创建 Lead。CCD 的创建、默认模型、有效模型及强度读取均需在 CCD 宿主内重新核查；本轮不得标为接通。

## 验收记录约定

宿主执行者必须保存工具名、请求标识、原生返回会话标识与状态、工作区关联、任务目录实际执行证据、有效模型和强度证据。准备提示、工具参数、排队 ID、会话空闲以及离线测试均不能替代真实执行和验收。
