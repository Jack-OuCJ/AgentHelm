# 02: 解析并展示 App 角色模型绑定

**What to build:** 用户在同一角色配置中设置各 App 的默认模型及角色覆盖，查询实际请求参数，同时继续使用原有 CLI 命令。

**Blocked by:** None (can start immediately).

**Status:** done

- [x] 按字段解析角色覆盖、App 默认、原生默认，default 不继承 Dispatcher 或 CLI。
- [x] 明确拒绝非法配置，保留现有 CLI 行为。
- [x] 公共 JSON 查询和生成模型表展示 App 绑定及来源。
- [x] unittest 验证各字段优先级、默认与 CLI 回归。

验收：公开 CLI 单测 8 项通过；实现提交 6de21d8。原生 App 实测不属于本票结论。
