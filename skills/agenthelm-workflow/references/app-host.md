# App 宿主执行协议

适用 `app.codex` 与 `app.ccd`。项目 CLI 管理本地绑定和请求，当前聊天中的智能体调用原生工具；Python 不会调用聊天内工具。先确认用户已授权创建独立 Lead、委派或追加任务，并遵守宿主对独立聊天、跨聊天消息和子代理的限制。本规则不增加用户权限。

## 1. 核对当前身份与能力

- 从当前宿主原生会话信息取得真实会话 ID、入口和工作区；不从工作区路径、`.agenthelm/config/role` 或父提示猜身份。Codex 读取精确 ID 的 `read_thread`，并用 `list_projects` 核对项目根目录等于当前工作区。用户指定的当前主控经核对后运行 `bin/dispatch --entry app.codex --session ID`；CCD 使用 `app.ccd`。`--print` 仅只读预览，不注册。已有主控时按下文交接，不抢占。
- 有效 Dispatcher 用 `bin/app-session show --session ID` 核对当前归属。已绑定 Lead 用 `bin/lead-reload ABS_TASK --session OWN_ID` 核对自身 session、entry、role 与任务；此命令不会授予 Dispatcher 权限。角色模型通过 `bin/models resolve ROLE --entry ENTRY` 解析；请求参数与实际生效值分别记录。
- 能力登记由有效 Dispatcher 完成：查看当前宿主工具定义后，向 `bin/app-session capabilities --session DISPATCHER_ID` 提交 JSON：`entry`、总 `source`、逐项 `capabilities`。每项含 `available` 和自己的 `source`；创建需 create/read/wait/followup/model/effort，Executor 另需 native_executor。verify_model 作为事后取证能力单独登记，缺失不阻塞创建或执行。`model.values` 列当前可用模型，`effort.combinations` 按模型列合法强度，提供运行取证时，`verify_model.fields` 列出可观察的 model、effort。Lead/Executor 仍须核对本次宿主工具；缺口报告父会话，不冒用主控 ID 登记。工具存在与真实端到端验收分别记录。
- `default`/null 需要目标 App 新会话默认值的可靠来源。先确定最终所选 model，再取得该 model 的原生默认 effort；角色显式 model、effort=default 时，不能套用 App 默认模型或 Dispatcher 当前模型的 effort。配置文件顶层值、父会话实际值和参数回显都不足以单独证明默认选择。无可靠来源即报告 capability gap，保持未创建；用户已配置显式角色 model/effort 时按显式值执行。
- 宿主未开放原生独立会话创建工具时将 create 标为 unavailable，明确停止自动创建；深链接、手工粘贴与 CLI 不能冒充原生创建成功。CCD 的创建流程见第 5 节。

### 身份绑定与运行取证

Lead 的身份绑定只确认原生 session、workspace、task cwd、可见性与独立性。父会话用 `evidence_level="identity"`、`runtime_verified=false` 提交 created 回执；不需要首轮动作、turn ID、prompt ID 或模型运行证据。请求 model/effort 保存为 requested，不冒充 configured 或 actual。绑定完成即可执行、委派和接受后续任务；运行取证通过 read 单独补录，不作为启动前置。

原生 Executor 收到授权委派后，按 request.prompt 的 entry、task、role 和文件边界直接完成任务、运行验收并回报结果。执行期间无需自身本地绑定，不运行 lead-reload，不发送启动握手，也不等待 created 回执。父会话在完成后先提交 executor result 的 status=completed 回执，再按需补交运行核验回执。证据缺失或不匹配时如实报告核验限制，不要求子代理为绑定重跑任务。未绑定 Executor 的委派不授予 Dispatcher 身份或下层委派权限；其他未知会话仍不能自认主控。

identity 回执示例：

```json
{
  "request_id": "CREATE_REQUEST_ID", "owner_epoch": 1, "entry": "app.codex",
  "status": "created", "evidence_level": "identity", "runtime_verified": false,
  "session": "NATIVE_SESSION_ID", "workspace": "/absolute/workspace",
  "cwd": "/absolute/workspace/experiments/009-task", "visible": true, "independent": true,
  "evidence": {
    "session": "native exact session ID", "workspace": "native workspace metadata",
    "cwd": "native task directory metadata", "visible": "native visible session listing",
    "independent": "native independent session creation"
  }
}
```

该回执适用于两个 App 的 Lead create，不适用于 Executor；不带 model、effort、configured、actual 或 served_model。排队或未知创建结果保留原请求，确认真实会话后补交身份回执，不重复创建。

## 2. 准备一次操作

`app-session` 默认返回对应请求或绑定；register/release/claim 返回归属摘要。需要操作后的完整状态时加 `--full`（仅当前 Dispatcher 可读；release 在释放前核验身份），只读全量查询用 `show`。

在工作区运行 `bin/app-session prepare --session ID --operation create|executor|read|wait|followup --task ABS_TASK`，stdin 提供该操作 JSON。新任务与已有任务可分别用 `bin/new-task SLUG --session ID --app-params JSON < card.md`、`bin/spawn-lead ABS_TASK --session ID --app-params JSON` 取得 create 请求；两者自身不创建 App 聊天。

create/read/wait/followup 由有效 Dispatcher 准备，executor 由已绑定 Lead 准备；Executor 执行授权委派并向父会话报告证据。

- create 的参数可含 important；需要原生默认的字段须有 `defaults: {model, effort, source, evidence}`。证据属于目标 App 和所选模型。任务卡必须明确目标、可写范围、输出与验收要求。
- `run-executor --print` 返回 preview=true、executable=false，无请求 ID；只读预览不能调用宿主或提交回执。正式 executor 的参数为 role、brief 及必要 defaults。使用已绑定 Lead 的 session；`bin/run-executor ABS_TASK --session LEAD_ID --role hard --app-params JSON < brief.txt` 会附加完整工作区与角色入口。brief 明确可写文件和验收命令。
- read/wait 使用 `{}`；followup 使用 brief、observation、revision、cursor，关联发送前新完成的一次 read 观察。
- 保存输出 request 的 id、owner_epoch、entry、workspace、task、caller_session 与完整 prompt。宿主只执行该 request 声明的操作。未决 create 保留占位；先读取待处理请求，不重复准备另一个创建。

## 3. Codex 创建独立 Lead

1. 核对请求归属和用户授权；从 list_projects 选路径精确等于 request.workspace 的本地项目。调用 create_thread，target 为该 project 的 local 环境，prompt 使用 request.prompt，model/thinking 使用 request.effective_request。Lead 直接执行正式任务，不安排独立握手轮。
2. clientThreadId 只表示排队，不能填作最终 session。排队或网络结果未知时回写 queued/unknown，保留原请求和占位；查询原操作恢复，不重复 create。只有宿主明确确认未创建，才用 failed、created=false 释放占位。
3. 拿到真实 threadId 后，用原生返回、list_threads 与精确 ID 的 read_thread 核对独立、可见、同工作区和任务目录。cwd 可来自宿主 metadata；创建时指定的参数本身不作独立观察证据。会话不能是 Dispatcher，也不能已绑定其他任务。提交第 1 节 identity 回执即可绑定，无需等待任务动作或模型运行证据。
4. Lead 在身份绑定尚未完成时可按已授权 create request 执行任务；需使用本地委派功能时，先由父会话完成身份绑定，不以运行取证代替身份绑定。绑定后用自身 session 的 lead-reload 恢复。
5. 按需取证：从该精确 threadId 的原生 read_thread 独立取得实际 turn ID，再运行 `bin/codex-session-evidence --session THREAD_ID --turn TURN_ID --workspace ABS_WORKSPACE`。用 read result 的 actual、runtime_verified=true 与 model/effort evidence 记录实际值。证据不足时保持 runtime_verified=false，正常执行不等待取证。

## 4. Codex 原生 Executor

使用 request.caller_session 对应 Lead 的原生 collaboration.spawn_agent 或当前宿主等价能力。委派完整 request.prompt，明确角色、绝对任务目录、可写范围、验收命令、禁止全局配置修改和不再向下委派。需要独立指定模型时使用当前工具允许的无历史 fork 方式与 request.effective_request。

Executor 在任务 workdir 完成整个 brief 和验收后回报结果，不做启动握手，不等待自身本地绑定。完成后由 Lead 从精确子代理 ID 的原生 read_thread 取得该子代理实际 turn ID，再运行：

```sh
bin/codex-session-evidence --session EXECUTOR_ID --kind executor \
  --parent-session LEAD_ID --turn EXECUTOR_TURN_ID --workspace ABS_WORKSPACE
```

父会话先按原生结果核对 session、workspace、cwd、native、parent_session 与任务完成，提交 status=completed、executed=true、runtime_verified=false 及这些字段和 completed 的 evidence；不带 model、effort、actual 或 served_model。完成回执解除未决执行门槛，不建立已验模型绑定。随后可向同一 request 补交 executor created 回执（此时表示事后运行核验登记），含 executed=true、native=true、parent_session=LEAD_ID 及各字段证据。父历史不能作为子代理运行证据；helper 不证明任务验收。缺少模型证据时报告限制，请求保持 completed，仍可继续追加、结束或交接任务；不要求子代理重跑。执行是否完成仍必须由父会话确认，尚未完成的请求仍阻止结束或交接。

## 5. CCD 创建 Lead、模型与原生 Executor

- Dispatcher 的模型由用户在 CCD 中用 `/model` 手动选择，不读 roles.toml。
- 创建 Lead 按以下顺序完成，不发送独立握手轮：
  1. `start_session`（initiation=user_asked、context=fresh、cwd=request.task、use_worktree=false）发占位轮：只回复一行，不调用工具。start_session 的 model 参数或 preset 不作为最终设置证据。
  2. 对真实 session 调用 `set_session_model` 与 `set_session_effort`，设为 request.effective_request，再用 `get_session` 读回。会话不能改自己的模型。
  3. 原生信息确认 session 真实、可见、独立，workspace=request.workspace、cwd=request.task。cwd 可来自宿主 metadata，不要求占位轮执行 pwd。向原 create request 提交 identity 回执；有设置读回时也可使用下方 settings 回执。设置读回或运行证据缺失不阻塞身份绑定与正式派发。
  4. 等占位轮结束，用第 6 节 read prepare/result 读取该 session 的最新上下文，以 followup.brief=request.prompt 准备正式任务；发送前复核上下文和可观察的设置，用 `SendMessage` 发送，按 followup 协议回写。Lead 收到后直接核验自身绑定并执行任务。
- 只有 `app.ccd` 的 `create` 可显式选择 `evidence_level="settings"`。`model`/`effort` 是 get_session 的设置读回，必须精确匹配 effective_request；必填 `executed=false`、`runtime_verified=false`。每个身份、目录、可见性和设置字段须有独立 evidence；不得填 actual 或 served_model。示例（所有占位均替换为本次真实值与证据定位）：

```json
{
  "request_id": "CREATE_REQUEST_ID", "owner_epoch": 1, "entry": "app.ccd",
  "status": "created", "evidence_level": "settings", "session": "LOCAL_SESSION_ID",
  "workspace": "/absolute/workspace", "cwd": "/absolute/workspace/experiments/009-task",
  "visible": true, "independent": true, "executed": false, "runtime_verified": false,
  "model": "EXACT_MODEL_ID", "effort": "high",
  "evidence": {
    "session": "get_session: exact session ID", "workspace": "get_session: workspace metadata",
    "cwd": "get_session: task directory metadata", "visible": "native session listing: visible entry",
    "independent": "native creation/readback: independent session, not Dispatcher or subagent",
    "model": "get_session after set_session_model: model", "effort": "get_session after set_session_effort: effort"
  }
}
```

- 成功后 request=succeeded、task.state=running 仅表示绑定可用，不证明正式任务已执行；任务 STATUS 仍独立维护。session/task 保存 `configured={model, effort}`、`evidence_level=settings`、`runtime_verified=false`，不生成 `actual`。跟踪与继承使用所选 configured 设置，不将其宣称为运行验证。
- 已有 queued/unknown create：先核对原请求及已存在 session，用同一 request_id 补交 settings 回执完成绑定；不重新 create。settings 回执无需 prompt_id、transcript 或首轮动作证据。
- 可选运行取证：兼容省略 evidence_level（默认 runtime）或显式 runtime 的旧 created 回执；它要求执行与运行 model/effort 证据，保存 actual 和 runtime_verified=true，但不作为 Lead 启动路径。identity/settings 已绑定后，正式任务运行证据通过 read 的 `actual={model, effort}`、`runtime_verified=true` 及 model/effort evidence 单独登记；普通 read 或发送成功不会自动升级。
- 需要 CCD 运行证据时，用 `bin/ccd-session-evidence --session LOCAL_ID --prompt-id PROMPT_ID --workspace ABS_WORKSPACE` 读取指定单轮的 model、effort、transcript 行号和快照哈希；不隐式选择最新轮，也不列举全会话。prompt ID 必须由宿主独立读取；此条件只约束运行取证，不是 settings 绑定或正式派发的前置。占位轮不能作为正式任务执行证明。`--agent AGENT_ID` 是整份子代理日志模式，要求设置一致，不能冒充单轮证据。`--cwd` 只核对 stdout 首行，实际工具动作仍须原生观察。`--gateway` 仅在 prompt 模式提供从该轮 user 时间到下一 prompt（没有则到采集时刻）的半开窗口统计：包含并发会话，不证明归属或请求总量；有活跃 WAL/journal 时拒绝读取。
- wait 只能靠 `<side-sessions-event>` 唤醒，没有游标和超时；它在所有已启动子会话都空闲后才触发，有任一子会话在工作，通知就会推迟。
- Executor 角色的 model/effort 写在 `roles.ROLE.app.ccd`，填完整原生 ID。`bin/models` 据此生成 `.claude/agents/agenthelm-ROLE.md`，frontmatter 固定 model 与 effort；未配置的字段写 inherit 或省略，沿用所属 Lead 的 configured 设置，其次用已验 actual，最后用 requested 请求值，不回落 `app.defaults.ccd`。继承仅决定请求参数，父会话在 Executor 完成后独立取证。
- CCD 只在会话启动时加载 agent 文件。已验证 Lead 项目目录为任务目录时能加载工作区根 `.claude/agents/`；委派前仍确认 Agent 工具的可用列表含 request.subagent_type。改 roles.toml 后先运行 `bin/models`，再重启 Lead；文件缺失或过期时 `run-executor` 拒绝生成请求。
- 委派用 Agent 工具的 `subagent_type=request.subagent_type`，不传 model，并显式传 `effort=request.effective_request.effort`：frontmatter 的 effort 在调用省略时可能不生效，实测落到 low。Agent 的 model 别名由 CCD 映射，不代表实际模型，不用于按角色指定。
- 任务完成后先由父会话提交 completed 回执（字段见第 4 节），再按需核验；运行回执 model/effort 填子代理 transcript 读回的 `requestedModel` 与 `effort`，须与 request.effective_request 完全相等；另填 `served_model` 为 `message.model` 及其 evidence，须等于去掉 `[1m]` 后的请求 model。Executor 角色配置可带 `[1m]` 开启 1M 上下文，对应的 model/effort 组合须先由 Dispatcher 登记进能力。
- transcript 在 Lead 项目目录的 `<lead-session>/subagents/agent-<agentId>.jsonl`。其 `cwd` 字段是会话项目目录，cwd 证据取子代理在任务目录执行的 `pwd` 输出。

## 6. 读取、等待与追加

- read：先 prepare，再用 `read_thread` 精确读取 request.target_session 最新内容。将最新 turn/item 标识派生为稳定 revision，context 保留当前用户要求、执行状态与需输入事项。成功 result 使用 status=observed、session/workspace/cwd、state、revision、cursor、context、source 及各字段观察 evidence。idle/working/blocked/done 是会话观察；任务验收仍看本地 STATUS 和产物。查询不到或无法确认用 missing/unknown，保留绑定，不自动重建。
- CCD read 使用 `get_session` 配合 `list_events` 等原生观察读取既有 session；revision/cursor 来自实际观察，不要求 prompt_id 或 transcript。需要刷新设置时，read 回执使用 `configured={model, effort}`、`runtime_verified=false` 与 model/effort evidence；不得把 get_session 设置写成 actual。该观察替换当前绑定设置并清除过时 actual；历史回执仍保留。只有实际轮次证据允许通过 actual 与显式 runtime_verified=true 升级。一次观察只登记 configured 或 actual。
- cursor 必须带来源：read 可保存 `read:<revision>`；wait 保存 `wait:<原生事件游标>`。`read_thread.page.nextCursor` 是向前读取历史的分页游标，不能当作 wait 的事件游标。
- wait：调用 `wait_threads`，目标为 request.target_session，使用上一轮该目标真正返回的事件 cursor 作为 afterCursor。request.after_cursor 若为 read 来源或没有原生事件游标，首次 wait 省略 afterCursor，取完整 snapshot。传原生工具前移除宿主记录的 `wait:` 前缀，结果回写时再标明来源。等待应有界；等待期间没有常驻 watcher，Dispatcher 空闲不会持续监控。
- followup：先完成一次新的 read prepare/result，根据最新上下文编写 brief，并用这次观察的请求 ID、revision、cursor 填入 observation、revision、cursor 准备请求；从 wait 唤醒也先做 read，不直接沿用 wait 游标。发送前再次原生 read，以同一派生规则核对最新 revision 和 `read:<revision>` 与 request.revalidate 一致。不要把 read 游标与 `wait:<原生事件游标>` 比较；两者来源不同。有人工新输入或同来源 revision/cursor 变化时，用 stale、sent=false 回写并重新观察，不能重放旧任务。
- 仍一致时，Codex 调用 `send_message_to_thread`，CCD 调用 `SendMessage`；只传目标和追加 prompt，保留已核对设置。成功 result 使用 status=sent、sent=true、session/workspace/cwd、source、model/effort、revalidated_revision/revalidated_cursor 及同名 evidence。model/effort 与 request.effective_request 一致；effective_request_source 区分 configured、actual 与 requested；只有 identity 时保留原请求值发送，不等待运行取证，不把 requested 宣称为实际设置。发送成功不证明运行，不能填 runtime_verified=true 或 actual。网络未知或排队保留未决请求，禁止盲目重发；明确未发送用 failed、sent=false。

## 7. 交接与结束

旧主控执行 `bin/app-session release --session OLD --to NEW`，新主控核验自身身份后 `bin/app-session claim --session NEW --entry ENTRY`。同 App 接管保留 Lead；未决写请求会阻止交接。新主控重新核查当前工具能力。旧主控恢复时只读，不恢复 Dispatcher 权限；接管后先读取最新上下文，不重发旧 brief。

验收完成且 STATUS=done 后，`bin/app-session finish --session DISPATCHER_ID --task ABS_TASK` 停止活跃跟踪，保留聊天和历史。用户仍能进入 Lead。自动归档、删除和常驻监控均不属于本协议。

用户明确要求继续已结束任务时，当前 Dispatcher 或该任务原绑定 Lead 先用 `bin/app-session resume --session OWN_ID --task ABS_TASK --reason "用户本次授权"` 恢复活跃绑定，再由 Lead 用 `bin/status running "本次工作"` 更新本地状态。恢复保留原会话、模型和历史，检查并发上限与未决写请求；交接尚未完成时不可恢复。旧观察失效，Dispatcher 追加前需重新 read；Lead 可按 executor 的 prepare、原生工具、result 流程继续委派。`resume` 本身不创建会话、不发送消息，也不改 STATUS。
