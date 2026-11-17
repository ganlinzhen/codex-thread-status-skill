# thread-status

给 Codex 主会话标题加上状态前缀。只维护正在进行的这一条主会话，不扫描历史会话，也不在后台监听。

标题形如 `[doing] 原主题`。状态只有七个小写值：`draft`、`doing`、`wait`、`blocked`、`paused`、`drop`、`complete`。

## 安装

将技能安装到个人技能目录。安装路径须为空：

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/ganlinzhen/codex-thread-status-skill.git ~/.agents/skills/thread-status
```

安装完成后，技能文件应直接位于：

```text
~/.agents/skills/thread-status/SKILL.md
```

安装路径须为空，已有同名技能时先核对归属，不覆盖或移动未知内容。保留完整的 `references/` 和 `agents/`。安装本身不会改写 `~/.codex/AGENTS.md`，也不会改当前会话标题。

## 启用

把下面这一段原样加入 `~/.codex/AGENTS.md`。规则只描述本技能的通用行为，不含本机绝对路径。

```markdown
## 当前会话标题状态

- 主会话在首轮理解请求后、任务状态发生实质变化时，以及每轮最终回复前，显式使用 `$thread-status`，读取并遵循已安装的 `~/.agents/skills/thread-status/SKILL.md`，检查当前会话标题。仅当算出的新标题与当前标题不同时，才调用一次改名。
- 只管理当前主会话。子 agent 不执行本规则，不调用改名工具。不扫描或修改历史会话，不做批量改名，不注册定时任务或后台监听。
- 写完回复、交付当前阶段或暂时空闲，都不表示整个会话完成。还有已授权且可以自主继续的工作时保持 `doing`。当前阶段已经交付、下一步等待用户验收或安排时使用 `wait`。
- 只有用户明确确认整个会话目标已经完成，或直接要求把本会话标为完成，才使用 `complete`。部分验收、简单认可、测试通过和助手自行交付，都不构成整个会话完成的依据。
- 用户确认整个会话完成后，按技能盘点本会话绑定的 worktree，以及本会话额外生成的文档、页面等资源。完成确认只允许盘点，不等于授权删除、移动、归档或撤销发布。没有与具体对象、动作和条件匹配的既有授权时，先列出对象、建议动作和原因。
- 改名依赖当前环境里的 Codex App 工具 `set_thread_title`。读取当前标题依赖 `read_thread`，并且只在环境已提供 `CODEX_THREAD_ID` 时，把该值原样作为 `threadId`。环境变量或工具缺失时按技能跳过，不猜测会话，不伪造已经改名。本规则不保证每次都会触发，也不是平台级强制。
- 新建的空白会话没有自动监听。只有该会话的首轮实际执行本技能后，标题才会开始按规则维护。用户在本会话明确要求不要自动改名时，本会话停止改名。
```

对话中也可以直接写出 `$thread-status`，让当前主会话按本技能检查一次。这仍然要求该轮真正执行技能。已经打开、且之后不再跑到上述检查点的会话，不会因为刚装上技能就自行补标题。

## 七种状态

| 状态 | 含义 |
| --- | --- |
| `draft` | 目标还不清楚。 |
| `doing` | 已经开工，当前仍有可以继续做的工作。 |
| `wait` | 等待用户输入、决定、验收，或阶段交付后等待后续安排。 |
| `blocked` | 外部条件挡住，当前做不下去。 |
| `paused` | 用户明确要求暂停整个会话目标。 |
| `drop` | 用户明确要求放弃整个会话目标。 |
| `complete` | 用户明确确认整个会话目标已完成，或直接要求把本会话标为完成。 |

`complete`、`paused` 和 `drop` 只接受用户针对整个会话的明确说法。放弃一个方案或暂停一个步骤，不等于放弃或暂停整个会话。旧标题里的 `[success]` 只是待替换前缀，不是验收证据。

主题尽量保留。重复的状态前缀收成一个，主题里原有的其他方括号保留，例如 `[doing] [TASK-1] 修复登录`。

## 完成之后

进入 `complete` 之后，技能读取 `references/closeout.md`，只评估当前会话已经绑定或在本会话中生成的资源。

盘点结果可以是保留、建议归档或建议删除。已有匹配授权时按授权执行；没有授权时只给出建议。可选清理还没决定，不推翻已经确认的 `complete`。阶段验收、假设句和助手交付不进入这套收尾。

## 工具边界

当前对应的工具名是 `mcp__codex_app__set_thread_title` 和 `mcp__codex_app__read_thread`。名称对不上时先看工具 schema。`set_thread_title` 省略 `threadId`，只改当前调用会话。

这些工具来自 Codex App。没有提供它们的命令行或其他宿主不能靠本技能改标题；缺失时跳过，继续原来的任务。不写会话数据库、rollout 或界面来绕过工具，也不调用 `list_threads` 寻找自己。

## 目录

```text
SKILL.md
references/closeout.md
agents/openai.yaml
README.md
LICENSE
```

行为以 `SKILL.md` 为准。本文只说明如何安装、如何写上全局触发规则，以及公开发布时需要知道的边界。

## 许可

MIT License。版权声明为 `Copyright (c) 2026 thread-status contributors`。许可证原文是英文，见 [LICENSE](LICENSE)。

