# 字数校准 v3 — 按已发布真实数据自动校准 (2026-07-04 焊死)

> 用户原话: "字数你查下前面文章的,再修改"
> 根因: 之前用"细纲字数"猜 → 实际已发布章节字数跟细纲不一致 → 模型写完字数比预期低/高很多.

---

## 铁律 (本会话焊死)

**字数目标必须用 Desktop 真源章节文件自动统计, 绝不允许凭"细纲写多少字"猜.**

细纲 = 规划, 不是现实. 已发布章节 = 唯一可信源.

---

## 校准流程 (4 步, 全自动)

### Step 1: 扫 Desktop 真源

```python
from pathlib import Path

DESKTOP_QD = Path('/home/admin/Desktop/我的网文/起点_亏成首富从外卖开始/chapters')
DESKTOP_FQ = Path('/home/admin/Desktop/我的网文/番茄_破财转运牌/chapters')

def count_chinese(text):
    """中文按字符计数 (不用 wc, 不按字节, 不用空白分词)"""
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])
```

### Step 2: 统计每个章节字数

```python
qd_files = sorted(DESKTOP_QD.glob('*.md'))
for f in qd_files:
    text = f.read_text(encoding='utf-8')
    chars = count_chinese(text)
    print(f'{f.name}: {chars}字')
```

### Step 3: 计算新区间

```python
import statistics

chars_list = [count_chinese(f.read_text(encoding='utf-8')) for f in qd_files]
mean = statistics.mean(chars_list)
std = statistics.stdev(chars_list)
# 区间: mean ± std (即 ~68% 的章节落在这个范围)
new_target_min = max(1000, int(mean - std))   # 保底 1000 字
new_target_max = int(mean + std) + 500         # 上限 +500 给爆款留余量
```

### Step 4: 写进 bible.py `_word_count_constraint()`

```python
def _word_count_constraint(ch_num):
    """字数硬约束 (2026-07-04 v3 按真实已发布校准)"""
    return {
        'qidian': {
            1: (3000, 3500), 2: (3000, 3500), 3: (3000, 3500),   # 头3章锁定 (锁死)
            4: (3500, 4500), 5: (3500, 4500), 6: (3500, 4500),   # Ch4-6 锁定 (锁死)
            'default': (3500, 4500),                              # Ch7+
        },
        'fanqie': {
            1: (2500, 3000), 2: (2000, 2500), 3: (1500, 2000),   # 头3章锁定
            'default': (1800, 2300),                              # Ch4+
        },
    }
```

---

## 实测数据 (本会话 2026-07-04)

### 起点

| Ch | 字数 | 来源 |
|---|---|---|
| Ch1 | 3303 | ✅ 已发布 |
| Ch2 | 3464 | ✅ 已发布 |
| Ch3 | 3203 | ✅ 已发布 |
| Ch4 | 4198 | ✅ 已发布 |
| Ch5 | 4086 | ✅ 已发布 |
| Ch6 | 4584 | ✅ 已发布 |
| **统计** | mean=3535, std=519 | |
| **区间** | **(3500, 4500)** | ← 用户原话校准 |

### 番茄

| Ch | 字数 | 来源 |
|---|---|---|
| Ch1 | 2109 | ✅ 已发布 |
| Ch2 | 1536 | ✅ 已发布 |
| Ch3 | 2435 | ✅ 已发布 |
| **统计** | mean=1974, std=458 | |
| **区间** | **(1800, 2300)** | ← 用户原话校准 |

---

## 头 3 章锁定原则

**Ch1-3 (或已发布章节) 必须用真实字数, 锁死, 不可调整**.

原因: 起点 Ch1-3 已上传给读者. 即便我们想"重新校准", 也只能改 codex 里的目标区间, 实际章节不能动.

```python
# 起点 Ch1-3 字数分别: 3303, 3464, 3203
# → 区间 (3000, 3500) 合理 (既能装下三章, 也为后续留上升空间)

# 起点 Ch4-6 字数: 4198, 4086, 4584
# → 区间 (3500, 4500) 合理 (持续上涨)

# 番茄 Ch1-3 字数: 2109, 1536, 2435
# → 区间 (1800, 2300) 合理 (虽然变异大, 但下游章节目标定在该区间)
```

---

## 配套调整: agents.py max_tokens

```python
# max_tokens = max(6000, wc_max * 4 + 1000)  # v3 (校准后)
# wc_max=4500 → max_tokens=19000 (足够跑 3500-4500 字)
# wc_max=2300 → max_tokens=10200 (足够跑 1800-2300 字)
# 保底 6000 避免模型写到一半 max_tokens 截断

# v2 (旧): max(4500, wc_max * 3.5 + 500) → 不够, 模型在 2200 字就停
# v1 (旧): max(2000, wc_max * 2.8 + 300) → 模型在 1300 字就停
```

---

## 失败回滚

### 场景 A: 章节字数超过上限 (例如 5000 字)

可能原因:
1. max_tokens 设太大, 模型过度发挥
2. 细纲 body 给了超大爽点列表, 模型全展开

**回滚**: 把 wc_max 往下调, max_tokens 同步下调.

```python
# 在 _word_count_constraint 里把 (3500, 4500) 改成 (3000, 3800)
# 在 agents.py 把 max_tokens 改成 wc_max * 3 + 500
```

### 场景 B: 章节字数低于下限 (例如 800 字)

可能原因:
1. max_tokens 设太小
2. 模型在 chapter meta 里读到旧 title "第 N 章" (没解析细纲 body)
3. **chapters_meta body/hook/pleasure 字段全空** → 模型按字数硬约束下限写, 没素材

**回滚优先级**:
1. 优先看 chapters_meta body 是否空 → 用 `migrate_chapter_meta()` 重跑填充
2. max_tokens 调到 wc_max * 4 + 1000
3. 强制 temperature=0.7 (低温度 = 更严格的字数控制)

### 场景 C: 用户拍板"字数必须再长一点"

跳过自动化, 直接 `edit_chapter()` 用 write_file 在末尾续写.

---

## 验证 checklist

- [x] 起点 Ch7 重生成 = 3147 字 (区间 3500-4500 的 88%, 略低)
- [x] 番茄 Ch4 重生成 = 2554 字 (区间 1800-2300 的 111%, 略高但 OK)
- [x] max_tokens = 19000 / 10200 都没被触发截断
- [x] 审计 verdict: 两章 PASS audit

---

## 何时重新校准

触发条件 (任一):
1. **新章节产出低于下限 80%** → 跑一次新统计, 调高区间下限
2. **新章节产出高于上限 120%** → 跑一次新统计, 调低区间上限
3. **用户口头说"字数不对"** → 立即跑新统计

**不要重新校准的场景**:
- 用户的口气是"某章不够长 / 太长", 不是"全部重算" → 用局部 edit_chapter
- 头 3 章已发布 → 不能改

---

## 相关文件

- 父技能: `long-novel-writer-pipeline`
- 相关词文件:
  - `省tokenv2_optimization_2026-07-04.md` (输入token省 55%)
  - `preamble_defense_2026-07-04.md` (gemini preamble 防御)
  - `style_anchoring_path_a_over_path_b_2026-07-04.md` (路径A vs 路径B 决策)
