# 章节命名 + 文件管理铁律(2026-07-06 焊死 — 本会话实踩)

> **触发**: 本会话起点 Ch11 写了 3 个文件名版本 — v1"苏婉清起诉"(剧情错位)、v2"春风开会"(剧情错位)、v3"假装外卖"(最终)。Ch12 也叫"假装外卖",导致 Ch11/Ch12 重名混乱。

> 这是 v5 reference `扩字模式_破折号堆与剧情错位_2026-07-06.md` 的补充 — 专门讲章节命名 + 文件管理。

---

## 🚨 核心铁律:1 章 1 文件, 章节名 1 章对应 1 唯一核心词

### 反例(本会话起点 Ch11 实踩)

```
v1: 起点_第11章_苏婉清起诉.md       ← 剧情错位 (Ch8 已发生)
v2: 起点_第11章_春风开会.md         ← 剧情错位 (细纲没安排)
v3: 起点_第11章_假装外卖.md         ← 最终通过
Ch12: 起点_第12章_假装外卖.md       ← ❌ 重名!跟 Ch11 一字不差
```

**问题**:
- v1/v2 文件被 `rm` 但 git 历史保留, 用户视角看到 3 个版本历史
- Ch11/Ch12 重名 → 用户 `ls chapters/` 无法区分
- git `git log --all` 会看到 3 个 Ch11, 但当前工作区只有 v3

### 修复铁律:章节命名 3 约束

1. **1 章 1 文件**: `起点_第N章_<2-4字核心词>.md` (番茄同样格式)
2. **章节名唯一**: N 章内的章节名**绝不与前 N-1 章或后续 1 章重复**。即使剧情相似,核心词必须区分。
3. **章节名与剧情 1:1 对应**: 章节名 = 本章 1 个核心剧情关键词 (≤ 4 字)

### 章节命名实战模板

```
起点_第N章_<2-4字核心词>.md

模板:
- 核心动词: 假装 / 周氏合作 / 母亲到 / 王大龙登场 / 假装外卖
- 核心名词: 春风开会 / 假装外卖 / 500万的局 / 父子反目 / 汉庭府堵人
- 核心结果: 母亲到 / 王大龙受审 / 苏婉清起诉 / 春风开会

反例 (不要这样命名):
- "杂项 / 待定 / 续写 / 试写 / v1"  ← 章节名必须有剧情含义
- "本章 / 本章续写 / 第一稿"       ← 章节名必须有具体场景
- 跟前一章 / 后一章重名           ← 章节名必须 1 章 1 词
```

### 重写章节的处理流程

如果章节剧情错位需要重写(本会话 Ch11 v1→v3):

```
Step 1: read_file 旧章节内容 (备份到内存)
Step 2: os.remove() 旧文件
Step 3: write_file() 新内容到新章节名 (1 章 1 文件)
Step 4: git rm + git add + git commit (1 个新文件, 不是覆盖)
```

**反例**: 用 `write_file` 覆盖旧章节名 — 看起来文件改了, 但 git diff 会显示混乱,而且 git 历史里旧剧情还在。

### 章节重名检测脚本(必跑)

```python
import os, glob, re

def check_duplicate_chapter_names(book_dir):
    """章节重名检测 — 写章节前必跑"""
    files = glob.glob(os.path.join(book_dir, 'chapters', '*.md'))
    # 文件名格式: {book}_第N章_{core}.md
    chapters = {}  # N -> set of cores
    for f in files:
        basename = os.path.basename(f)
        m = re.match(r'.*_第(\d+)章_(.+)\.md', basename)
        if not m:
            continue
        n = int(m.group(1))
        core = m.group(2)
        chapters.setdefault(n, set()).add(core)

    issues = []
    # 检查每个 N 是否有多个 core (重写痕迹)
    for n, cores in chapters.items():
        if len(cores) > 1:
            issues.append(f"⚠️ Ch{n} 有 {len(cores)} 个版本: {cores} — 应只保留 1 个")

    # 检查是否有 N 和 M 共用 core (重名)
    all_cores_by_name = {}
    for n, cores in chapters.items():
        for c in cores:
            all_cores_by_name.setdefault(c, []).append(n)
    for core, ns in all_cores_by_name.items():
        if len(ns) > 1:
            issues.append(f"⚠️ 章节名 '{core}' 在 Ch{ns[0]} 和 Ch{ns[1]} 都用了")

    return issues

# 用法
issues = check_duplicate_chapter_names('/home/admin/Desktop/我的网文/起点_亏成首富从外卖开始')
if issues:
    for i in issues:
        print(i)
    print("→ 必修: rm 旧版本 + 保留最新 1 个")
else:
    print("✅ 章节命名无重名")
```

### 真实案例:2026-07-06 本会话起点 Ch11

```
修复前:
  起点_第11章_苏婉清起诉.md (v1, 错位)
  起点_第11章_春风开会.md (v2, 错位)
  起点_第11章_假装外卖.md (v3, 通过)
  起点_第12章_假装外卖.md (Ch12 也叫假装外卖, 重名)

修复后:
  起点_第11章_假装外卖.md (Ch11 唯一)
  起点_第12章_周氏合作.md (改名字, 不重名)
  起点_第13章_母亲到.md (Ch13 唯一)
```

修复命令:
```bash
# 删除旧 Ch11 (v1/v2) — 已经在 Ch11 v3 write_file 时手动删了
# 删除 Ch12 重名 — 改名为周氏合作
mv chapters/起点_第12章_假装外卖.md chapters/起点_第12章_周氏合作.md
# 同步 dist/
mv dist/起点_第12章_假装外卖.txt dist/起点_第12章_周氏合作.txt
# 同步 Git 真源
mv /home/admin/Riky-/novels/起点_亏成首富从外卖开始/chapters/起点_第12章_假装外卖.md \
   /home/admin/Riky-/novels/起点_亏成首富从外卖开始/chapters/起点_第12章_周氏合作.md
```

---

## 🚨 文件清理:写完一章必做的 4 个清理动作

每次写完一章,必跑 4 个清理:

```bash
# 1. 删除旧的版本 (按剧情错位判定)
ls chapters/ | grep "第11章"  # 看是否有多个版本

# 2. 检查 git 工作区状态
cd /home/admin/Riky-/ && git status --short
# - 看是否有未跟踪的孤儿文件
# - 看是否有删除状态但没 commit 的文件 (dist/ 假象)

# 3. 同步双路径 (Desktop + Git 真源)
diff chapters/番茄_第N章_xxx.md /home/admin/Riky-/novels/番茄_破财转运牌/chapters/番茄_第N章_xxx.md
# 不一致 → cp 同步

# 4. 转 .txt 到 dist/
sed -e 's/\*\*//g' -e 's/^# //' -e 's/^---$//' \
    chapters/番茄_第N章_xxx.md > dist/番茄_第N章_xxx.txt
```

---

## 反例(本会话真实踩雷)

### 反例 1:Ch11 v1→v2→v3 写了 3 个文件再删 2 个

- ❌ 用户视角 `ls chapters/` 看到 3 个 Ch11, 不知道哪个是真
- ❌ git `git log` 会看到 3 次 Ch11 commit, 旧剧情(苏婉清起诉/春风开会) 还在 git 历史
- ✅ 正做: 第 1 次写就**先写剧情大纲 1 行**,再 write_file; 中途发现错位 → **rm 旧 + write_file 新**,不留 v1

### 反例 2:Ch11/Ch12 都叫"假装外卖"

- ❌ `ls chapters/` 看到 `起点_第11章_假装外卖.md` + `起点_第12章_假装外卖.md`, 章节名一字不差, **章节名等于不存在**
- ❌ 用户在文件管理器里排序, 第 11 章和第 12 章章节名一致 → 选中错误
- ✅ 正做: **章节名用不同核心词** — Ch11 = 假装外卖 (动作), Ch12 = 周氏合作 (结果)

### 反例 3:Ch13 一直叫"母亲到",但旧版本"母亲到"已经存在,Ch14 又叫"母亲到"

- ❌ Ch13/Ch14 章节名重名 → 同上
- ✅ 章节名规划: v0 写章节大纲前,**先列 N 章章节名清单**,确保 1 章 1 词

---

## 📌 章节命名规划 SOP(写 N 章前必做)

```python
# v0 步骤: 列章节名清单, 写 N 章前必做

chapter_titles = {
    11: '假装外卖',     # Ch11 = 4 个员工穿美团服
    12: '周氏合作',     # Ch12 = 周映雪谈合作
    13: '母亲到',       # Ch13 = 何秀兰到汉庭府
    14: '王大龙报复',   # Ch14 = 3 花臂男骚扰
    15: '周映雪约会',   # Ch15 = 周映雪约会主角
    # ... N 章
}

# 校验 1: 1 章 1 词
titles = list(chapter_titles.values())
assert len(set(titles)) == len(titles), "❌ 章节名重复"

# 校验 2: ≤ 4 字核心词
for n, t in chapter_titles.items():
    assert len(t) <= 4 or t == chapter_titles[n], f"❌ Ch{n} 章节名 '{t}' > 4 字"

# 校验 3: 跟细纲对得上
# (查细纲文件, 确认每章细纲有对应事件)
```

---

## 🎯 总结

**1 章 1 文件 + 1 文件 1 核心词 + 1 核心词跟剧情 1:1 对应 + 重写必 rm 旧** — 4 条铁律,1 条都不能破。

下次 DS-0 写新章节前,**先**:
1. 列章节名清单 (v0 步骤)
2. 跑 `check_duplicate_chapter_names` 校验
3. 写大纲 (1 行剧情摘要)
4. write_file 1 次到位, **不重写**(避免 v1→v2→v3 反复)
5. 写完跑 4 个清理动作 (git status / diff / sed / cp)

写错章节剧情 → **rm + write_file 1 次到位**,**不要 v1→v2→v3 重命名**(本会话 Ch11 踩雷)。