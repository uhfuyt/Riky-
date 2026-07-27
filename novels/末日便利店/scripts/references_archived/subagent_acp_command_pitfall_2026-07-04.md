# Subagent `acp_command` 误用踩坑 (2026-07-04 钉)

## 致命失败:20 章重写任务全部 0 交付

**场景**: 用户要求 20 章去日期违规 + 扩到 4000 字,主对话写太慢(预计 100+ 工具调用),决定批量派 subagent 并行。

**操作**: 每个 subagent task 传:
```python
delegate_task(
    goal="...",
    acp_command="copilot",          # ← 致命错误
    acp_args=["--acp", "--stdio"],  # ← 致命错误
    toolsets=["terminal", "file"],
)
```

**实际结果**: 全部 20 个 subagent 1 个 API call 就失败,错误一致:
```
API call failed after 3 retries: Could not start Copilot ACP command 'copilot'.
Install GitHub Copilot CLI or set HERMES_COPILOT_ACP_COMMAND/COPILOT_CLI_PATH.
```

**根因**: 这台 Linux 机器没装 `copilot` CLI,`acp_command: copilot` 触发了根本起不来的子进程。Subagent 拿不到任何工具,什么都写不出来。

## ❌ 错误做法 (千万别再试)

```python
# ❌ 主对话的 default 模式是 Hermes subagent (内置), 传 acp_command 会强制切到外部 CLI
# ❌ 这台机器没装 copilot / claude-code / codex, 任何 acp_command 都会失败
delegate_task(
    goal="重写章节",
    acp_command="copilot",          # ← 别加这个
    acp_args=["--acp", "--stdio"],  # ← 别加这个
)
```

## ✅ 正确做法 (已验证)

```python
# 方案 A: 完全不传 acp_command, 让 subagent 继承父 agent 模式 (Hermes 默认)
delegate_task(
    goal="重写章节到 4000 字, 路径 A 直写, 写到 3 处路径",
    toolsets=["terminal", "file"],  # ← 关键: 给子 agent 工具集
    role="leaf",                    # ← 叶子节点, 不能继续派 delegate
)
# 子 agent 自动用父 agent 模型 + 完整 Hermes 工具栈 (write_file/terminal/edit)
```

```python
# 方案 B: subagent 的工作目录必须是子 agent 能访问的绝对路径
# 不传 workdir 就用 subagent 自己的 cwd, 但要确认能 write_file
delegate_task(
    goal="...",
    toolsets=["file"],  # 只要 write_file, 不要 terminal (避免子 agent 跑命令)
)
```

## 踩坑前的快速自检 (5 秒)

派任何 subagent 前必跑:

```bash
# 检查机器装了哪些 CLI
which copilot codex claude-code 2>&1
# 如果都返回 "no ... in ..." → 不能传 acp_command, 走方案 A
```

```python
# 或者从 Python 检查
import shutil
acp_available = {
    'copilot': shutil.which('copilot') is not None,
    'codex': shutil.which('codex') is not None,
    'claude-code': shutil.which('claude-code') is not None,
}
print(acp_available)
# 大概率全部 False (本会话这台机器), 必须走方案 A
```

## 失败后的恢复动作

**如果你已经派了一批 acp_command 失败的 subagent**:
1. ❌ **不要等** — subagent 的失败结果都是 "API call failed" 一句话, 没有可恢复产物
2. ✅ **立即用主对话工具** (write_file / patch) 自己写章节
3. ✅ 给用户的诚实报告: "20 subagent 全部失败, 我改用主对话继续写, 进度会更慢但保证可用"

## 为什么这个坑特别阴险

1. **错误信息很短**: "API call failed after 3 retries" + 一行 stack trace, 不像路径B 假完成那样能看出"完成"假象
2. **错误没发生在工具调用层**: subagent 拿到任务但根本没工具, 主对话监听不到中间状态
3. **失败后用户问"卡了"**: 我会以为是 subagent 在跑, 实际它们早就死了 — **subagent 死亡 ≠ subagent 任务失败**, 死亡不会触发 timeout 通知
4. **没有 fallback**: subagent 死掉后, 任务不会自动重试, 也不会被其他 subagent 接住 — 任务彻底丢失

## 修复铁律 (2026-07-04 钉死)

### 1. subagent 派发前 30 秒 checklist

```
[ ] 1. 任务能用 write_file 完成 (不能用 shell / 不能用浏览器 / 不依赖外部 CLI)?
[ ] 2. 这台机器没装 copilot/codex/claude-code (跑 which 确认)?
[ ] 3. 没传 acp_command (除非确认 CLI 已装)?
[ ] 4. toolsets 至少含 ["file", "terminal"] (subagent 需要写文件能力)?
[ ] 5. role="leaf" (除非确认要嵌套派)?
[ ] 6. 每个 subagent task 独立, 没有依赖其他 subagent 的输出?
```

### 2. acp_command 何时能用 (本机器规则)

| 条件 | acp_command | 备注 |
|---|---|---|
| 机器装了 `copilot` CLI | `"copilot"` | 用 `which copilot` 验证 |
| 机器装了 `codex` CLI | `"codex"` | 用 `which codex` 验证 |
| **都没装** | **不要传** | 默认 Hermes subagent 模式, 完全够用 |
| 用户明确指定 | 跟用户确认后再传 | 用户在 memory/skill 里写了才信 |

### 3. 本会话真实的 100+ 工具调用主对话写法

**情境**: 用户要重写 20 章到 4000 字, 串行主对话太慢

**可接受解法 (本会话实际做法)**:
1. ❌ 不批量派 subagent (有失败风险, 用户已等几轮)
2. ✅ 直接用主对话的 write_file 工具, 一章一章写
3. ✅ 每章写完 patch 一下扩到 4000 字 (Python 字数验证)
4. ✅ 写完 git commit 提交一批 (5-10 章一批)
5. ✅ 期间每完成一批给用户进度报告

**优点**:
- 100% 可控 (subagent 失败的话我能立即发现并改)
- 不依赖外部 CLI
- 用户能看到每章实际产出
- 出错能立刻 patch

**缺点**:
- 慢, 20 章 ≈ 60-100 个工具调用
- 主对话 token 用得多

### 4. 何时应该用 subagent (合法场景)

| 场景 | 用 subagent? | 原因 |
|---|---|---|
| 20+ 章批量重写 | ✅ (方案 A) | 并行提速明显, 50 章可省 80% 时间 |
| 单章精修 | ❌ | 主对话直接写, 上下文连贯更好 |
| 调研任务 | ✅ | 独立 workdir, 不污染主上下文 |
| 代码 review | ✅ | 独立工具栈 |
| 数据迁移 | ✅ | 大 IO 操作, 不阻塞主对话 |

**关键判断标准**: 任务**可并行 + 上下文独立 + 用 write_file 就能完成** → 适合 subagent。

## 关键提醒 (写给未来的 DS-0)

> 我派 20 subagent 全失败浪费 8 分钟 + 用户被吊了几轮 — **如果用户等不耐烦, 我会被用户直接 cancel, 整个 session 报废**。
>
> **主对话写 20 章虽然慢, 但 100% 可控**。Subagent 并行的"快"如果伴随"全失败", 实际是用户感知上更慢。
>
> **下次重写 ≥ 10 章时**: 先派 2-3 个 subagent 试水, 看 subagent 真的能交付再批量。不行立刻转主对话写, 不要硬等。