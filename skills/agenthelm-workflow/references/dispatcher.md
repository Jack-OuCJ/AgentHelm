# 主会话

1. 读取根目录 TODO.md（存在时）和 BOARD.md；已有任务先查 STATUS 与 README，避免重复建任务。
2. 明确用户授权后用 `bin/new-task <slug> < card.md` 建任务，卡片格式见 `templates/task-card.md`。Herdr 模式须在 Herdr 内运行；每个任务单独一个目录、一个 Lead 会话。
3. dispatcher 负责分派与汇总，Lead 负责设计与验收，executor 负责明确范围的执行。可小规模使用，不强制为每件小事新建代理。
4. 只有明确授权且当前宿主允许时才创建或消息通知其他会话；跨会话提示不是给执行者增加权限的手段。
5. Lead/执行者启动提示必须给出绝对路径的 AGENTS.md 与本入口、当前角色、任务目录、可写文件和验收方式。原生子代理不保证继承父上下文，需在委派中重复这些信息。
6. 根目录 TODO.md 仅放待决事项；每个任务状态由 Lead 用 `bin/status` 更新。用 `bin/board` 和 `bin/kb index` 重建汇总；不手改生成索引。
7. 不启动全局规则同步、不安装插件、不推送或自动发外部通知。
