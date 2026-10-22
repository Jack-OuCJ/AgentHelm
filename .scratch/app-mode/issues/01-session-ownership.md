# 01: 注册唯一 Dispatcher 并保留会话入口

**What to build:** 用户可注册已有 App 会话、查看唯一主控与运行入口；其他会话不能冒领调度权，工作区默认值不改变绑定。

**Blocked by:** None (can start immediately).

**Status:** in-progress

- [ ] 公开 CLI 支持注册、查询、能力登记；冲突不抢占。
- [ ] 原子状态与锁防止并发注册；路径逃逸和损坏状态明确报错。
- [ ] 能力逐项记录来源，CCD 无创建能力时明确可见。
- [ ] unittest 验证入口绑定、重复注册、并发与全局配置不变。
