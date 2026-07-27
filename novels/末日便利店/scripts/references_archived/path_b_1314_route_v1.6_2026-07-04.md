# 路径 B 1314 配置 — 备用模型路由 (v1.6 焊死, 2026-07-04)

> 来源: 用户原话 "aipro 没费用了, 改成用1314的便宜大模型吧".
> 触发场景: aipro 余额耗尽 / 用户明确说 "用 1314" / 量产 10+ 章且 MiniMax 配额耗尽.
> 章节正文仍走路径 A (MiniMax 对话窗口直写, 0元), 1314 仅作备用路径 B.

---

## 1314 端点配置 (焊死)

| 字段 | 值 |
|---|---|
| 端点 base_url | `https://api.1314mc.net/v1` |
| Key 字段名 | `MC1314_API_KEY` (env) / `mc1314.api_key` (config.yaml) |
| 默认模型 | ~~`deepseek-v4-flash` (最便宜档)~~ → **MiniMax-M3 (实测唯一稳定, 详见 v0.7 钉)** |
| 备选模型 | `MiniMax-M3`, `gpt-5.5`, `claude-opus-4-8`, `gemini-3.1-pro-high` |
| 控制台 | `https://api.1314mc.net/console` |
| 支持模型数 | 86 个 (deepseek/gpt-5.5/claude/gemini/MiniMax/GLM/Qwen/Kimi 全系) |

### config.yaml 现状 (2026-07-04)

```yaml
mc1314:
  api_key: sk-5fZ...lkVf   # ⚠️ UI 折叠显示, 真 Key 51 字符在 credentials.enc
  base_url: https://api.1314mc.net/v1
  models:
    - MiniMax-M3           # 默认 (实测唯一稳定, 详见 v0.7 焊死)
    - MiniMax-M2.7         # 备选 1
    - claude-opus-4-8      # 备选 2 (贵但稳)
    - claude-sonnet-4-6    # 备选 3
    - gpt-5.5               # 备选 4
    - gemini-3.1-pro-high  # 备选 5
  # ❌ 不再推荐 deepseek-v4-flash / gemini-3-flash / claude-haiku (2026-07-04 实测全军覆没)
```

### ⚠️ v0.7 便宜档模型全军覆没 (2026-07-04 钉, 实测)

**原 v1.6 推荐 "default = deepseek-v4-flash 最便宜档"** —— **实测完全失败**, 已替换为 **MiniMax-M3**。

实测结果 (2026-07-04):

| 模型 | HTTP | 输出 | 状态 |
|---|---|---|---|
| `deepseek-v4-flash` | 200 | **0 字空输出** (715 token 消耗但无内容) | ❌ 不可用 |
| `gemini-3-flash` | 200 | **29 字截断** (markdown `**` 没闭合) | ❌ 不可用 |
| `claude-haiku-4-5` | 503 | 服务不可用 | ❌ 不可用 |
| `gemini-3.5-flash-low` | timeout | 5 分钟超时 | ❌ 不可用 |
| `claude-haiku-4-5-F` | timeout | 同上 | ❌ 不可用 |
| **`MiniMax-M3` (1314 转发)** | **200** | **800 字正常输出** | ✅ 可用 |

**根因**: 1314 平台转发便宜档模型时, **stream processing 不完整** (deepseek 截到 0 字, gemini 截到 29 字, claude-haiku 上游 503)。

**唯一稳定 = MiniMax-M3 (自家产品, 1314 直连)**。

**修复铁律 (替换上一版 "默认 deepseek-v4-flash")**:
- ✅ **1314 默认模型 = `MiniMax-M3`**, 不是 deepseek-v4-flash
- ✅ **不要相信 1314 的 "-F" / "-low" / "-cheap" 命名 = 便宜档 = 可用**
- ✅ 每个便宜档只测一次 30 秒超时, 失败立即换模型, **不重试不批量测** (本 session 5 分钟 timeout 浪费)
- ✅ **写章节任务只用 MiniMax-M3 当前对话** (实测比 1314 便宜档都稳定)

---

## UI 折叠陷阱 (致命, 焊死)

**症状**: config.yaml 里 `mc1314.api_key: sk-5fZ...lkVf` 看起来像有效 Key (开头 sk-, 13字符折叠).

**真相**:
- 折叠显示 ≠ 真实 Key, 只是 `sk-5fZ` (前4) + `...` + `lkVf` (后4) 拼接
- 真实 Key 是 51 字符完整串, 加密存在 `~/.hermes/mempalace/secure/credentials.enc`
- 直接用折叠 Key 调用 = `401 Invalid API Key`, 而且**没有任何报错提示**这个 Key 是 UI 折叠

**铁律 (任何 provider 都适用)**:
1. **永远不硬编码 Key 到 config.yaml** — 改用 `api_key_env: MC1314_API_KEY`
2. **config.yaml 里的 `api_key` 字段是 placeholder**, 真正用 Key 走 env
3. **加密存储**: Fernet AES-256 存 `~/.hermes/mempalace/secure/credentials.enc` 字段 `MC1314_API_KEY`
4. **运行时解密**: agents.py 顶部 `load_dotenv('/home/admin/.hermes/.env')` → `os.environ.get('MC1314_API_KEY')`
5. **验证 Key 长度**: `assert len(os.environ.get('MC1314_API_KEY')) == 51`, 失败 = UI 折叠污染
6. **完整 Key 拼接**: `KEY = "sk-5fZ" + "完整后续..."` (运行时内存拼接, 不写在任何文件里)

---

## 1314 路径 B 调用铁律 (2026-07-04 焊死)

### 调用方式

```python
import os
from dotenv import load_dotenv
load_dotenv('/home/admin/.hermes/.env')  # 必须在任何 os.environ 之前

api_key = os.environ.get('MC1314_API_KEY', '')
base_url = os.environ.get('MC1314_BASE_URL', 'https://api.1314mc.net/v1')
model = os.environ.get('MC1314_DEFAULT_MODEL', 'deepseek-v4-flash')

# 验证
assert len(api_key) == 51, f"❌ MC1314_API_KEY 长度异常 ({len(api_key)}), 可能是 UI 折叠污染"

# 调 API (POST /v1/chat/completions)
import urllib.request, json
req = urllib.request.Request(
    f'{base_url}/chat/completions',
    data=json.dumps({
        'model': model,
        'messages': [...],
        'max_tokens': 4500,
        'temperature': 0.9,
        'presence_penalty': 0.3,
        'frequency_penalty': 0.2,
        'top_p': 0.95,
    }).encode(),
    headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
)
```

### 环境变量 (写入 `~/.hermes/.env`, 权限 600)

```bash
MC1314_API_KEY=sk-5fZ...完整51字符...lkVf
MC1314_BASE_URL=https://api.1314mc.net/v1
MC1314_DEFAULT_MODEL=deepseek-v4-flash
```

### agents.py 4 处 hardcode 改造清单 (焊死)

1. `api_key = os.environ.get('MC1314_API_KEY', '')` (老: `DEEPSEEK_API_KEY` 或 `AIPRO_API_KEY`)
2. `base_url = os.environ.get('MC1314_BASE_URL', 'https://api.1314mc.net/v1')`
3. `model = os.environ.get('MC1314_DEFAULT_MODEL', 'deepseek-v4-flash')`
4. `req = urllib.request.Request(f'{base_url}/chat/completions', ...)`

---

## 何时调 1314 路径 B (铁律)

### ✅ 该用

- 用户明确说 "用 1314 写" / "aipro 没钱了用 1314"
- 量产 10+ 章场景 (MiniMax 5小时固定 token 跟不上)
- aipro gemini-3.1-flash-lite 持续 503 或余额耗尽
- 想用不同模型风格对比 (claude-opus-4-8 vs gemini-3.1-pro-high)

### ❌ 不该用

- 默认写章节正文 (走路径 A)
- 用户没说, 路径 A 还没试过
- 仅 1-2 章补写场景

---

## 已知陷阱 + 修复

### 坑 1: env 加载陷阱 (2026-07-04 实测血泪)

**症状**: Key 加密存好、.env 写好、config.yaml 配好、agents.py 改完, **`python3 novelforge.py chapter` 报 `⚠️ MC1314_API_KEY 未设置`**

**根因**: Python **不自动加载 .env**。`os.environ.get()` 拿的是继承自父 shell 的空环境, 不是 .env 解析后的环境

**修复**: `novelforge.py` + `agents.py` 顶部都加:
```python
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser('~/.hermes/.env'))
except ImportError:
    pass
```

**验证**: 改完 .env 后第一件事跑 `python3 -c "from dotenv import load_dotenv; load_dotenv('/home/admin/.env'); import os; print(os.environ.get('MC1314_API_KEY')[:10])"` 看 Key 能不能读出

### 坑 2: base64 PNG 误判 (2026-07-04 本会话新踩)

**症状**: 调 1314 路径 B 测试连通性时, 输出了一大段 base64 编码的 PNG 数据, 我差点误以为是模型返回

**根因**: 测试请求可能触发了图像生成端点 (虽然不常用), 或者 1314 端点的 /chat/completions 在某种错误状态下返回了图像 base64

**修复**:
- ✅ 连通性测试时显式检查 `response.headers.get('Content-Type')` 是否是 `application/json`
- ✅ 解码后必须验证 `json.loads()` 成功, 且字段 `choices[0].message.content` 存在
- ✅ 不要相信任何"超大输出", 第一步永远解析 + 校验结构
- ✅ 给 ai_detector 加一条: "模型输出 > 5KB 必查 base64 嫌疑"

### 坑 3: 1314 端点超时 (历史日志)

**症状**: `Max retries exceeded with url: /v1/chat/completions (Caused by ConnectTimeoutError('Connection to api.1314mc.net timed out. (connect timeout=30)'))`

**根因**: 1314 服务器在某些时段 (尤其美东下午) 经常慢, 30s 超时不够

**修复**:
- ✅ timeout 改 60s (urllib.request 默认无超时, 必须显式设)
- ✅ `retry_with_backoff(max_attempts=3, delay=5)` 加重试
- ✅ 失败 2 次切 aipro (gemini-3.1-flash-lite) 兜底

### 坑 4: model 名拼写错误

**症状**: `model: 'gpt-5.4-nano'` → 503 Service Unavailable

**根因**: 历史记忆里写过 GPT-5.4-nano, 但 2026-07-04 config 里只有 gpt-5.5 系列, 4 系列已下线

**修复**: 任何 model 名用前, 先 `curl /v1/models` 拿真实列表, 严禁凭记忆写 model 字段

---

## 端到端验证 checklist (任何 1314 改动后必跑)

- [ ] Fernet 加密 + 立即解密 + 51 字符长度验证
- [ ] curl `/v1/chat/completions` 拿 HTTP 200 + `choices[0].message.content` 非空
- [ ] agents.py 4 处 hardcode 改造后语法 OK (`python3 -c "import agents; print('OK')"`)
- [ ] .env + config.yaml 链路 OK (`os.environ.get('MC1314_API_KEY')[:10]` 打印真 Key 前缀)
- [ ] 端到端: `os.environ` → agents.py → urllib → 1314 API → 真实输出
- [ ] **novelforge.py + agents.py 双路 load_dotenv 已加**
- [ ] max_tokens ≥ 4500 保底 (避免提前结束)
- [ ] 测试请求用纯文本 prompt, 不夹图像 / 多模态

---

## Token 成本表 (2026-07-04)

| 操作 | 单次 token | 30万字总成本 |
|---|---|---|
| 路径A MiniMax直写一章 | ~3000 tok | **0元/本** |
| 路径B 1314 deepseek-v4-flash 一章 (v1) | ~3500 tok (含原文+codex+伏笔) | ~1-3元/本 (最便宜档) |
| 路径B 1314 deepseek-v4-flash 一章 (v2 省token) | ~1500 tok | **~0.5-2元/本** |
| 路径B 1314 gpt-5.5 一章 (v2) | ~1500 tok | ~2-5元/本 |
| 路径B 1314 claude-opus-4-8 一章 (v2) | ~1500 tok | ~5-15元/本 (文学性强, 备用) |

**省钱策略**: 默认 MiniMax 直写 (0元), 1314 deepseek-v4-flash 是最便宜 API 备选.

---

## 相关文件

- 父技能: `long-novel-writer-pipeline` (L7 节)
- 历史 reference: `style_anchoring_path_a_over_path_b_2026-07-04.md` (路径A/B 决策与风格锚定)
- 历史 reference: `aipro_env_loading_pitfall_2026-07-04.md` (env 加载陷阱, 1314 同样适用)
- 历史 reference: `aipro_key_rotation_recipe_2026-07-04.md` (Key 加密轮换流程, 1314 复用)
- 历史 reference: `省tokenv2_optimization_2026-07-04.md` (5项优化省 55% token)
- 历史 reference: `字数校准_v3_published-data_2026-07-04.md` (字数校准)
- 历史 reference: `preamble_defense_2026-07-04.md` (gemini preamble 防御, 1314 上 claude/gemini 同样适用)