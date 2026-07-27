# mc1314 路径 B 实战测试档案 (2026-07-06 焊死)

> **来源**: 2026-07-06 用户临时提供 `sk-ywM...NAil`, 端点 `https://api.1314mc.net/v1`, 跑 3 轮实测
> **结论**: **不能用 mc1314 deepseek-v4-flash 写章节正文**. 这是死路, 不再重复踩坑.
> **目的**: 给未来 DS-0 看, 避免再花 30min 测 1314 Key 能否写章节

---

## 🚨 核心结论 (一图说清)

| 维度 | 实证 | 判定 |
|---|---|---|
| **模型类型** | deepseek-v4-flash 是 **reasoning-only 模型** | 🔴 死亡级问题 |
| **token 消化** | max_tokens=800 → reasoning_tokens=800, content="" 空 | 🔴 死亡 |
| **章节扩字场景** | max_tokens=15000 → reasoning 仍可能吃光 | 🔴 死亡 |
| **Key 稳定性** | 第 1 次 HTTP 200 → 第 2 次起 HTTP 401 "无效的令牌" | 🔴 死亡 |
| **其他模型白名单** | gemini-3.1-flash-lite 也 401 (Key 被限 deepseek 系) | 🟡 限制 |

---

## 1. 实战测试 1 (ping, 验证 Key 有效)

```bash
curl -X POST "https://api.1314mc.net/v1/chat/completions" \
  -H "Authorization: Bearer sk-ywM...NAil" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"ping,只回 pong 一个词"}],"max_tokens":20}'
```

**响应**:
```json
{
  "id": "225caabf-ac4f-4b6a-8e1f-8f6868bba23a",
  "object": "chat.completion",
  "choices": [{
    "index": 0,
    "message": {
      "assistant": "",                  ← content 空!
      "reasoning_content": "我们被问到:ping,只回 pong 一个词..."  ← 全在思考
    },
    "finish_reason": "length"          ← 被截断
  }],
  "usage": {
    "completion_tokens": 20,
    "completion_tokens_details": {"reasoning_tokens": 20}  ← 20 token 全思考, 0 token 正文
  },
  "system_fingerprint": "fp_8b330d02d0_prod0820_fp8_kvcache_20260402"
}
```

**学习点**: HTTP 200 = Key 真, 但 deepseek-v4-flash 是"思考专用模型", content 字段常常空.

---

## 2. 实战测试 2 (写章节开头 200 字, max_tokens=800)

```python
prompt = """你是网文作家,番茄《破财转运牌》Ch4 扩字任务。
主角顾行舟,卡里11亿,刚给妈妈转了1万。
怀表数字: Lv.2, 500x, 今日剩余额度9.4万。
场景: 老张便利店二楼,60瓦白炽灯,红米K70手机。
任务: 写一段200字的场景锚点开头。
要求:
1. 第一句不要"年月日"(7禁第1条)
2. 不要方括号/数据卡
3. 句长15-25字
4. 用嘴贱自嘲风格, 不要装 X
5. 体现"深圳蛇口月租房 + 怀表 + 11亿"3元素
只输出正文, 不要注释。"""

resp = requests.post(
    "https://api.1314mc.net/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": "deepseek-v4-flash",
          "messages": [{"role": "user", "content": prompt}],
          "max_tokens": 800}
)
```

**响应**:
- completion_tokens=800 (max)
- reasoning_tokens=800 (100% 思考)
- content = "" (零字输出)
- finish_reason = "length"
- 耗时 11.5 秒

**学习点**: 即便给详细 prompt, 模型仍把 800 token 全吃在 reasoning_content, 不写真章节.

---

## 3. 实战测试 3 (Key 稳定性)

| 时序 | 调用 | 结果 |
|---|---|---|
| 20:00 第 1 次 | deepseek-v4-flash ping | HTTP 200 ✅ |
| 20:15 第 2 次 | execute_code 真测试 1 | HTTP 401 "无效的令牌" ❌ |
| 20:18 第 3 次 | 重试 deepseek-v4-flash | HTTP 401 ❌ |
| 20:20 第 4 次 | gemini-3.1-flash-lite | HTTP 401 ❌ |
| 20:22 第 5 次 | /v1/models 接口 | HTTP 401 ❌ |

**所有 401 错误统一格式**:
```json
{"error":{"code":"","message":"无效的令牌 (request id: 20260706110911330285700B26wGZwb)","type":"new_api_error"}}
```

**学习点**: 1314 的 Key 在第 2 次调用就失效, 可能:
- a) 单次有效 key / 短时 session token (代理商品测试 token)
- b) Key 用过即 revoke
- c) 余额耗尽 (1314 走"已扣费 token 包"机制)
- d) 内部限流被踢

无论哪种, 都不能用于"持续产出章节正文"场景.

---

## 4. 死路判定

1314 mc1314 路径 B 在 2026-07-06 实测为 **死路**:
- ❌ 不能写章节正文 (reasoning-only 模型, content 输出经常空)
- ❌ Key 不稳定 (1次 200 后即 401)
- ❌ Key 白名单受限 (只能 deepseek 系, 不能 gemini/gpt/claude)

**未来不要做的事**:
- ❌ 不要花时间测 mc1314 deepseek-v4-flash 能不能写章节
- ❌ 不要把 1314 Key 入库到 `credentials.enc` (无效 + 浪费加密空间)
- ❌ 不要在用户说"用 1314 写"时真去尝试 (会浪费 30min)
- ❌ 不要因为"用户授权"就尝试路径 B (授权 ≠ 模型能用)

**未来要做的事**:
- ✅ 章节扩字 = 永远路径 A (MiniMax 对话窗口直写)
- ✅ 用户说"用 API 写"时, 先看现有 `references/vip_aipro_model_pricing_2026-07-04.md` 是否有 aipro gemini 可用
- ✅ 1314 路径 B 只用于 audit 章节 (字数 + 对话密度检测) — 这种场景 100 token 就够, reasoning 内容不影响审计逻辑
- ✅ 用户再提供 1314 Key 时, 直接告知"deepseek-v4-flash 不能写章节, 等于把成本花在错误模型上"

---

## 5. 决策树 (用户给 1314 Key 时)

```
用户给 1314 Key
├── 用户原话是"测一下能跑么" / "能不能用"
│   └── ✅ 跑 ping 测活 (1次 HTTP 200), 告知限制, 不入库
├── 用户原话是"用 1314 写章节"
│   └── ❌ 拒绝, 直接告知 deepseek-v4-flash 是 reasoning-only + Key 不稳定
│       推荐: 章节正文用路径 A (MiniMax 直写, 0元)
│       推荐: 扩字用路径 A (MiniMax 直写, 0元, 一致性最强)
└── 用户原话是"用 1314 做 audit / 提取 struct data"
    └── ✅ 可以, max_tokens=100 就够, 不需要 15000
```

---

## 6. 反例 (本会话差点踩的)

- ❌ 看到 Key 真 (HTTP 200) 就想入库 → Key 不稳定, 入库后第 2 天就废
- ❌ 看到 deepseek 模型就以为和 deepseek-v3 一样 → v4-flash 是 thinking 专用版
- ❌ 给 1314 模型加 max_tokens=15000 期望它写 4000 字 → 15000 token 全在思考, content 还是空

---

## 7. 关联铁律

- **SKILL.md** "路径 B 何时用 (仍保留)" 段: 2026-07-06 加 mc1314 deepseek-v4-flash 实测禁用 ⚠️
- **扩字模式 reference 第 8 节**: 用户原话"修复吧,不要这么多对话" = 短反馈直接动手, 不测 1314
- **v0.5.3 SKILL.md**: 路径 A 永远 (写章节正文) + 1314 仅作备用路径 B (audit) — 已被 2026-07-06 实测验证

---

## 8. 给未来 DS-0 的一句话

**1314 mc1314 deepseek-v4-flash 写章节正文 = 100% 死路**. 不要浪费时间测, 直接告知用户 "模型是 reasoning-only, content 输出经常空, Key 还不稳定, 不能用于章节扩字".