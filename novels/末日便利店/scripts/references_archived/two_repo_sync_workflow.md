# 双仓库同步工作流 (2026-07-04 焊死)

## 背景

DS-0 的章节产出存在两个 git 仓库, **结构完全不同**, 同步不能直接 push, 必须路径路由.

| 仓库 | 路径 | 结构 | 用途 |
|---|---|---|---|
| memopalace | `/home/admin/.hermes/mempalace/novel/` | `chapters/` 平铺 | DS-0 开发迭代 + codex.json 真源 |
| Riky- | `/home/admin/Riky-/` | `novels/<书名>/chapters/` 按书分类 | GitHub 公开备份 |

**用户访问路径**: GitHub 网页 `https://github.com/zr199139-lab/Riky-/tree/main/novels/起点_亏成首富从外卖开始/chapters`
→ 如果 Riky- 落后 memopalace, 用户刷新看不到新章节.

## 每章 4 步必跑(不可跳过任何一步)

```bash
# Step 1: write_file 写入 memopalace (DS-0 真源)
PLATFORM="起点"  # 或 "番茄"
N=10
TITLE="500万的局"
CONTENT="..."  # 章节正文

# Step 2: 同步 Desktop (用户图形界面)
cp /home/admin/.hermes/mempalace/novel/chapters/${PLATFORM}_第${N}章_${TITLE}.md \
   /home/admin/Desktop/我的网文/${PLATFORM}_亏成首富从外卖开始/chapters/

# Step 3: 同步 Riky- (按书分类路由)
BOOK_DIR=$([ "$PLATFORM" = "起点" ] && echo "起点_亏成首富从外卖开始" || echo "番茄_破财转运牌")
cp /home/admin/.hermes/mempalace/novel/chapters/${PLATFORM}_第${N}章_${TITLE}.md \
   /home/admin/Riky-/novels/${BOOK_DIR}/chapters/

# Step 4: memopalace commit + Riky- commit + push
cd /home/admin/.hermes/mempalace/novel && git add -A && git commit -m "[NOVEL] ${PLATFORM}Ch${N} ${TITLE}"
cd /home/admin/Riky- && git add -A && git commit -m "[NOVEL] ${PLATFORM}Ch${N} ${TITLE} (路径A产出)" && git push origin main
```

**省略任何一步 = 假完成**. 用户原话"为什么git仓库没有找到"= 几乎一定是 Step 4 push 漏跑.

## 漂移检测脚本(每章写完前必跑)

```python
# /home/admin/.hermes/scripts/check_repo_drift.py
import subprocess
import os

def get_head(repo_path):
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True)
    return r.stdout.strip()[:8]

def get_origin_head(repo_path):
    r = subprocess.run(["git", "rev-parse", "origin/main"], cwd=repo_path, capture_output=True, text=True)
    return r.stdout.strip()[:8] if r.stdout.strip() else "无 origin"

def get_uncommitted(repo_path):
    r = subprocess.run(["git", "status", "--porcelain"], cwd=repo_path, capture_output=True, text=True)
    return len(r.stdout.strip().split('\n')) if r.stdout.strip() else 0

mp = "/home/admin/.hermes/mempalace/novel"
rk = "/home/admin/Riky-"

mp_head = get_head(mp)
rk_head = get_head(rk)
rk_origin = get_origin_head(rk)
mp_uncommitted = get_uncommitted(mp)
rk_uncommitted = get_uncommitted(rk)

print(f"memopalace HEAD:    {mp_head}  uncommitted={mp_uncommitted}")
print(f"Riky- HEAD:         {rk_head}  uncommitted={rk_uncommitted}")
print(f"Riky- origin/main:  {rk_origin}")
print()

# 漂移判定
if rk_uncommitted > 0:
    print(f"⚠️ Riky- 有 {rk_uncommitted} 个未提交文件 → 立即跑下方 sync 脚本")
if rk_origin != rk_head:
    print(f"⚠️ Riky- 本地 vs origin 不一致 ({rk_head} vs {rk_origin}) → 立即 push")
if mp_uncommitted > 0:
    print(f"⚠️ memopalace 有 {mp_uncommitted} 个未提交 → 立即 commit")
```

## 反向补救: 把 memopalace 所有未推送章节一次性推到 Riky-

```python
# /home/admin/.hermes/scripts/reverse_sync_to_riky.py
import os, shutil, subprocess

mp = "/home/admin/.hermes/mempalace/novel"
rk = "/home/admin/Riky-"

mapping = {
    '起点': '起点_亏成首富从外卖开始',
    '番茄': '番茄_破财转运牌',
    'qidian': '起点_亏成首富从外卖开始',
    'fanqie': '番茄_破财转运牌',
}

# 同步 chapters
mp_chapters = os.path.join(mp, "chapters")
for fn in os.listdir(mp_chapters):
    src = os.path.join(mp_chapters, fn)
    if not os.path.isfile(src):
        continue
    for prefix, book in mapping.items():
        if fn.startswith(prefix + "_") or fn.startswith("_archive_" + ("qidian" if prefix == "起点" else "fanqie")):
            dst = os.path.join(rk, "novels", book, "chapters", fn)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            print(f"  ✓ chapters: {fn}")
            break

# 同步 diagnostics / drafts / outline / logs (其他副产物)
for sub in ["diagnostics", "drafts", "outline", "logs"]:
    src_dir = os.path.join(mp, sub)
    if not os.path.isdir(src_dir):
        continue
    for fn in os.listdir(src_dir):
        s = os.path.join(src_dir, fn)
        if not os.path.isfile(s):
            continue
        # diagnostics 默认归起点 (双书共享)
        if sub == "diagnostics":
            for book in mapping.values():
                dst = os.path.join(rk, "novels", book, "diagnostics", fn)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(s, dst)
        else:
            dst = os.path.join(rk, sub, fn)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(s, dst)
        print(f"  ✓ {sub}: {fn}")

# Commit + push
subprocess.run(["git", "add", "-A"], cwd=rk)
subprocess.run(["git", "commit", "-m", "[NOVEL-SYNC] 反向补救 memopalace→Riky- 章节同步"], cwd=rk)
r = subprocess.run(["git", "push", "origin", "main"], cwd=rk, capture_output=True, text=True)
print(f"\nPush 结果: {r.stdout}")
print(f"Stderr: {r.stderr}")
```

## 历史漂移事件(2026-07-04 钉)

### 症状
- 章节 Ch5-10 已路径A产出, memopalace HEAD `0ca6a9a` 含 6 个新 commits
- Riky- HEAD 仍停在 `346998c` (7-03 假完成的 Ch7/Ch4 v0.5.4)
- Riky- working tree 27 个文件 untracked + 4 个文件 git 视为 deleted
- 用户 GitHub 刷新: 看不到 Ch5-10

### 根因
- memopalace 路径 = `chapters/起点_第10章_500万的局.md` (平铺)
- Riky- 路径 = `novels/起点_亏成首富从外卖开始/chapters/起点_第10章_500万的局.md` (按书分类)
- 7-03 三处同步的"cp + push"模板没说清这个结构差异
- 写完章节只跑了 memopalace commit, 漏了 Riky- 这一跳

### 修复时长
- 11 秒: `cp 17 章节 + git add + commit + push` 一气呵成
- commit hash: `fd844b8 [NOVEL-SYNC] 章节+大纲+诊断全量同步`
- push 结果: `346998c..fd844b8 main -> main`

### 教训(钉 SKILL.md 顶部)
> 一章一推, 不要攒批. 任何"批量同步" = 假完成陷阱.