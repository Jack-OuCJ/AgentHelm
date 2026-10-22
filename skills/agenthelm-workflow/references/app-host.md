# App 宿主执行协议

适用 `app.codex` 与 `app.ccd`。项目 CLI 管理本地绑定和请求，当前聊天中的智能体调用原生工具；Python 不会调用聊天内工具。先确认用户已授权创建独立 Lead、委派或追加任务，并遵守宿主对独立聊天、跨聊天消息和子代理的限制。本规则不增加用户权限。

## 1. 核对当前身份与能力

- 从当前宿主原生会话信息取得真实会话 ID、入口和工作区；不从工作区路径、`.agenthelm/config/role` 或父提示猜身份。Codex 读取精确 ID 的 `read_thread`，并用 `list_projects` 核对项目根目录等于当前工作区。用户指定的当前主控经核对后运行 `bin/dispatch --entry app.codex --session ID`；CCD 使用 `app.ccd`。`--print` 仅只读预览，不注册。已有主控时按下文交接，不抢占。
- 有效 Dispatcher 用 `bin/app-session show --session ID` 核对当前归属。已绑定 Lead/Executor 用 `bin/lead-reload ABS_TASK --session OWN_ID` 核对自身 session、entry、role 与任务；此命令不会授予 Dispatcher 权限。角色模型通过 `bin/models resolve ROLE --entry ENTRY` 解析；请求参数与实际生效值分别记录。
- 能力登记由有效 Dispatcher 完成：查看当前宿主工具定义后，向 `bin/app-session capabilities --session DISPATCHER_ID` 提交 JSON：`entry`、总 `source`、逐项 `capabilities`。每项含 `available` 和自己的 `source`；创建需 create/read/wait/followup/model/effort/verify_model，Executor 另需 native_executor。`model.values` 列当前可用模型，`effort.combinations` 按模型列合法强度，`verify_model.fields` 必须含 model、effort。Lead/Executor 仍须核对本次宿主工具；缺口报告父会话，不冒用主控 ID 登记。工具存在与真实端到端验收分别记录。
- `default`/null 需要目标 App 新会话默认值的可靠来源。先确定最终所选 model，再取得该 model 的原生默认 effort；角色显式 model、effort=default 时，不能套用 App 默认模型或 Dispatcher 当前模型的 effort。配置文件顶层值、父会话实际值和参数回显都不足以单独证明默认选择。无可靠来源即报告 capability gap，保持未创建；用户已配置显式角色 model/effort 时按显式值执行。
- CCD 当前没有确认可用的原生独立会话 create 工具。缺口未补齐时将 create 标为 unavailable，明确停止自动创建；深链接、手工粘贴与 CLI 不能冒充原生创建成功。

### 首次创建的绑定握手

父会话提交 created 回执前，新 Lead/Executor 的原生 ID 尚无本地绑定。仅在当前会话确由父会话已获授权的 create/executor request 原生创建或委派时，按该 request.prompt 的 entry、task、role 和文件边界执行首个授权任务动作，并向父会话报告原生 ID、当前 turn、实际任务目录与动作记录、实际 model/effort 的观察证据。此阶段不注册 Dispatcher，也不创建下层 Executor。

父会话完成原生核验并成功写入 created 回执后，才用 `bin/lead-reload ABS_TASK --session OWN_ID` 核验正式绑定并继续对应角色流程。回执仍待验证时停在握手等待阶段；其他未知绑定直接报告缺失。提示词中的角色声明或 unknown-binding 都不授予主控或委派权限。

## 2. 准备一次操作

在工作区运行 `bin/app-session prepare --session ID --operation create|executor|read|wait|followup --task ABS_TASK`，stdin 提供该操作 JSON。新任务与已有任务可分别用 `bin/new-task SLUG --session ID --app-params JSON < card.md`、`bin/spawn-lead ABS_TASK --session ID --app-params JSON` 取得 create 请求；两者自身不创建 App 聊天。

create/read/wait/followup 由有效 Dispatcher 准备，executor 由已绑定 Lead 准备；Executor 执行授权委派并向父会话报告证据。

- create 的参数可含 important；需要原生默认的字段须有 `defaults: {model, effort, source, evidence}`。证据属于目标 App 和所选模型。任务卡必须明确目标、可写范围、输出与验收要求。
- `run-executor --print` 返回 preview=true、executable=false，无请求 ID；只读预览不能调用宿主或提交回执。正式 executor 的参数为 role、brief 及必要 defaults。使用已绑定 Lead 的 session；`bin/run-executor ABS_TASK --session LEAD_ID --role hard --app-params JSON < brief.txt` 会附加完整工作区与角色入口。brief 明确可写文件和验收命令。
- read/wait 使用 `{}`；followup 使用 brief、observation、revision、cursor，关联发送前新完成的一次 read 观察。
- 保存输出 request 的 id、owner_epoch、entry、workspace、task、caller_session 与完整 prompt。宿主只执行该 request 声明的操作。未决 create 保留占位；先读取待处理请求，不重复准备另一个创建。

## 3. Codex 创建独立 Lead

1. 再次核对请求归属和用户授权；从 `list_projects` 选路径精确等于 request.workspace 的本地项目。调用 `create_thread`，target 为该 project 的 local 环境，prompt 使用 request.prompt，model/thinking 使用 request.effective_request 的模型与强度。不要用原生子代理、fork 或后台 CLI 代替独立用户聊天。
2. `clientThreadId` 只表示排队，不能填作最终 session。排队或网络结果未知时回写 queued/unknown，保留 request 和占位；使用宿主返回的操作标识查询恢复，不重复 create。只有宿主明确确认未创建，才用 failed、created=false 释放占位。
3. 拿到真实 threadId 后，用 `list_threads` 与精确 ID 的 `read_thread` 验证独立、可见、同工作区；会话不能是 Dispatcher，也不能已绑定其他任务。创建工具的 prompt 字段不证明首轮执行。
4. 首轮必须真实执行授权任务动作：工具的 workdir 指向 request.task，执行 `pwd` 和任务要求的首个动作。用 `read_thread` 的输出或等价原生观察保存 first_action 工具记录及实际 stdout。receipt.cwd 的证据来自真实任务操作进程的目录；提示词写了任务路径不算执行。
5. 从该精确 threadId 的原生 `read_thread` 独立取得当前实际 turn ID，然后运行 `bin/codex-session-evidence --session THREAD_ID --turn TURN_ID --workspace ABS_WORKSPACE`。核对返回 session、turn_id、source、model、effort 与请求；证据引用 source.path、locator 行号和快照哈希。helper 的 runtime cwd 可为工作区根目录，只用于工作区关联，不能替代第 4 步的任务 cwd 与动作证据。
6. 用 `bin/app-session result --session DISPATCHER_ID --request REQUEST_ID` 回写完整 created 回执。回执关联 request_id、owner_epoch、entry、真实 session、workspace、cwd，含 visible=true、independent=true、executed=true、实际 model/effort，以及各字段 evidence 的原生观察定位。model/effort 证据必须来自实际轮次，不能来自调用参数。

缺任意证据时保持待验证，不宣称 running。实际参数不匹配时报告失败或待处理原因，不能静默降级模型、改写请求后假称原请求成功。helper 只读本机运行记录，不证明可见性、首轮动作或任务验收。

## 4. Codex 原生 Executor

使用 request.caller_session 对应 Lead 的原生 `collaboration.spawn_agent` 或当前宿主等价能力。委派完整 request.prompt，明确角色、绝对任务目录、可写范围、验收命令、禁止全局配置修改和不再向下委派。需要独立指定模型时使用当前工具允许的无历史 fork 方式与 request.effective_request；不能把默认继承父模型冒充目标 App 默认。

从精确子代理 ID 的原生 `read_thread` 独立取得该子代理当前 turn ID，然后运行：

```sh
bin/codex-session-evidence --session EXECUTOR_ID --kind executor \
  --parent-session LEAD_ID --turn EXECUTOR_TURN_ID --workspace ABS_WORKSPACE
```

即使子代理日志带父历史，也只接受精确子代理当前 turn；不能从 helper 将要验证的日志反向挑选 turn，也不能使用父 turn。子代理须真实在任务 workdir 执行授权动作。created 回执另含 native=true、parent_session=LEAD_ID，以及 evidence.native、evidence.parent_session。Executor 的原生来源与父绑定由 helper 检查；fork 会话不能作为独立 Lead。

## 5. CCD 模型与原生 Executor

- Dispatcher 的模型由用户在 CCD 中用 `/model` 手动选择，不读 roles.toml。
- Lead 先起 session，再切到 `bin/models resolve ROLE --entry app.ccd` 解析出的原生 ID。会话不能改自己的模型，由用户 `/model` 或其他会话切换。核对以 Lead 实际轮次的 model 为准。
- Executor 角色的 model/effort 写在 `roles.ROLE.app.ccd`，填完整原生 ID。`bin/models` 据此生成 `.claude/agents/agenthelm-ROLE.md`，frontmatter 固定 model 与 effort；未配置的字段写 inherit 或省略，沿用所属 Lead 的实际值，不回落 `app.defaults.ccd`。
- CCD 只在会话启动时加载 agent 文件。已验证 Lead 项目目录为任务目录时能加载工作区根 `.claude/agents/`；委派前仍确认 Agent 工具的可用列表含 request.subagent_type。改 roles.toml 后先运行 `bin/models`，再重启 Lead；文件缺失或过期时 `run-executor` 拒绝生成请求。
- 委派用 Agent 工具的 `subagent_type=request.subagent_type`，不传 model。Agent 的 model 别名由 CCD 映射，不代表实际模型，不用于按角色指定。
- 回执 model/effort 填子代理 transcript 读回的 `requestedModel` 与 `effort`，须与 request.effective_request 完全相等；另填 `served_model` 为 `message.model` 及其 evidence，须等于去掉 `[1m]` 后的请求 model。Executor 角色配置可带 `[1m]` 开启 1M 上下文，对应的 model/effort 组合须先由 Dispatcher 登记进能力。
- transcript 在 Lead 项目目录的 `<lead-session>/subagents/agent-<agentId>.jsonl`。其 `cwd` 字段是会话项目目录，cwd 证据取子代理在任务目录执行的 `pwd` 输出。

## 6. 读取、等待与追加

- read：先 prepare，再用 `read_thread` 精确读取 request.target_session 最新内容。将最新 turn/item 标识派生为稳定 revision，context 保留当前用户要求、执行状态与需输入事项。成功 result 使用 status=observed、session/workspace/cwd、state、revision、cursor、context、source 及各字段观察 evidence。idle/working/blocked/done 是会话观察；任务验收仍看本地 STATUS 和产物。查询不到或无法确认用 missing/unknown，保留绑定，不自动重建。
- cursor 必须带来源：read 可保存 `read:<revision>`；wait 保存 `wait:<原生事件游标>`。`read_thread.page.nextCursor` 是向前读取历史的分页游标，不能当作 wait 的事件游标。
- wait：调用 `wait_threads`，目标为 request.target_session，使用上一轮该目标真正返回的事件 cursor 作为 afterCursor。request.after_cursor 若为 read 来源或没有原生事件游标，首次 wait 省略 afterCursor，取完整 snapshot。传原生工具前移除宿主记录的 `wait:` 前缀，结果回写时再标明来源。等待应有界；等待期间没有常驻 watcher，Dispatcher 空闲不会持续监控。
- followup：先完成一次新的 read prepare/result，根据最新上下文编写 brief，并用这次观察的请求 ID、revision、cursor 填入 observation、revision、cursor 准备请求；从 wait 唤醒也先做 read，不直接沿用 wait 游标。发送前再次原生 read，以同一派生规则核对最新 revision 和 `read:<revision>` 与 request.revalidate 一致。不要把 read 游标与 `wait:<原生事件游标>` 比较；两者来源不同。有人工新输入或同来源 revision/cursor 变化时，用 stale、sent=false 回写并重新观察，不能重放旧任务。
- 仍一致时调用 `send_message_to_thread`，只传目标和追加 prompt，省略 model/thinking，保留实际配置。成功 result 使用 status=sent、sent=true、session/workspace/cwd、source、实际 model/effort、revalidated_revision/revalidated_cursor 及同名 evidence。无法证明实际设置时不能报成功。网络未知或排队保留未决请求，禁止盲目重发；明确未发送用 failed、sent=false。

## 7. 交接与结束

旧主控执行 `bin/app-session release --session OLD --to NEW`，新主控核验自身身份后 `bin/app-session claim --session NEW --entry ENTRY`。同 App 接管保留 Lead；未决写请求会阻止交接。新主控重新核查当前工具能力。旧主控恢复时只读，不恢复 Dispatcher 权限；接管后先读取最新上下文，不重发旧 brief。

验收完成且 STATUS=done 后，`bin/app-session finish --session DISPATCHER_ID --task ABS_TASK` 停止活跃跟踪，保留聊天和历史。用户仍能进入 Lead。自动归档、删除和常驻监控均不属于本协议。

用户明确要求继续已结束任务时，当前 Dispatcher 或该任务原绑定 Lead 先用 `bin/app-session resume --session OWN_ID --task ABS_TASK --reason "用户本次授权"` 恢复活跃绑定，再由 Lead 用 `bin/status running "本次工作"` 更新本地状态。恢复保留原会话、模型和历史，检查并发上限与未决写请求；交接尚未完成时不可恢复。旧观察失效，Dispatcher 追加前需重新 read；Lead 可按 executor 的 prepare、原生工具、result 流程继续委派。`resume` 本身不创建会话、不发送消息，也不改 STATUS。
