# 本地任务跟踪

未发现已配置的外部 tracker；本轮使用 to-tickets 支持的本地文件方式，不修改全局配置。需要永久 tracker 配置时由用户另行运行 /setup-matt-pocock-skills。

规格：[App 模式规格](../../docs/design/2026-10-22-app-mode-spec.md)。
架构：[App 模式设计](../../docs/design/2026-10-22-app-mode-design.md)；[ADR 0001](../../docs/adr/0001-app-lead-sessions.md)。

状态：ready-for-agent、in-progress、done、blocked。只有依赖全部 done 的任务可领取。勾选所有验收项、记录测试和提交后置 done；真实宿主测试单独记录，不能用离线通过替代。

集成分支：feat-app-lead-sessions。固定基点：91d4267。

## 接口约定

- 新增公共入口 bin/app-session，子命令 register、show、capabilities、prepare、result、release、claim、finish。
- register --entry app.codex|app.ccd --session ID；同一工作区只有一个有效 Dispatcher。
- capabilities --session ID 从 stdin 接收宿主能力 JSON；来源、目标入口与每项能力都必须明确。
- prepare --session ID --operation create|read|wait|followup|executor --task PATH；stdin 为 JSON 参数。输出请求 JSON，脚本本身不调用宿主工具。
- result --session ID --request ID；stdin 为回执 JSON。回执必须关联请求、运行入口、真实会话及观察证据。
- release --session OLD --to NEW；claim --session NEW --entry ENTRY；未决写请求阻止交接。
- show --session ID 返回绑定及本地任务状态；finish --session ID --task PATH 只在 STATUS=done 时停止跟踪，不操作宿主聊天。
- 模型公共函数由 bin/_models.py 提供 resolve_app(config, role, entry)，返回 model/effort 字段（default 为 null）及来源。bin/models resolve ROLE --entry ENTRY 输出 JSON。
- 各实现者可在自身负责文件增加参数；共享接口变化先报告，后续任务使用已合并代码。

## 任务图

01 与 02 可并行；03 依赖 01、02；04 依赖 03；05 依赖 01，可与 03/04 并行；06 依赖 03、05，可与 04 并行；07 依赖 04、06。

能力核查发现可通过本机 rollout 的白名单字段读取实际模型；将此独立可验证切片拆为 05，原宿主规则与最终集成顺延为 06、07。

宿主入口与恢复只依赖已完成的绑定、创建和运行证据接口；将 06 对 04 的依赖移至最终集成 07，避免把可并行工作串行化。

## 交付结果

01—07 全部完成代码与离线验收。完整测试112/112；Matt双轴审查最终无未解决发现。真实独立Lead创建、多模型分派、CCD创建与App默认取源的验收边界见 [验收记录](../../docs/validation/2026-10-22-app-mode-validation.md)。7个临时worktree已清理，未推送。
