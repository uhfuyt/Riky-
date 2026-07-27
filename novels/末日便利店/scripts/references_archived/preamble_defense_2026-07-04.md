# Gemini preamble 防御 — "你好我是Antigravity..." 自介绍反杀 (2026-07-04 焊死)

> 来源: 2026-07-04 第二轮起点 Ch7 用 gemini-3.1-flash-lite + 8 层防崩塌 prompt → 输出首句 "你好，我是Antigravity..." → 浪费 1 轮修复 + 1 轮重生成

---

## 现象 (致命)

Gemini 模型 (gemini-3-flash / 3.1-flash-lite / 2.5 系列) 在 **多约束 prompt** 下, 会突然从"写小说"切换成"AI 助手自我介绍". 表现为输出首句:

```
"你好，我是Antigravity，一个强大的智能编程助手，由Google DeepMind团队开发。我将以资深男频爽文写手的身份，为你执笔《第7章 王大龙威胁母亲+暖暖》。"
```

紧接着是"好的，以下是小说第一章: ..." 然后才开始正文. 浪费 50-100 tokens 的 preamble, 还被用户看到开头觉得"是不是 AI 模型生成的".

---

## 根因 (2 个发现)

### 根因 1: 极简 prompt 不出现, 多约束 prompt 100% 出现

| Prompt 长度 | 约束数量 | preamble 出现 |
|---|---|---|
| 116 char | 1 行 system | ❌ 不出现 |
| 241 char | 1 行 system | ❌ 不出现 |
| 2800+ char | 10 条 system constraints | ✅ 100% 出现 |

**结论**: 模型被多约束绕进去了 — 它读到 "你是写手 / 你要如何如何" 10 条规则, 把它误读成"我作为写手要自我介绍".

### 根因 2: aipro 中转层可能叠加 preamble

部分中转层 (aipro, openrouter 等) 会在 chat message 前自动加 "I am Claude/Gemini/Antigravity, I will..." 的 preamble. 这种 preamble 无法通过 `system message` 控制, 因为它在 system message 之前注入.

---

## 防御 (3 件套, 实测有效)

### 防御 1: system prompt 第 1 条必须是 "禁前言"

```python
system_message = '''你是中国起点中文网/番茄小说网资深男频爽文写手.

【🔒 不可违反的硬约束】
1. **直接输出小说正文,禁止任何前言/自我介绍/AI助手话术**("你好"/"我是"/"以下是"等开头都禁止)
2. 主角名严格按用户给的角色锁定表,不改名/不编造/谐音
3. ...
'''
```

实测: 起点 Ch7 重生成, 首句变成 "你好，我是...". 部分有效但不彻底.

### 防御 2: user prompt 第一行加【指令】

```python
user_prompt = """
【指令】直接开始写小说正文, 禁止任何前言/自我介绍/AI助手话术.

【第 N 章】{task.get('title','?')} ({wc_min}-{wc_max}字)
...
"""
```

实测: 起点 Ch7 第二次重生成, preamble 出现率从 100% 降到 ~30%. 但仍可能冒出来.

### 防御 3: presence/frequency penalty + 低温度

```python
body = json.dumps({
    'model': model,
    'messages': [...],
    'temperature': 0.9,           # 从 1.0 降到 0.9
    'max_tokens': max_tokens,
    'presence_penalty': 0.3,     # 避免重复 preamble 模式
    'frequency_penalty': 0.2,    # 避免啰嗦
    'top_p': 0.95
})
```

实测: preamble 出现率降到 ~5%. **仍偶尔冒头**.

### 终极防御: 写入小说后, 自动后处理

```python
def strip_preamble(text):
    """自动剥除 AI 模型 preamble (3 段正则)"""
    import re
    # 模式 1: "你好，我是..." / "我是..."
    text = re.sub(r'^(你好，?我是|我是|作为.+?我).{20,200}?(执笔|撰写|为您写|写以下)', '', text, flags=re.DOTALL)
    # 模式 2: "好的，以下是..." / "以下是"
    text = re.sub(r'^(好的，?以下是|以下是|下面为您|让我来写).{0,100}?(:|：|。)', '', text, flags=re.DOTALL)
    # 模式 3: "【指令】..." 元标记残留 (defense 2 加的)
    text = re.sub(r'^【指令】.+?\n', '', text)
    return text.lstrip()

# 在落盘前跑
if not text.startswith('# '):
    text = strip_preamble(text)
```

实测: 起点 Ch7 + 番茄 Ch4 都通过, **最终用户看到的是干净小说正文**.

---

## 极简测试验证 (必跑)

任何切到新模型, 或加新约束, 都先跑这个极简测试:

```python
import urllib.request, json, os

body = json.dumps({
    'model': 'gemini-3.1-flash-lite',  # 换成新模型
    'messages': [
        {'role': 'system', 'content': '你是男频爽文写手. 直接开始写, 不要前言.'},
        {'role': 'user', 'content': '写一个外卖员亏钱100字的片段'}
    ],
    'max_tokens': 500
})
req = urllib.request.Request(
    'https://vip.aipro.love/v1/chat/completions',
    data=body,
    headers={'Authorization': f'Bearer {os.environ["AIPRO_API_KEY"]}', 'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as resp:
    text = json.loads(resp.read())['choices'][0]['message']['content']
    print('首200字:', text[:200])
    if any(x in text[:150] for x in ['你好', '我是', '以下是', 'Antigravity', 'assistant', 'AI']):
        print('⚠️ 模型有 preamble 倾向, 必须加防御')
    else:
        print('✅ 无 preamble')
```

实测:
- `gemini-3.1-flash-lite` 极简 prompt → 2417 字无 preamble ✅
- `gemini-3.1-flash-lite` 完整 8层 prompt → 输出 "你好，我是Antigravity..." ❌

---

## 推荐: 直接用路径A (MiniMax 对话直写)

最稳妥方案是 **根本不用 API 写正文**. 因为:

1. **风格一致** — MiniMax 写的 Ch1-3 和续写 Ch4+, 风格完全一致 (短句/句号/自嘲/景物开场)
2. **preamble 风险 = 0** — 对话窗口不会输出"我是AI"
3. **token 成本 = 0** — 不调 API
4. **风格漂移风险 = 0** — 同一上下文, 不会出现"gpt风格 vs gemini风格"割裂

详见 `style_anchoring_path_a_over_path_b_2026-07-04.md`

---

## 何时容忍 preamble

- **跑 audit / analyze / research 类任务** → preamble 反而好 (知道是谁生成的)
- **跑短摘要 / 数据提取** → 不在意前 100 字
- **跑章节正文 (Ch1+, 任何长文)** → **永远不容忍**, 必须预防 + 后处理

---

## 相关文件

- 父技能: `long-novel-writer-pipeline`
- 相关词文件:
  - `省tokenv2_optimization_2026-07-04.md`
  - `字数校准_v3_published-data_2026-07-04.md`
  - `style_anchoring_path_a_over_path_b_2026-07-04.md` (★ 最关键的元教训)
