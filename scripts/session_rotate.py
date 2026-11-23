#!/usr/bin/env python3
"""
会话轮换管家 —— 归档旧对话到 Git 仓库, 并让新对话能接上上下文。

由 Hermes 的 session_reset (idle 2880 分钟 = 48小时) 触发:
  1. 把当前会话导出成 Markdown 摘要
  2. 提交到 ~/Riky-/session_archive/ (Git)
  3. 写一份「接续说明」到 mempalace, 新对话启动时先读

用法:
  python session_rotate.py            # 归档 + git 提交 (cron / session_reset 后手动跑)
  python session_rotate.py --handoff   # 只生成给新对话的接续说明
  python session_rotate.py --check    # 检查是否需要归档
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERMES = Path(os.path.expanduser("~/.hermes"))
REPO = Path(os.path.expanduser("~/Riky-"))
ARCHIVE_DIR = REPO / "session_archive"
MEMPALACE = HERMES / "mempalace" / "quant_trading"
HANDOFF = MEMPALACE / "SESSION_HANDOFF.md"
ARCHIVER = HERMES / "scripts" / "archive_session.py"


def run(cmd, cwd=None, timeout=120):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, shell=isinstance(cmd, str))
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"


def do_archive():
    rc, out = run([sys.executable, str(ARCHIVER)])
    print(out.strip())
    return rc == 0


def do_git():
    """把归档提交到 Git 仓库。"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    # 复制最新归档进仓库
    src = HERMES / "mempalace" / "session_archive"
    copied = []
    if src.exists():
        for p in src.glob("*.md"):
            dst = ARCHIVE_DIR / p.name
            dst.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
            copied.append(p.name)

    if not copied:
        print("  (无新归档)")
        return True

    # 只 add 归档目录, 不混入其他改动
    rc, out = run(["git", "add", "session_archive/"], cwd=REPO)
    if rc != 0:
        print(f"  git add 失败: {out[:200]}")
        return False

    # 检查是否真有东西要提交
    rc, out = run(["git", "diff", "--cached", "--quiet"], cwd=REPO)
    if rc == 0:
        print("  (无变化, 跳过 commit)")
        return True

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"[会话归档] {stamp} · {len(copied)} 个文件\n\n" + \
          "\n".join(f"- session_archive/{n}" for n in copied)
    rc, out = run(["git", "commit", "-m", msg], cwd=REPO, timeout=180)
    if rc != 0:
        print(f"  commit 失败: {out[:300]}")
        return False
    print(f"  ✅ 已提交: {out.strip().splitlines()[0] if out.strip() else 'ok'}")

    # push (失败不阻塞 —— 本地已安全)
    rc, out = run(["git", "push", "origin", "HEAD"], cwd=REPO, timeout=300)
    if rc == 0:
        print("  ✅ 已 push 到 GitHub")
    else:
        print(f"  ⚠️ push 失败(本地已安全): {out.strip()[:150]}")
    return True


def build_handoff():
    """生成给新对话的接续说明。"""
    src = HERMES / "mempalace" / "session_archive" / "LATEST.md"
    if not src.exists():
        print("❌ 没有归档, 先跑 --archive")
        return False

    content = src.read_text(encoding="utf-8")

    # 提取关键小节
    def section(title, nxt):
        try:
            a = content.index(title)
            b = content.index(nxt, a)
            return content[a:b]
        except ValueError:
            return ""

    timeline = section("## 一、用户指令时间线", "## 二、")
    reports = section("## 三、结论落盘处", "## 四、")

    lines = [
        "# 🔄 会话接续说明（新对话必读）",
        "",
        f"> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> **触发**: Hermes session_reset（idle 2880 分钟 = 48 小时自动轮换）",
        "",
        "---",
        "",
        "## 新对话第一步要做什么",
        "",
        "1. 读本文件 → 了解上一轮做到哪了",
        "2. 读 `~/.hermes/mempalace/session_archive/LATEST.md` → 完整上一轮",
        "3. 读下面「结论落盘处」列出的报告文件 → 那些是硬数据，不要重做",
        "4. 用 `session_search` 查更早的历史",
        "",
        "---",
        "",
        "## 上一轮用户指令时间线",
        "",
        timeline,
        "",
        "---",
        "",
        "## 结论落盘处（不要重做这些）",
        "",
        reports,
        "",
        "---",
        "",
        "## 恢复提示",
        "",
        "- 长期记忆在 `~/.hermes/mempalace/` 和 `~/.hermes/USER.md`，**跨会话保留**",
        "- 完整逐字对话在 `~/.hermes/state.db`（`session_search` 工具可查）",
        "- Git 归档在 `~/Riky-/session_archive/`（已 push 到 uhfuyt/Riky-）",
        "",
        f"*由 `session_rotate.py` 生成 | 归档指纹 {abs(hash(content)) % 10**10}*",
    ]
    MEMPALACE.mkdir(parents=True, exist_ok=True)
    HANDOFF.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✅ 接续说明: {HANDOFF} ({HANDOFF.stat().st_size} 字节)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handoff", action="store_true", help="只生成接续说明")
    ap.add_argument("--check", action="store_true", help="检查状态")
    ap.add_argument("--no-git", action="store_true")
    args = ap.parse_args()

    if args.check:
        src = HERMES / "mempalace" / "session_archive"
        n = len(list(src.glob("*.md"))) if src.exists() else 0
        print(f"归档数: {n}")
        print(f"接续说明: {'有' if HANDOFF.exists() else '无'}")
        rc, out = run(["git", "log", "--oneline", "-3"], cwd=REPO)
        print("Git 最近提交:")
        print(out)
        return 0

    if args.handoff:
        build_handoff()
        return 0

    print("=== 1/3 归档会话 ===")
    do_archive()
    print("=== 2/3 Git 提交 ===")
    if not args.no_git:
        do_git()
    print("=== 3/3 生成接续说明 ===")
    build_handoff()
    print("✅ 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
