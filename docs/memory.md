# 工作记忆使用入口

记忆的维护源是项目 `memory/<id>.md` 和任务 `memory/<id>.md` 中的主题笔记。各层 `MEMORY.md` 是生成的短目录，不是另一份正文。完整格式、更新责任和冲突边界见[工作记忆协议](../rules-extra.md)。规则源在 `templates/research-extra.md`。

下面的命令在工作区根目录运行。笔记来源、依赖和 CLI 的相对路径都以工作区根目录为基准，不随启动目录改变；本地绝对路径必须仍位于工作区内。真实示例见[目录归属笔记](../memory/workspace-layout.md)。

## 读取

Dispatcher 读取项目目录：

```bash
bin/kb memory context
```

Lead 读取项目和当前任务目录：

```bash
bin/kb memory context --task experiments/008-workspace-layout
```

按目录命中主题后显式打开笔记：

```bash
bin/kb memory read memory/workspace-layout.md
```

命令会检查已声明的来源。来源变化、缺失或明确冲突需要重查；哈希匹配不能证明权限、线上配置或用户要求仍然有效。有效的 active 笔记读取返回 `0`；非有效笔记返回 `1`，标明问题并显示原文供复查。非法或越界路径返回 `2`，不输出正文。Executor 只读取委派中给出的相关笔记，不自动继承全部项目和任务记忆。

## 更新与检查

先检索同主题并完整读取旧笔记，再核对相关出处。获授权 Lead 维护笔记正文，保留限制条件；Executor 将候选和证据交回 Lead。本文不提供自动总结、覆盖决定或定时整理命令。

代码调查通过具体源文件的内容指纹判断是否需要重查。读取指纹不修改笔记：

```bash
bin/kb memory fingerprint bin/lead-reload bin/kb
```

编辑完成后生成目录；生成前会校验笔记和预算：

```bash
bin/kb index
```

检查全部作用域：

```bash
bin/kb memory check
```

`memory check` 默认检查项目和全部直接任务；带 `--task` 时只查项目和指定任务。结构错误、目录缺失或过期、来源变化及声明 stale/conflict 都会失败；合法的 superseded 关系不视为失败。生成目录前会预检全部作用域，失败不发布索引；不要手工创建第二份 `MEMORY.md`。

只读核对目录是否过期：

```bash
bin/kb index --check
```

索引过期时，context 会提示并呈现内存中生成的当前短目录，不自动写回。非法或超限索引只显示诊断，身份和 STATUS 恢复仍继续。重建目录不代表重新核验笔记，只有实际重查后才能更新验证日期和来源指纹。

## 内容归属

| 内容 | 维护位置 |
|---|---|
| 跨任务仍有用的用户约束、经验与检索线索 | 项目 `memory/` |
| 本任务恢复不可丢失的决定与限制 | 任务 `memory/` |
| 当前进度、任务范围与结论 | STATUS 和任务 README，不复制到记忆 |
| 项目设计和已接受的架构决定 | `docs/`、`docs/adr/`，记忆仅引用 |
| 原始调查、运行输出和交付成品 | 任务 `findings/`、`results.jsonl`、`artifacts/` |

项目记忆不接管 HOME 中的 Claude/Codex 自动记忆，也不改变它们的既有规则。来源指向本机 ignored 资料的笔记只能在该资料存在时核验，不能因此声称克隆仓库即可恢复全部历史。
