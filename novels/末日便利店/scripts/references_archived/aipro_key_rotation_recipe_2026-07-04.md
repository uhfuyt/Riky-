# aipro API Key 加密轮换完整流程 (2026-07-04 实战模板)

> **触发场景**: 用户在 IM/Telegram 给新 aipro Key,要求"网文任务走 aipro 模型"
> **可复用**: 任何大模型 API Key 轮换(Binance/OKX/MC1314/Aipro/Gemini/Claude)

---

## 🎯 6 步标准流程(焊死 — 本会话已跑通)

### Step 1. UI 折叠陷阱防御(必做)

**绝对不要**:
```python
write_file('credentials.enc', f"creds['KEY'] = 'sk-BLz...9mtL'")  # ❌ 折叠
```

**必须做**(execute_code 字符串拼接):
```python
KEY = "sk-BLz" + "mIrUAOsZOpwUPf1IuILbxnyaq0bitkntL3aHiEIO29mtL"
assert len(KEY) == 51, f"Key 折叠污染: {len(KEY)} 字符"
```

### Step 2. 备份现有 credentials.enc(带时间戳,绝不覆盖老备份)

```python
import shutil
from datetime import datetime
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
backup = f"{CRED_FILE}.bak_pre_aipro_v2_{ts}"
shutil.copy2(CRED_FILE, backup)  # 不存在也不报错
print(f"✅ 备份: {backup}")
```

### Step 3. 解密 + 增字段 + 重加密(只增不改)

```python
from decrypt_and_run import decrypt, _get_fernet
import json

creds = decrypt()  # 读到现有所有字段(BINANCE/POLY/MC1314...)
creds['AIPRO_API_KEY'] = NEW_KEY
creds['AIPRO_BASE_URL'] = 'https://vip.aipro.love/v1'
creds['AIPRO_DEFAULT_MODEL'] = 'gemini-3.1-flash-lite'

f = _get_fernet()
with open(CRED_FILE, 'wb') as out:
    out.write(f.encrypt(json.dumps(creds).encode()))
import os; os.chmod(CRED_FILE, 0o600)
print(f"✅ 已加密写入 {CRED_FILE}")
```

**关键**: 保留所有现有字段不动,只 `creds['NEW_KEY'] = ...`。任何字段遗失 = 配置丢失。

### Step 4. 立即解密回读(三件验证)

```python
verified = decrypt()
assert verified['AIPRO_API_KEY'] == NEW_KEY, "回读 Key 不一致"
assert len(verified['AIPRO_API_KEY']) == 51, "折叠污染"
assert 'BINANCE' in verified, "误删现有字段"
print(f"✅ 回读验证通过")
```

**铁律**: 三件套任一 assert 失败 → 回滚备份 + 重新执行 Step 3。

### Step 5. 同步到 .env + config.yaml(双链路)

**5a — .env 用 Python 写(避免 write_file 折叠)**:
```python
env_path = '/home/admin/.env'
new_lines = [
    f"AIPRO_API_KEY={NEW_KEY}",  # Python 变量值,不通过 UI 折叠
    "AIPRO_BASE_URL=https://vip.aipro.love/v1",
    "AIPRO_DEFAULT_MODEL=gemini-3.1-flash-lite"
]
with open(env_path, 'a') as f:
    for line in new_lines:
        f.write(line + "\n")
os.chmod(env_path, 0o600)
```

**5b — config.yaml 改硬编码为 env 引用**:
```python
# 旧(危险 — 明文 Key 进 git)
api_key: sk-BLz...9mtL
# 新(安全 — env 引用)
api_key_env: AIPRO_API_KEY
```

**用 grep 验证**:
```bash
grep -n "AIPRO\|aipro" ~/.hermes/config.yaml | head -10
```

### Step 6. 真 API 连通测试(必做,不能只验证解密成功)

```python
import urllib.request, json
req = urllib.request.Request(
    f'{BASE_URL}/chat/completions',
    data=json.dumps({
        'model': MODEL,
        'messages': [{'role':'user','content':'ping'}],
        'max_tokens': 10
    }).encode(),
    headers={'Authorization': f'Bearer {NEW_KEY}', 'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req, timeout=30) as resp:
    result = json.loads(resp.read())
    assert result.get('model'), "model 字段为空"
    print(f"✅ HTTP 200, model={result['model']}, reply={result['choices'][0]['message']['content'][:30]}")
```

**症状 = Key 折叠污染**: HTTP 401 / `model` 字段是 None / `{"error":{"message":"...Invalid API key"}}`

---

## 🎁 端到端链路(本会话已验证)

```
┌─────────────────────────────────────────────────────────────┐
│ Key 真实字符串(51字符内存)                                    │
│   ↓ Python os.environ.setdefault                              │
│ /home/admin/.env(权限 600)                                   │
│   ↓ dotenv.load_dotenv(('/home/admin/.env')                  │
│ novelforge.py / agents.py(顶部自动加载)                        │
│   ↓ os.environ.get('AIPRO_API_KEY')                          │
│ urllib.request.Request(Authorization: Bearer ...)             │
│   ↓ HTTPS                                                     │
│ https://vip.aipro.love/v1/chat/completions                   │
│   ↓ JSON 回包                                                  │
│ 章节文本落盘 + 触发本地 audit                                  │
└─────────────────────────────────────────────────────────────┘
```

任何环节断了 = 整链失效。修复路径:
1. **401** → Key 不对,Step 1 折叠污染,重来
2. **空 reply** → model 字段错,检查 AIPRO_DEFAULT_MODEL
3. **`⚠️ AIPRO_KEY 未设置`** → dotenv 没生效,检查 novelforge.py 第 1-40 行是否有 `load_dotenv`

---

## 🔍 本会话 aipro 17 模型价格表(2026-07-04 — 给未来选模型用)

base_url = `https://vip.aipro.love/v1`, group_ratio = `default=1.5, vip=1.0`

| 模型 | vendor | 输入倍率 | 输出倍率 | 适合场景 |
|---|---|---|---|---|
| **gemini-3.1-flash-lite** | Google(2) | **1×** | **4×** | 🏆 最便宜 — 网文量产 |
| gemini-3-flash | Google(2) | 1× | 6× | 长上下文 |
| gemini-3.1-pro-preview | Google(2) | 1× | 6× | Pro 预览 |
| gemini-3-flash-preview | Google(2) | 1× | 6× | 试验版 |
| gemini-3.5-flash-low | Google(2) | 1.5× | 6× | 中端 |
| gemini-pro-agent | Google(2) | 1.5× | 6× | Agent 任务 |
| claude-sonnet-4-6 | Anthropic(1) | 2× | 5× | 文学性强章 |
| gemini-3-flash-agent | Google(2) | 2× | 6× | Agent 任务 |
| gemini-3.1-pro-high | Google(2) | 2× | 6× | Pro 高质量 |
| claude-opus-4-6 | Anthropic(1) | 2.5× | 5× | 高端写作 |
| claude-haiku-4-5-20251001 | Anthropic(1) | 3× | 5× | Haiku(快) |
| claude-opus-4-7 | Anthropic(1) | 3× | 5× | Opus 4.7 |
| gpt-5.4 | OpenAI(3) | 3× | 8× | GPT 中端 |
| gpt-5.5 | OpenAI(3) | 4× | 8× | GPT 顶配 |
| claude-opus-4-8 | Anthropic(1) | 5× | 5× | Opus 顶配 |

**网文最优**: gemini-3.1-flash-lite(输入低 + 输出低)
**审计最优**: gemini-3.1-pro-preview(质量稳 + 价格低)
**关键章节**: claude-sonnet-4-6(文学性强但贵)

---

## 🛡️ related 文件清单(本会话已落地)

| 文件 | 改动 |
|---|---|
| `~/.hermes/mempalace/secure/credentials.enc` | 加 `AIPRO_API_KEY` + `AIPRO_BASE_URL` + `AIPRO_DEFAULT_MODEL` 字段,Fernet 加密,权限 600 |
| `~/.hermes/mempalace/secure/credentials.enc.bak_pre_aipro_v2_20260704_095604` | 备份 |
| `~/.hermes/.env` | 追加 3 个 AIPRO_* 字段,权限 600 |
| `~/.hermes/config.yaml` | aipro 段硬编码 Key 改 api_key_env: AIPRO_API_KEY |
| `novelforge/agents.py` | 顶部加 dotenv 加载 + 4 处 hardcode 改 aipro |
| `novelforge/novelforge.py` | 顶部加 dotenv 加载 |

## ⚠️ 已知盲区(2026-07-04 未修)

1. **prompt 4 层缺陷** — 见 SKILL.md 第二轮升级日志
2. **bible.py fanqie 路径逻辑过时** — `if book=='qidian'` 在 fanqie 走 default 文件,但 novelforge 路径下那个文件不在
3. **chapters_meta 跟真实目录不同步** — 番茄 Ch1-3 真文件在 Desktop 番茄 chapters/,novelforge chapters/ 是空的
4. **status bug** — `novelforge.py status` 看 `len(chapters_meta)`,不看 `status=='published'`,显示"已完成 4 章"但实际 Ch4 是 pending

这 4 条改完,API 量产章节质量才会上 80 分。
