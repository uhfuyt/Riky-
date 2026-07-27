# Subagent 派发前置检查 (2026-07-04 焊死)

## 致命陷阱

**一次性派 N 个 subagent 用 `acp_command: <cli>` 重写章节 → 机器没装该 CLI → 全部失败 → 0 文件改动 → 7 个 [ASYNC DELEGATION BATCH COMPLETE] 失败消息污染上下文 → 用户问"为什么卡"时无法解释**

## 真实复现 (2026-07-04)

派 20 个 subagent 重写 20 章节,每个 task 都传 `acp_command: copilot` + `acp_args: [--acp, --stdio]`。
机器**没装 GitHub Copilot CLI**(`which copilot` 返回空)。
20 个 subagent 全部 1 个 API call 就失败:
```
API call failed after 3 retries: Could not start Copilot ACP command 'copilot'.
Install GitHub Copilot CLI or set HERMES_COPILOT_ACP_COMMAND/COPILOT_CLI_PATH.
```

7 个 [ASYNC DELEGATION BATCH COMPLETE] 失败消息接连返回,但 `status=completed` 标记"完成",**严重误导**:看上去 subagent 跑完了,实际 0 改动。

**用户问"为什么卡"时无法说"我没装 CLI",因为这在 17:07 派发时本应知道。**

## 前置检查清单 (焊死,派发 subagent 前必跑)

```bash
# 1. 验证 ACP CLI 存在
which <acp_command> 2>&1
# 或
command -v <acp_command>

# 2. 验证 API key 配置
echo $DEEPSEEK_API_KEY $AIPRO_API_KEY $MC1314_API_KEY | head -c 50

# 3. 验证 subagent 工具集生效
# (这一项无法前置测试,只能派发 1 个看返回)
```

**任何一项 fail → 不派 subagent,改用主对话 write_file 工具**

## 默认正确做法 (3 种方案)

### 方案 A: 不传 `acp_command` (推荐,最稳)

```python
delegate_task(
    goal="写 Ch3 到 4000字",
    context="...",  # 完整自包含上下文
    toolsets=['terminal', 'file'],  # 必填工具集
    # 不要传 acp_command
    # 不要传 acp_args
    # 默认用父级 Hermes transport
)
```

subagent 自动用 parent 相同的 transport,不会触发 CLI 检查。

### 方案 B: 传 `acp_command` 但先验证

```bash
which copilot || echo "❌ copilot CLI 未装, 不要传 acp_command=copilot"
```

如果未装 → **必须用方案 A**。

### 方案 C: 派 1 个 subagent 试水

派 1 个 subagent,等返回。如果 `status=completed` 但 `api_calls=1` 且消息是 "Could not start Copilot ACP command" → 立即撤销剩余派发,改主对话。

## 失败后正确反应 (焊死)

**subagent 失败后禁止**:
- ❌ 再次 retry
- ❌ 分析"为什么失败" (用户已经看到失败消息)
- ❌ 改用其他 acp_command (大概率也未装)
- ❌ 等更多失败消息回来

**subagent 失败后必须**:
- ✅ **立即切回主对话**,用 `write_file` 工具自己干
- ✅ 诚实告诉用户"subagent 失败, 我用主对话写"
- ✅ 不要重复"假完成"陷阱 (v0.5.4 的覆辙)

## 用户偏好 (2026-07-04)

> 用户原话:"检查下刚刚为什么会卡, 起点第7章和番茄第4章看下是否需要重新写, 当它们不存在"

**用户已经看穿 v0.5.4 的"假完成"**。subagent 失败等同 v0.5.4 假完成,**禁止任何形式**的 "稍等我再试一次" / "换个 tool 试试" / "我分析下原因"。

## 验证 checklist (派发前 1 分钟必跑)

- [ ] `which <acp_command>` 验证 CLI 存在 (或不用 acp_command)
- [ ] `echo $<API_KEY>` 验证 Key 长度 ≥ 40
- [ ] 工作目录存在且 git status 干净
- [ ] 任务的 `context` 字段自包含 (subagent 看不到我的对话历史)
- [ ] 任务的 `goal` 字段明确字数 + 字数验证方法 (例如 "目标 3800-4200 字, 写完跑 len(re.findall(...)) 验证")
- [ ] 任务的 `file_path` 明确 (不要让 subagent 猜)
- [ ] 我已准备好 1-2 个 backup plan (subagent 失败用主对话写)
