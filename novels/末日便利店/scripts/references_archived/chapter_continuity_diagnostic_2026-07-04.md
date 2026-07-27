# 章节连贯性诊断 — 起点Ch7 / 番茄Ch4 双失败报告

**生成时间**: 2026-07-04
**触发**: 用户原话 "检查下刚刚为什么会卡, 起点第7章和番茄第4章看下是否需要重新写, 当它们不存在"
**结论**: 两章必须当不存在重写, 路径B(v0.5.4)失败已确认

---

## 🎯 用途

**任何章节产出后,用户表达以下任一信号时,立即跑本诊断**:
- "卡" / "卡了" / "慢" / "还没好" → 怀疑路径B 失败
- "当它们不存在" / "当不存在重写" → 强制走本流程
- "剧情不连贯" / "时间线不对" / "数字错了" / "人名漂了" → 失败已确认,走本流程
- "这章跟前面接不上" → 走本流程

---

## 🩺 诊断流程 (5 步)

### Step 1 — 卡顿原因定位 (3 个并行探针)

```bash
# 1.1 看有没有卡死的进程
ps aux | grep -E 'novelforge|python.*chapter|aipro|cron' | grep -v grep

# 1.2 看 git log 最近 10 次 commit, 找"反复改 prompt 没真正产出"的痕迹
cd /home/admin/.hermes/mempalace/novel
git log --oneline -20

# 1.3 看 chapters 目录最近修改文件,确认哪些章节落盘了
ls -lat /home/admin/.hermes/mempalace/novel/chapters/ | head -10
ls -lat /home/admin/Desktop/我的网文/{起点|番茄}/chapters/ | head -10
ls -lat /home/admin/Riky-/novels/{起点|番茄}/chapters/ | head -10
```

**判定**:
- 没有 novelforge 进程在跑 + git log 有 3+ 次 "v0.5.x" 类提交 = 路径B 反复失败, 上一版"完成"是假完成
- 章节文件落盘了但 git commit 标记"完成" = 高概率假完成,必须审计剧情

### Step 2 — 真源定位 (从 Desktop 读原文, 不要读 mempalace 副本)

```bash
# 2.1 列出 Desktop 用户真源章节 (用户已上传的)
ls /home/admin/Desktop/我的网文/起点_亏成首富从外卖开始/chapters/
ls /home/admin/Desktop/我的网文/番茄_破财转运牌/chapters/

# 2.2 读取 ChN-1 末段 (前 60 行) 提取末态真值
for ch in 起点_第[1-6]章_*.md; do
    echo "=== $ch ==="
    tail -60 "/home/admin/Desktop/我的网文/起点_亏成首富从外卖开始/chapters/$ch"
done
```

**提取末态清单** (5 维):
- 时间 (Day X / 7月X日 / 时点)
- 现金 (账户余额 / 累计亏损 / 累计返利)
- 等级 (Lv.X / 倍数 Xx / 日限额)
- 人物位置 (主角住哪 / 反派在哪 / 女主在哪)
- 已发生事件 (谁欠谁钱 / 谁撤诉 / 谁登报)

### Step 3 — 受审章节 6 维审计 (从已落盘 .md 读,不要只看 codex)

| 维度 | 检查项 | 跑法 |
|---|---|---|
| **时间线** | ChN 开头时间是否接 ChN-1 末段 | grep "月\|日\|Day\|点" |
| **数字** | 累计返利/余额/倍数 vs codex.current_state | grep "余额\|累计\|倍数\|Lv\." |
| **人物位置** | 主角/反派/女主位置 vs ChN-1 末段 | grep "在\|回\|去\|开" |
| **立场反转** | 反派/女主行为是否跟前文矛盾 | grep "答应\|拒绝\|撤诉\|威胁" |
| **剧情节奏** | 一章内塞了多少剧情节点 (建议 ≤3) | grep "^第\|^$\|——" |
| **大纲对照** | 章节事件是否在卷一细纲 ChN 的预期内 | 读 `outline/起点_卷一细纲.md` |

### Step 4 — 致命错误清单 (任意一条 → 整章当不存在)

**Ch7 失败案例 (起点) 8 条致命**:
1. 时间线接不上 (Ch6=7月6日23:00 vs Ch7 含混)
2. 王大龙立场反转 (Ch6 主角要500万 → Ch7 王大龙要主角500万)
3. 系统倍数瞎编 (500x 不存在于起点规则)
4. 人物凭空出现 (暖暖/江北新区 没在 Ch1-3)
5. 节奏爆表 (7 个剧情节点同章)
6. codex current_state 漂移 (返利数对不上 Ch6 末)
7. 暧昧线推进过早 (周映雪 Ch7 出浴 vs Ch95 才加盟)
8. 副作用未解锁 (白浴袍是 Ch30 之后才出现的情节)

**Ch4 失败案例 (番茄) 4 条致命**:
1. 时间线跳回 (Ch3=Day 3 升级 Lv.2 → Ch4 写"Day 2")
2. 数字自相矛盾 (累计返利 vs 妈妈账户差额)
3. 业务内容冲突 (Ch3 电子厂 vs Ch4 便利店)
4. 副作用时间错位 ("劝你省钱" Ch3 末 16:42 才解锁 vs Ch4 立刻用)

### Step 5 — 输出诊断报告 (3 处同步)

```bash
# 报告落盘位置
/home/admin/.hermes/mempalace/novel/diagnostics/ch{N}_ch{M}_audit_{日期}.md
/home/admin/Desktop/我的网文/{起点|番茄}/diagnostics/同上
/home/admin/Riky-/novels/{起点|番茄}/diagnostics/同上

# git commit (本地 + 远端备份)
cd /home/admin/.hermes/mempalace/novel
git add diagnostics/
git commit -m "[DIAGNOSTIC] ChN/ChM 连贯性审计: 全部失败, 当不存在重写"
```

**报告格式** (13KB 模板已验证):
1. 🚨 终极结论 (1-2 行)
2. 卡的原因 (git log 时间线 + 5 条结构性问题)
3. 起点/番茄 各章节 致命错误清单
4. 统一性 / 大纲对照
5. 修复方案 (路径A vs 路径B)
6. 下一步动作 (用户拍板)

---

## 🚨 反模式 (本次踩坑清单)

### 反模式 1: 看 git log 末行"完成"就汇报
**症状**: v0.5.4 git commit 写 `[NovelForge v0.5.4] 4件套达标`, 我就汇报"完成了"
**真相**: git commit ≠ 质量验收. 章节 .md 真读了才知剧情崩.
**缓解**: 任何"完成"话术前, 必须**在对话窗口展示真实剧情摘要**给用户.

### 反模式 2: 改 5 版 prompt 没改路径
**症状**: v0.3 → v0.5.4 共 5 次 commit 都在改 prompt 缺陷, 没一次说"放弃路径B"
**真相**: 路径B 章节 = 高失败率, 不是 prompt 能修的. 是 LLM 心算 vs codex 喂入的根本矛盾.
**缓解**: 见 novelforge-architecture SKILL.md "路径 B 章节正文已确认为高失败率模式" 5 条结构性问题.

### 反模式 3: 把"字数达标"当完成标志
**症状**: v0.5.1/v0.5.2 改 max_tokens 保底 4500/系数 ×3.5 → 字数达标 → 以为完成
**真相**: 字数只是字数, 剧情 / 数字 / 承接 / 人物位置 / 大纲一致 都没验.
**缓解**: 任何"完成"必须跑本诊断 5 步流程.

### 反模式 4: 把 archive 章节留在 chapters/ 干扰审计
**症状**: Ch7/Ch4 当不存在后, 没标 `__archive`, 后续 audit 还会扫到.
**真相**: audit 会从 chapters/ 目录扫描, 失败章节会让后续 audit 报"历史违规".
**缓解**: archive 文件必须 `__archive_v0.5.4` 后缀, audit 加 glob 排除 `*__archive*`.

### 反模式 5: 路径B 写章节, DS-0 不读真源
**症状**: bible.pre_read_checklist() 说"读最近 3 章原文", 但实际从 mempalace 副本读 (该副本 ch6/ch3.md 不存在).
**真相**: 真源 = Desktop `番茄_第{N}章_xxx.md`. mempalace/novel/chapters/ 只是开发副本, 不全.
**缓解**: agents.py `pre_read_checklist()` 改读 `os.path.expanduser('~/Desktop/我的网文/{book}/chapters/')`, fallback 才读 mempalace.

---

## 🛠️ 给未来 DS-0 的快速诊断 (90 秒跑完)

```python
# 任何章节产出后必跑
import os, re
from hermes_tools import read_file

BOOK = '起点'  # 或 '番茄'
CH_N = 7
CH_FILE = f"/home/admin/Desktop/我的网文/{BOOK}/chapters/...第{CH_N}章_*.md"
PREV_FILE = f"/home/admin/Desktop/我的网文/{BOOK}/chapters/...第{CH_N-1}章_*.md"

# 1. 读前章末态
prev = read_file(PREV_FILE)
prev_tail = prev.split('\n')[-60:]
prev_time = [l for l in prev_tail if re.search(r'\d+月|\d+日|Day|点', l)]
prev_state = [l for l in prev_tail if re.search(r'余额|累计|倍数|Lv\.', l)]

# 2. 读本章前 60 行
cur = read_file(CH_FILE)
cur_head = cur.split('\n')[:60]
cur_time = [l for l in cur_head if re.search(r'\d+月|\d+日|Day|点', l)]
cur_state = [l for l in cur_head if re.search(r'余额|累计|倍数|Lv\.', l)]

# 3. 时间漂移检测
print(f"前章末段时间: {prev_time[-1] if prev_time else '未提取'}")
print(f"本章开头时间: {cur_time[0] if cur_time else '未提取'}")
if prev_time and cur_time:
    print("⚠️ 时间漂移需人工判断")

# 4. 数字漂移检测
print(f"\n前章末段数字: {prev_state[-1] if prev_state else '未提取'}")
print(f"本章开头数字: {cur_state[0] if cur_state else '未提取'}")
if prev_state and cur_state:
    prev_lv = re.search(r'Lv\.\d+', prev_state[-1])
    cur_lv = re.search(r'Lv\.\d+', cur_state[0])
    if prev_lv and cur_lv and prev_lv.group() != cur_lv.group():
        print(f"🚨 Lv 漂移: 前章 {prev_lv.group()} → 本章 {cur_lv.group()}")

# 5. 节奏爆表检测 (一章 >3 个剧情节点 = 警告)
scene_markers = [l for l in cur.split('\n') if re.match(r'^第[一二三四五六七八九十]|^——|^\d{2}:\d{2}', l)]
print(f"\n本章场景切换数: {len(scene_markers)} ({'🚨 爆表' if len(scene_markers) > 5 else '✅ 正常'})")
```

---

## 📚 相关文档

- `novelforge-architecture/SKILL.md` "路径 B 章节正文已确认为高失败率模式" 章节
- `novelforge-user-machine-bridge/SKILL.md` "❌ 路径B 章节正文 = 当不存在重写" 反例 18
- `/home/admin/.hermes/mempalace/novel/diagnostics/ch7_ch4_audit_2026-07-04.md` 本次诊断报告完整版 (13KB)