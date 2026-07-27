# 三处同步失效恢复协议 (2026-07-04 焊死)

**触发**: `git status` 出现 ≥ 5 个 untracked + ≥ 3 个 deleted, 或章节数量三处不一致

## 三处结构差异 (致命)

| 位置 | 路径模式 | git 历史 |
|---|---|---|
| memopalace | `chapters/起点_第N章_xxx.md` (平铺) | 独立 |
| Desktop | `我的网文/起点_xxx/chapters/起点_第N章_xxx.md` (按书) | 无 git |
| Riky- | `novels/起点_xxx/chapters/起点_第N章_xxx.md` (按书) | 独立 |

**关键**: memopalace 和 Riky- **不能直接 cherry-pick 或 reset**, 因为结构 + 历史都不同。

## 真实复现 (2026-07-04 会话起点)

```
Riky- HEAD = 346998c (假完成 v0.5.4 Ch7/Ch4)
memopalace HEAD = 0ca6a9a (包含 Ch5-10 路径A真产出)
差异: Riky- 落后 memopalace 5 commits

但: memopalace 仓库里 chapters/ 是平铺, Riky- 是 novels/<书>/chapters/
→ 单纯 reset --hard memopalace/main 后, Riky- 的 novels/ 全空 (untracked)
```

## 7 步恢复协议 (已验证)

### Step 1: 指纹盘点 (确认真实状态)
```python
import os, hashlib
def md5(p):
    if not os.path.isfile(p): return None
    return hashlib.md5(open(p,'rb').read()).hexdigest()

def chapter_meta(p):
    if not os.path.isfile(p): return None
    with open(p, encoding='utf-8') as f: c = f.read()
    return sum(1 for ch in c if '\u4e00' <= ch <= '\u9fff')

mp = "/home/admin/.hermes/mempalace/novel/chapters"
paths = {
    "mp": mp,
    "dt_q": "/home/admin/Desktop/我的网文/起点_亏成首富从外卖开始/chapters",
    "dt_f": "/home/admin/Desktop/我的网文/番茄_破财转运牌/chapters",
    "rk_q": "/home/admin/Riky-/novels/起点_亏成首富从外卖开始/chapters",
    "rk_f": "/home/admin/Riky-/novels/番茄_破财转运牌/chapters",
}

# 对每个文件: 比对 5 处的 md5 + 字数
all_files = set()
for p in paths.values(): all_files |= set(os.listdir(p))
for fn in sorted(all_files):
    h = {k: md5(os.path.join(p, fn)) for k, p in paths.items()}
    m = {k: chapter_meta(os.path.join(p, fn)) for k, p in paths.items()}
    distinct = set(v for v in h.values() if v)
    flag = "✅" if len(distinct) == 1 else f"❌{len(distinct)}版本" if distinct else "⚠️缺失"
    print(f"{fn}  [{flag}]  " + " | ".join(f"{k}={m[k]}字" for k in paths))
```

### Step 2: 决策保留版本
**优先级**: 
1. Desktop 版本 (真源, 用户最可能打开看的)
2. memopalace 工作区最新版 (开发副本, 一般跟 Desktop 一致)
3. Riky- 已 commit 版 (历史, 通常较旧)

**字数 / 内容更完整的优先**, 即使修改时间不是最新

### Step 3: 识别废稿 / 重复
按 4 类处理:
1. **同章多版本**: 保留字数最大 + 内容最完整, 其余归档 `_archive_<书>_<章>_2026-07-04.md`
2. **命名漂移** (`qidian_xxx` vs `起点_xxx`): 用 `起点_xxx` 命名统一
3. **错位** (番茄废稿在起点目录): 直接删
4. **rk 残留** (内容跟 archive 同字节): 删 rk 的, 保留 archive

### Step 4: 三处文件级同步 (NOT git level)
```python
import shutil
KEEP = [...]  # 保留文件列表
DELETE = [...] # 删除文件列表

for fn in KEEP:
    for p in [mp, dt_q, dt_f, rk_q, rk_f]:
        dst = os.path.join(p, fn)
        # 找任一存在的源文件复制过去
        for src_p in paths.values():
            src = os.path.join(src_p, fn)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                break

for fn in DELETE:
    for p in [mp, dt_q, dt_f, rk_q, rk_f]:
        f = os.path.join(p, fn)
        if os.path.isfile(f):
            os.remove(f)
```

### Step 5: 两个仓库分别 commit
```bash
# memopalace
cd /home/admin/.hermes/mempalace/novel
git add -A
git commit -m "[NOVEL-CLEANUP] 删废章节+三处同步 (mm/dd/yyyy)
删除: qidian_第N章_xxx.md (命名错位)
保留: 起点_第N章_xxx.md (正确命名)
同步: 起点Ch1-6 + 番茄Ch1-3 (原本只在 Desktop)"

# Riky-
cd /home/admin/Riky-
git add -A
git commit -m "[NOVEL-CLEANUP] 同上 (缩短版)"
git push origin main
```

### Step 6: 验证三处一致
```python
# 跑同一个指纹盘点脚本, 期望: 所有 distinct_hashes == 1
```

### Step 7: 清理 stash + 临时 remote
```bash
cd /home/admin/Riky- && git stash drop
cd /home/admin/Riky- && git remote remove memopalace  # 如果用了 memopalace 作为临时 remote
```

## 验证 Checklist

- [ ] `git status` 在 mp / Riky- 都显示 "working tree clean"
- [ ] `git log -3` 显示最近的 sync commit
- [ ] 5 处路径文件数完全相同 (mp 22 / 其他 11+11)
- [ ] md5 抽查 5 个文件, 三处完全一致
- [ ] GitHub 网页能看到最新 commit

## 失败模式 → 修复映射

| 症状 | 根因 | 修复 |
|---|---|---|
| Riky- `git status` 显示 `novels/` 是 untracked | reset --hard memopalace/main 后结构不匹配 | `git reset --hard 346998c` 回到自己历史, 然后只 copy 文件不改 history |
| `git push` 失败 "non-fast-forward" | 远端有新 commit | `git pull --rebase` 或 `git push --force-with-lease` |
| 文件改了但 git 不识别 | 文件名带特殊字符 (空格/中文标点) | 重命名为 ASCII 安全命名 |
| `git stash drop` 后丢文件 | 没确认 stash 内容就 drop | `git stash show -p` 先看内容 |

## 防坑铁律

1. **每章写完必做 3 步同步**: cp 到 Desktop + cp 到 Riky- + git commit + git push — **缺一不可**
2. **不要**用 `git reset --hard <其他仓库>` 跨仓库同步 — 结构不同必出问题
3. **不要**相信 commit msg 的"完成" — 必须 `git show --stat` 看实际改了哪些文件
4. **必须**三处文件名 md5 一致才算同步完成
5. **必须**留 archive 文件作为废稿备份, 命名 `_archive_<书>_<章>_<日期>.md`