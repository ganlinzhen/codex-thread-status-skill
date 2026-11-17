# thread-status

给 Codex 主会话标题加上状态前缀。只维护正在进行的这一条主会话，不扫描历史会话，也不在后台监听。

标题形如 `[doing] 原主题`。状态只有八个小写值：`draft`、`doing`、`scheduled`、`wait`、`blocked`、`paused`、`drop`、`complete`。

## 一键安装

需要 Python 3.9 或更新版本，仅使用标准库，无需安装第三方依赖。获取源码后，执行一次安装命令即可同时安装技能和配置全局触发规则，不需要手工编辑 `AGENTS.md`：

```bash
git clone https://github.com/ganlinzhen/codex-thread-status-skill.git
cd codex-thread-status-skill
python3 scripts/install.py
```

默认把技能复制到 `~/.agents/skills/thread-status/`，并向 `~/.codex/AGENTS.md` 添加一段带 `thread-status:begin` / `thread-status:end` 标记的触发规则。设置了 `CODEX_HOME` 时，规则与安装记录改写到该目录；技能目录仍保持默认位置。

安装器保留标记外的原有内容、换行和文件权限。重复执行不会重复添加规则；已安装技能存在个人改动或目标目录属于其他安装时，停止覆盖。安装记录保存在 Codex 配置目录的 `thread-status-install.json`，用于识别本安装器管理的对象。更新技能版本时，先保留个人修改、卸载，再运行新版安装器；重复安装不自动替换技能源版本。

安装完成后在新会话验证。如果技能尚未显示，可重新启动 Codex。技能仍依赖宿主提供标题读取和改名工具；装好文件不会为缺少这些工具的宿主补出能力，也不会让空白或空闲会话在后台自行改名。

## 卸载

使用已安装副本中的脚本即可卸载：

```bash
python3 ~/.agents/skills/thread-status/scripts/uninstall.py
```

也可以从下载的源码目录执行 `python3 scripts/uninstall.py`。卸载仅移除本安装器的托管规则，保留用户原有内容及后来在标记外增加的规则。只有技能目录由本安装器创建、且内容未变时才删除技能副本；预先存在的源码或符号链接、用户修改过的技能会保留并提示，不删除下载的源码仓库。

如果手工修改了托管规则内部，脚本会停止，避免抹掉这些修改。安装前已有的手工触发规则属于用户原文，不由本安装器卸载。

## 自定义路径

安装与卸载须使用相同参数：

```bash
python3 scripts/install.py --codex-home /path/to/codex --skills-dir /path/to/skills
python3 scripts/uninstall.py --codex-home /path/to/codex --skills-dir /path/to/skills
```

全局规则的模板位于 `prompts/global-trigger.md`，只负责读取技能；状态判断和收尾行为仍以 `SKILL.md` 为准。对话中也可以直接写 `$thread-status` 检查一次。规则是模型执行约定，不是平台级强制触发。

## 八种状态

| 状态 | 含义 |
| --- | --- |
| `draft` | 目标还不清楚。 |
| `doing` | 已经开工，当前仍有可以继续做的工作。 |
| `scheduled` | 已确认启用周期调度，当前等待下一轮执行，无需用户处理。 |
| `wait` | 等待用户输入、决定、验收，或阶段交付后等待后续安排。 |
| `blocked` | 外部条件挡住，当前做不下去。 |
| `paused` | 用户明确暂停整个会话目标，或已核实本会话调度已暂停。 |
| `drop` | 用户明确要求放弃整个会话目标。 |
| `complete` | 用户明确确认整个会话目标已完成，或直接要求把本会话标为完成。 |

`complete` 和 `drop` 只接受用户针对整个会话的明确说法；`paused` 也可以依据已核实的调度暂停状态。放弃一个方案或暂停一个步骤，不等于放弃或暂停整个会话。旧标题里的 `[success]` 只是待替换前缀，不是验收证据。

主题尽量保留。重复的状态前缀收成一个，主题里原有的其他方括号保留，例如 `[doing] [TASK-1] 修复登录`。

## 定时任务

已确认绑定到本会话且启用周期调度的任务，按下面的循环更新：

```text
[scheduled] 等待下一轮 → [doing] 本轮执行 → [scheduled] 正常结束
```

“没有新内容”“无需操作”以及无需逐轮验收的常规报告，都属于本轮正常结束。只有需要用户输入、决策、授权或处理异常时才用 `wait`。外部故障导致无法继续时用 `blocked`，不能把未解决的失败当成正常排期；明确暂停或核实调度暂停后使用 `paused`。

一次检查完成不代表整个监控结束，`complete` 始终需要用户明确确认。只在提到“每天检查”时，不会推断已有调度；取消调度也不自动判为完成。技能不创建或修改定时任务，也不会在后台持续刷新标题。

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
prompts/global-trigger.md
scripts/install.py
scripts/uninstall.py
scripts/_installation.py
scripts/test_installation.py
README.md
LICENSE
```

行为以 `SKILL.md` 为准。运行 `python3 scripts/test_installation.py` 可在临时目录验证安装与卸载，不触碰当前用户的全局配置。

## 许可

MIT License。版权声明为 `Copyright (c) 2026 thread-status contributors`。许可证原文是英文，见 [LICENSE](LICENSE)。

