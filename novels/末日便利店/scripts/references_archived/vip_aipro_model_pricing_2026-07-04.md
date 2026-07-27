# vip.aipro.love 模型价格速查 (2026-07-04 抓取)

**适用场景**: 网文写作选模型时,不知道该选哪款/哪家便宜。

## ⚡ 结论先行

**vip.aipro.love = 精品三巨头路线** (Anthropic / Google / OpenAI),**没有国产廉价款**。
❌ **没有** DeepSeek / Qwen / GLM / 混元 / 豆包
✅ **只有** Claude / Gemini / GPT 三家

## 🏆 最便宜档 (按 input/output 综合)

| 排名 | 模型 | 输入倍率 | 输出倍率 | 适合小说场景 |
|------|------|---------|---------|------------|
| 🥇 | **gemini-3.1-flash-lite** | 1× | **4×** | 性价比之王 |
| 🥈 | gemini-3-flash | 1× | 6× | Flash 主力 |
| 🥉 | gemini-3-flash-preview | 1× | 6× | 同等 |
| 4️⃣ | gemini-3.1-pro-preview | 1× | 6× | Pro 预览 |
| 5️⃣ | gemini-3.5-flash-low | 1.5× | 6× | |
| 6️⃣ | gemini-pro-agent | 1.5× | 6× | |
| - | claude-sonnet-4-6 | 2× | 5× | 质量中档 |
| - | claude-opus-4-6 | 2.5× | 5× | 文学性强 |
| - | gpt-5.5 | **4×** | **8×** | 最贵 |

## 💡 网文场景选款建议

**首选**:`gemini-3.1-flash-lite`
- 输入 1× 是最低 (小说 prompt 长 = 省钱大头是输入)
- 输出 4× 也是最低 (写章节输出省钱)
- Gemini 3 系列长上下文无敌,写大纲/章节/审计都够用

**质量升级**: `claude-sonnet-4-6` (2×/5×) — 关键头三章/高潮章用
**绝对便宜**对比 mc1314: mc1314 的 deepseek-v4-flash 仍比 aipro 最便宜的还便宜,但 aipro 的 gemini-3.1-flash-lite 在"中英双语长文"质量上明显更强

## 📐 倍率换算公式

aipro 用"倍率"计算价格,**1× = 多少元需要查用户账户的实际组比率**:
- default 组: group_ratio = 1.5 (贵 50%)
- vip 组: group_ratio = 1.0 (原价)

**当前用户(从 config.yaml 看)在 default 组**,所以实际成本 = 倍率 × 1.5 ÷ 100 元/倍单位(具体看后台)。
简易对比:**两个模型谁 input_ratio + completion_ratio 加起来小,谁便宜**。

## 🔧 抓取方法 (无需登录!可复用)

```bash
# 1. 拿完整价格列表(匿名,无需 token)
curl -sL https://vip.aipro.love/api/pricing | python3 -m json.tool

# 2. 输出字段说明:
#    model_name:  模型 ID (调 API 时用这个)
#    vendor_id:   1=Anthropic / 2=Google / 3=OpenAI
#    model_ratio: 输入倍率
#    completion_ratio: 输出倍率
#    enable_groups: ['default'] / ['vip'] 看用户在哪组
```

**关键点**: `/api/pricing` **不需要 Authorization header**,匿名可拉。这是用户的隐藏便利入口,**未来用户余额变化或新模型上线,这个 endpoint 是首选数据源**。

**注意**: `/api/v1/models` 走的是 OpenAI 格式(**404**),"API Key 验证用"端点是 `/v1/chat/completions`(**要 Key**)。不要混淆:
- `/api/pricing` → 价格 (匿名 ✅)
- `/v1/chat/completions` → 调用 (要 Key 🔑)
- `/api/models` 和 `/api/v1/models` → 都报错 (❌)

## 🆚 aipro vs mc1314 vs deepseek 站位对比

| 端点 | 风格 | 网文适配 |
|------|------|---------|
| **mc1314 (api.1314mc.net)** | 56 个模型全家桶(deepseek-v4-flash/Qwen/Kimi 全有) | **最便宜量产章节首选** |
| **aipro (vip.aipro.love)** | 17 个精品(Claude/Gemini/GPT) | **质量/逻辑审计+头三章** |
| **deepseek (原生)** | deepseek-v3 系列 | 备用 |

**实战组合**:
- 大纲 + 设定 + 审计 → mc1314 deepseek-v4-flash (便宜量大)
- 头三章 + 高潮章 → aipro claude-sonnet-4-6 或 gemini-3.1-flash-lite (质量强)
- 量产章节 → mc1314 deepseek-v4-flash (单价最低)
- 紧急/批产 10+ 章 → mc1314 qwen3-235b (中英平衡)

## 📌 用户偏好对齐 (从 memory 摘)

- 用户主控制台是 mc1314 (api.1314mc.net)
- aipro (vip.aipro.love) 余额常被烧光,**做主力备选**
- 写代码强制 Claude Opus 4.7 (aipro)
- 日常对话 DeepSeek
- 代码速度优先,不省 AI 费用
- 网文写作 MiniMax-M3 直写主路径 (0 元,主对话窗口)

**含义**: 网文写作时,**aipro 不是第一选择**。aipro 第一是 mc1314,第二是直写。如果 aipro 当主力是用户的临时切换(本会话用户的指令"小说先用这里的模型"),就用 `gemini-3.1-flash-lite` 当主力模型,能省 50% 成本。

## 触发条件

- 用户说"用 aipro/哈基米/vip.aipro 写小说" → 加载本文件 → 默认 gemini-3.1-flash-lite
- 用户问"哪家便宜" / "什么模型适合写小说" → 加载本文件
- 用户 aipro 余额耗尽 → 提醒改 mc1314 deepseek-v4-flash
- 列出 aipro 模型表时 → 引用本文件而非再 fetch

## 抓取快照 (2026-07-04 实时数据)

```json
{
  "total_models": 17,
  "group_ratio": {"default": 1.5, "vip": 1.0},
  "vendors": [
    {"id": 1, "name": "Anthropic"},
    {"id": 2, "name": "Google"},
    {"id": 3, "name": "OpenAI"}
  ],
  "models": [
    "claude-haiku-4-5-20251001", "claude-opus-4-6", "claude-opus-4-6-20260201",
    "claude-opus-4-6-thinking", "claude-opus-4-7", "claude-opus-4-8",
    "claude-sonnet-4-6",
    "gemini-3-flash", "gemini-3-flash-agent", "gemini-3-flash-preview",
    "gemini-3.1-flash-lite", "gemini-3.1-pro-high", "gemini-3.1-pro-preview",
    "gemini-3.5-flash-low", "gemini-pro-agent",
    "gpt-5.4", "gpt-5.5"
  ]
}
```

**注**: 价格会随时间变化,验证以最新 `curl https://vip.aipro.love/api/pricing` 为准。
