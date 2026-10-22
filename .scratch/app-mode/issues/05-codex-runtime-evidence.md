# 05: 只读提取 Codex Desktop 的实际模型证据

**What to build:** 宿主执行者按精确会话标识读取本机 Codex 运行记录，取得实际模型、推理强度与轮次证据，无需暴露聊天正文或凭据。

**Blocked by:** 01 注册唯一 Dispatcher 并保留会话入口。

**Status:** in-progress

- [ ] 公共 CLI 只读返回会话 ID、Desktop 来源、工作区、最新轮次、模型、强度和证据定位。
- [ ] 拒绝不匹配 ID、非 Desktop Lead 来源、无轮次、歧义记录、缺字段、截断记录和路径逃逸；原生 Executor 的来源可明确单独校验。
- [ ] 不输出消息正文、工具参数或凭据，不修改任何 HOME 文件；配置默认不冒充实际生效值。
- [ ] 公开 CLI 隔离 HOME 的 red/green 测试，以及当前会话白名单读取验证通过。
