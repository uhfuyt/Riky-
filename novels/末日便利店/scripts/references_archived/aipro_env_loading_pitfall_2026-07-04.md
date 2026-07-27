# aipro 路径 B 的 .env 加载陷阱 (2026-07-04 实测血泪)

> **触发**: 用户配置好 aipro gemini-3.1-flash-lite 路径(2026-07-04),改完 agents.py / config.yaml / 加密 Key,跑 `python3 novelforge.py chapter qidian 4` 立刻看到 `⚠️ AIPRO_API_KEY 未设置`。
> **根因**: Python 子进程**不自动加载 `.env`**。`agents.py` 第56行 `os.environ.get('AIPRO_API_KEY', '')` 拿的是空的,run_writer 直接 return,根本没调 aipro API。
> **影响**: 整个路径 B(API 量产章节)在不修这个之前**全部失效**,无论 Key 多正确。

---

## 🔴 症状复现(逐字)

```bash
$ cd /home/admin/.hermes/mempalace/novel/novelforge/
$ python3 novelforge.py chapter qidian 4

[写手] [qidian] 第4章 母亲来电(1500字)
  钩子:
  爽点:

--- 必读1: 全部Codex角色卡 ---
  [c001] 林北舟 (主角): ...
  ...
--- 必读4: 最近3章原文(防遗忘) ---

⚠️ AIPRO_API_KEY 未设置 — 当前无法调用LLM
→ 临时方案: 由DS-0直接产出章节正文,手动写到: ...
```

代码走到了"必读清单"那一步(说明 bible.py + codex.py + consistency.py 都正常加载),**但走到第 56 行环境变量检测就 return**。

debug: 在 agents.py 第 56 行加 `print(os.environ)` 会发现 `AIPRO_API_KEY` 字段不存在。但 `/home/admin/.env` 文件里**有这一行**。

---

## 🧪 真根因(已验证)

| 步骤 | 现象 | 解释 |
|---|---|---|
| shell 跑 `python3 ...` | 子进程 | Python 不读 .env —— 这是 Python 默认行为,**不是 bug** |
| `os.environ.get('AIPRO_API_KEY')` | 返回空字符串 | 子进程 env 完全继承**父 shell**,**.env 不会自动注入** |
| shell `source ~/.hermes/.env` | shell 变量生效 | bash 知道 `source`,但 Python 不会 |
| shell `export AIPRO_API_KEY=*** && python3 ...` | env 注入成功 | 临时 export 后子进程继承 —— 这是当前 SKILL 文档推荐做法 |

---

## ✅ 修复方案(三种,推荐第二种)

### 方案 A — shell 临时 export(文档推荐,但易忘)

```bash
export AIPRO_API_KEY=*** AIPRO_BASE_URL=https://vip.aipro.love/v1
export AIPRO_DEFAULT_MODEL=gemini-3.1-flash-lite
cd /home/admin/.hermes/mempalace/novel/novelforge
python3 novelforge.py chapter qidian 4
```

- 缺点: 每次跑要 export 三个变量;新开会话就忘;DS-0(我)从对话窗口跑 subprocess 也要写 export
- 优点: 0 依赖,改 shell 配置即可

### 方案 B — agents.py 顶部加 `python-dotenv` 加载(✅ 推荐)

```python
# agents.py 顶部,~ line 14 之后
try:
    from dotenv import load_dotenv, find_dotenv
    # 优先 ~/.hermes/.env,如果不存在就跳过(不报错)
    env_path = '/home/admin/.env'
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass  # 没装 python-dotenv 就静默 fallback 到方案 A
```

- **优点**: 一行代码,所有 `novelforge.py` 子命令自动生效,DS-0 跑 subprocess 不需要任何手动操作
- **依赖**: 需要 `pip install python-dotenv`(无副作用,纯 Python)
- **验证脚本**(改完跑这个,看 4 个 env 变量是否在 subprocess 里都有):
```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/home/admin/.env')
for k in ['AIPRO_API_KEY','AIPRO_BASE_URL','AIPRO_DEFAULT_MODEL','DEEPSEEK_API_KEY']:
    v = os.environ.get(k,'')
    print(f'  {k}={v[:8]+\"...\"+v[-6:] if len(v)>20 else v} (len={len(v)})')
"
```

### 方案 C — novelforge.py 顶部加载(写一次,所有子命令都受益)

跟方案 B 一模一样,只是写在 `novelforge.py` 而不是 `agents.py`。区别:
- 写 `novelforge.py` → `next` / `status` / `audit` / `chapter` / `polish` / `publish` 所有 CLI 入口都生效
- 写 `agents.py` → 只有 `chapter`(调 `run_writer`)和 `audit`(调 `run_auditor`)生效

**推荐方案 C** —— 一次性彻底解决。代码片段:

```python
# novelforge.py 顶部,line 1-5 之后
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser('~/.hermes/.env'))
except ImportError:
    pass
```

**这一行必须在任何 `os.environ.get()` 调用之前**,否则 Key 还是读不到。

---

## 🧨 同类陷阱清单(顺手清掉)

### 1. `pip install python-dotenv` 是否要 sudo?

不。`pip install --user python-dotenv` 就够。验证: `python3 -c "import dotenv; print('ok')"`。

### 2. `.env` 权限 600 + Python 子进程读取

没事,owner 是 `admin` 就读得到,Linux 文件权限不会拦读 own 文件。

### 3. 多 Key 同名(如 aipro 和 mc1314 都有同名变量)

把所有 aipro 相关 env 都用 `AIPRO_` 前缀(mc1314 用 `MC1314_` 前缀),不冲突。**不要图省事复用同一名字**。

### 4. DS-0 从对话窗口跑 subprocess 时,这条 fix 是否仍然生效?

✅ 生效。原因: DS-0 是 Hermes runtime 起的 Python,本身已加载 env。我用 `execute_code` 跑的子 Python 会在自己进程里调 `load_dotenv`,跟任何 shell 跑 `python3` 一样行为。

### 5. .env 文件被 .gitignore 了吗?

✅ 必须 .gitignore,`~/.hermes/.env` 不应在 git 里。但 `.gitignore` 写 `*.env` 太宽,推荐精确 `.gitignore`:
```
# web-novel 凭据
/.env
/aipro.env
```
然后 `git status` 确认 .env 不出现在 tracked files 里。

---

## 🔍 验证 checklist(修复后必跑)

```bash
# 1. dotenv 装好
python3 -c "import dotenv; print('✅ dotenv', dotenv.__version__)"

# 2. .env 加载生效
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('/home/admin/.env')
key = os.environ.get('AIPRO_API_KEY','')
assert len(key) == 51, f'Key 长度异常: {len(key)}'
print(f'✅ AIPRO_API_KEY 长度 {len(key)}')
print(f'   model: {os.environ.get(\"AIPRO_DEFAULT_MODEL\")}')
print(f'   url:   {os.environ.get(\"AIPRO_BASE_URL\")}')
"

# 3. 真跑 chapter 命令,看到 aipro 调用成功
cd /home/admin/.hermes/mempalace/novel/novelforge/
python3 novelforge.py chapter qidian 4
# 期待输出末尾有:
#   ✅ aipro调用成功 / 已落盘: ...
# 而非:
#   ⚠️ AIPRO_API_KEY 未设置
```

---

## 📍 真实案例记录(本会话 2026-07-04)

- **触发**: 用户说"执行写网文任务时你调用 https://vip.aipro.love 模型"
- **已完成全部步骤**:
  1. Fernet 加密 Key(AES-256) → `~/.hermes/mempalace/secure/credentials.enc` 加 `AIPRO_API_KEY` 字段
  2. 解密写入 `~/.hermes/.env`(权限600,字段 `AIPRO_API_KEY`+`AIPRO_BASE_URL`+`AIPRO_DEFAULT_MODEL=gemini-3.1-flash-lite`)
  3. agents.py 4 处 hardcode 改造:`DEEPSEEK_API_KEY`→`AIPRO_API_KEY` / `https://api.deepseek.com`→`f"{AIPRO_BASE_URL}/chat/completions"` / `'deepseek-chat'`→`os.environ.get('AIPRO_DEFAULT_MODEL', 'gemini-3.1-flash-lite')` / 错误消息改名
  4. config.yaml `aipro.api_key: sk-BLz...9mtL` 改成 `api_key_env: AIPRO_API_KEY`,models 列表加 `gemini-3.1-flash-lite`
  5. **✅ 本会话已修 .env 加载(2026-07-04)**: `novelforge.py` 和 `agents.py` 顶部都加了 try/except 双路 `load_dotenv`(有 python-dotenv 用库,无则手动解析 .env 退化)
- **验证**:`python3 novelforge.py chapter qidian 4` 在子进程无 env 情况下,dotenv 加载生效,aipro API 真调用成功,生成 1347 字章节并落盘,自动触发 audit
- **⏳ 已知未修**:prompt 4层缺陷(人名漂移/场景错乱/上下文没喂原文/bible路径fanqie逻辑过时)—— 见 SKILL.md 末"agents.py 升级日志 2026-07-04 第二轮"

**给下一个 session 的 DS-0**: 这一坑 100% 会再踩 —— 任何"配置 aipro Key 之后跑 novelforge chapter"的任务,优先确认这一行 fix 是不是在。**修复标准**: grep `load_dotenv` 必须在 `novelforge.py` 第 1-40 行之间。

---

## 🛠️ 关联文件 + 修复位置

| 文件 | 位置 | 改动 |
|---|---|---|
| `novelforge.py` | 顶部 line 1-10 之后 | 加 `try: from dotenv import load_dotenv; load_dotenv('/home/hermes/.env') except ImportError: pass` |
| `agents.py` | 顶部 line 14 之后 | 同上(若选方案 B 而非 C) |
| `requirements.txt` | novelforge/ 目录 | 加 `python-dotenv>=1.0.0` |
| `~/.gitignore` | novelforge/ 目录 | 加 `/.env`、`/aipro.env` |
| `web-novel-production/SKILL.md` | 阶段5.1 路径 B 段 | 加一句"路径 B 调用**前必须** `pip install python-dotenv`,"否则 `novelforge.py chapter` 会因读不到 .env 而 return" |
