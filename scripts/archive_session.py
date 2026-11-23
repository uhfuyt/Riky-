#!/usr/bin/env python3
"""
会话归档器 —— 把当前会话导出成 Markdown 摘要, 存进 Git 仓库。

用途:
  Hermes 的 session_reset 会自动开新对话, 旧对话的上下文就丢了。
  这个脚本在轮换前把【决策/状态/未完成事项】提取出来, 让新对话能接上。

设计要点:
  - 不导出 tool 全文 (动辄几万字, 没价值且占空间)
  - 提取: 用户指令 + 我的回复要点 + 所有 TODO + 文件产出路径
  - 输出: ~/.hermes/mempalace/session_archive/YYYY-MM-DD_<session_id>.md
  - 同时维护 LATEST.md 索引, 新对话启动时优先读这个

用法:
  python archive_session.py                # 归档当前活跃会话
  python archive_session.py --sid <id>     # 归档指定会话
  python archive_session.py --list         # 列出所有归档
  python archive_session.py --read         # 打印最新归档 (给新会话读)
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERMES = Path(os.path.expanduser("~/.hermes"))
DB = HERMES / "state.db"
OUT_DIR = HERMES / "mempalace" / "session_archive"
LATEST = OUT_DIR / "LATEST.md"


def get_sessions(conn):
    q = """
        SELECT s.id, s.title, s.started_at, s.last_activity_at,
               s.message_count, s.tool_call_count, s.input_tokens,
               s.output_tokens, s.estimated_cost_usd, s.source,
               s.end_reason, s.archived
          FROM sessions s
         WHERE s.message_count > 0
      ORDER BY COALESCE(s.last_activity_at, s.started_at) DESC
    """
    return [dict(r) for r in conn.execute(q)]


def active_session(conn, chat_id=None):
    """找当前活跃会话: 未结束 + 消息最多 + 最近活动。"""
    q = """
        SELECT s.id, s.title, s.started_at, s.last_activity_at,
               s.message_count, s.tool_call_count, s.input_tokens,
               s.output_tokens, s.estimated_cost_usd, s.source,
               s.end_reason, s.archived
          FROM sessions s
         WHERE s.ended_at IS NULL
      ORDER BY COALESCE(s.last_activity_at, s.started_at) DESC
    """
    rows = [dict(r) for r in conn.execute(q)]
    if not rows:
        return None
    return rows[0]


def fetch_messages(conn, sid):
    q = """
        SELECT id, role, content, tool_name, timestamp, token_count,
               compacted, display_kind
          FROM messages
         WHERE session_id = ?
      ORDER BY id
    """
    return [dict(r) for r in conn.execute(q, (sid,))]


def extract_user_turns(msgs):
    """用户真实指令 (排除工具结果和自动注入)。

    要过滤:
      - 压缩标记 / 心跳 / 系统注入
      - 重复投递 (gateway 可能把同一条消息记多次)
    """
    out = []
    seen_heads = set()
    for m in msgs:
        if m["role"] != "user":
            continue
        c = (m.get("content") or "").strip()
        if not c:
            continue
        # 过滤自动注入
        if c.startswith("[Context") or c.startswith("[Heartbeat") or c.startswith("[OUT-OF-BAND"):
            continue
        if c.startswith("[IMPORTANT:") or c.startswith("[SYSTEM"):
            continue
        # 压缩摘要不是用户说的话
        if "CONTEXT COMPACTION" in c[:200]:
            continue
        if "PRIOR CONTEXT" in c[:200] or "Historical Task Snapshot" in c[:300]:
            continue
        # 去重: 同一首行只留一次 (重复投递)
        head = c.split("\n")[0].strip()[:120]
        if head and head in seen_heads:
            continue
        if head:
            seen_heads.add(head)
        if len(c) > 4000:
            c = c[:2000] + f"\n\n...[截断, 原长 {len(c)} 字]...\n\n" + c[-1000:]
        out.append((m["id"], c, m.get("timestamp")))
    return out


def extract_assistant_answers(msgs):
    """我的【最终交付回复】。

    实测本环境 assistant 消息的分布 (2026-11-23):
      <50 字: 988 条   → 几乎全是"好/继续/开始查"这类过程碎片
      50-200 字: 930 条 → 内心过程叙述 ("先查...找到了...")
      1500+ 字: 41 条   → 真正的交付回复 (带 [DS-0] 标记 / 表格 / 代码块)
    判据: 长度 >= 1200 且不是压缩摘要。
    另外按内容指纹去重 —— gateway 会把同一条回复记多次。
    """
    out = []
    seen = set()
    for m in msgs:
        if m["role"] != "assistant":
            continue
        c = (m.get("content") or "").strip()
        if not c or len(c) < 1200:
            continue
        # 压缩摘要不是我的回复
        if "CONTEXT COMPACTION" in c[:300] or c.startswith("## Historical Task Snapshot"):
            continue
        if c.startswith("[PRIOR CONTEXT") or c.startswith("[END OF PRIOR CONTEXT"):
            continue
        if "END OF PRIOR CONTEXT" in c[:400]:
            continue
        # 重复投递去重
        fp = hashlib.sha256(c.encode()).hexdigest()
        if fp in seen:
            continue
        seen.add(fp)
        out.append((m["id"], c))
    return out


def extract_todos(msgs):
    """从 assistant 回复里抠出 TODO 工具调用。"""
    todos = []
    for m in msgs:
        if m["role"] != "assistant":
            continue
        # TODO 工具调用通常在 tool_calls 里, 这里从 content 里的清单也算
        c = (m.get("content") or "")
        for line in c.split("\n"):
            s = line.strip()
            if re.match(r'^[-*]\s*\[( |x|X)\]', s) or re.match(r'^\d+\.\s*\[( |x|X)\]', s):
                todos.append(s)
    # 去重保序
    seen, uniq = set(), []
    for t in todos:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def extract_files(msgs):
    """本会话产出/修改的文件路径。"""
    paths = set()
    pat = re.compile(r'(?:/(?:home|opt|srv|etc)/[^\s\'"`,;:()\[\]]{3,120})')
    for m in msgs:
        c = (m.get("content") or "")
        if m["role"] == "tool":
            if len(c) > 60000:
                continue
        for p in pat.findall(c):
            p = p.rstrip('.,;:')
            if any(x in p for x in ("/.git/", "__pycache__", "/node_modules/", "/.cache/")):
                continue
            paths.add(p)
    return sorted(paths)


def extract_reports(msgs):
    """写进 mempalace 的报告文件 (最重要: 那是结论落盘处)。"""
    hits = set()
    for m in msgs:
        c = (m.get("content") or "")
        if m["role"] == "tool" and len(c) > 60000:
            continue
        for p in re.findall(r'[\w./-]*mempalace/[\w./-]+\.(?:md|json|txt)', c):
            hits.add(p)
    return sorted(hits)


def fmt_ts(ts):
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


def build_markdown(sess, msgs, path):
    sid = sess["id"]
    turns = extract_user_turns(msgs)
    answers = extract_assistant_answers(msgs)
    todos = extract_todos(msgs)
    files = extract_files(msgs)
    reports = extract_reports(msgs)

    L = []
    L.append(f"# 会话归档 · {fmt_ts(sess.get('started_at'))}")
    L.append("")
    L.append(f"> **Session ID**: `{sid}`")
    L.append(f"> **来源**: {sess.get('source')} | **消息数**: {sess.get('message_count')} | "
             f"**工具调用**: {sess.get('tool_call_count')}")
    L.append(f"> **Token**: in={sess.get('input_tokens'):,} out={sess.get('output_tokens'):,} | "
             f"**成本**: ${sess.get('estimated_cost_usd') or 0:.4f}")
    L.append(f"> **开始**: {fmt_ts(sess.get('started_at'))} | **最后活动**: {fmt_ts(sess.get('last_activity_at'))}")
    L.append(f"> **归档时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("")
    L.append("> ⚠️ 本文件由 `archive_session.py` 自动生成, 供新会话恢复上下文用。")
    L.append("> 完整逐字对话在 `~/.hermes/state.db` 的 `messages` 表, 可用 `session_search` 查询。")
    L.append("")

    L.append("## 一、用户指令时间线")
    L.append("")
    L.append(f"共 {len(turns)} 条真实指令（已去重、已过滤系统注入）。")
    L.append("")
    for i, (mid, c, ts) in enumerate(turns, 1):
        first = c.split("\n")[0][:150]
        L.append(f"{i}. **[{fmt_ts(ts)}]** {first}")
        if len(c) > 150:
            L.append("")
            L.append("   <details><summary>展开全文</summary>")
            L.append("")
            for line in c.split("\n"):
                L.append(f"   {line}")
            L.append("")
            L.append("   </details>")
    L.append("")

    if todos:
        L.append("## 二、待办 / 任务清单")
        L.append("")
        for t in todos:
            L.append(f"- {t}")
        L.append("")

    if reports:
        L.append("## 三、结论落盘处（最重要，先读这些）")
        L.append("")
        for r in reports:
            L.append(f"- `{r}`")
        L.append("")

    L.append("## 四、关键回复要点")
    L.append("")
    L.append("### 4.1 全部回复概览")
    L.append("")
    for i, (mid, c) in enumerate(answers, 1):
        head = c.split("\n")[0][:160]
        L.append(f"{i}. {head}")
    L.append("")
    L.append("### 4.2 重要回复全文")
    L.append("")
    # 取最长的 8 条 (通常是核心结论)
    for i, (mid, c) in enumerate(sorted(answers, key=lambda x: -len(x[1]))[:8], 1):
        L.append(f"<details><summary>回复 #{i} ({len(c)} 字)</summary>")
        L.append("")
        L.append(c)
        L.append("")
        L.append("</details>")
        L.append("")

    if files:
        L.append("## 五、涉及文件路径")
        L.append("")
        L.append("```")
        for f in files[:120]:
            L.append(f)
        if len(files) > 120:
            L.append(f"... (共 {len(files)} 个)")
        L.append("```")
        L.append("")

    L.append("---")
    L.append("")
    L.append(f"*生成脚本: `~/.hermes/scripts/archive_session.py` | "
             f"内容指纹: `{hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else 'n/a'}`*")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", help="指定 session id")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--no-latest", action="store_true", help="不更新 LATEST.md")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.read:
        if LATEST.exists():
            print(LATEST.read_text(encoding="utf-8"))
        else:
            print("(还没有归档)")
        return

    if args.list:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        for s in get_sessions(conn)[:20]:
            print(f"{s['id'][:30]:<32} msg={s['message_count']:<5} "
                  f"${s['estimated_cost_usd'] or 0:.3f}  {fmt_ts(s.get('last_activity_at'))}  {s.get('title') or ''}")
        return

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    if args.sid:
        r = conn.execute("SELECT * FROM sessions WHERE id=?", (args.sid,)).fetchone()
        sess = dict(r) if r else None
    else:
        sess = active_session(conn)

    if not sess:
        print("❌ 找不到会话")
        return 1

    print(f"归档会话: {sess['id']} ({sess.get('message_count')} 消息)")
    msgs = fetch_messages(conn, sess["id"])
    print(f"  读取 {len(msgs)} 条原始消息")

    stamp = datetime.now().strftime("%Y-%m-%d")
    fname = f"{stamp}_{sess['id']}.md"
    path = OUT_DIR / fname
    path.write_text(build_markdown(sess, msgs, path), encoding="utf-8")
    print(f"  ✅ 写入: {path} ({path.stat().st_size} 字节)")

    if not args.no_latest:
        # LATEST.md = 最新归档 + 历史索引
        idx = []
        for p in sorted(OUT_DIR.glob("2*.md"), reverse=True)[:20]:
            idx.append(f"- `{p.name}`")
        header = (
            f"# 最新会话归档\n\n"
            f"> **更新**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"> **新会话启动时请先读这个文件**\n\n"
            f"---\n\n"
        )
        LATEST.write_text(header + path.read_text(encoding="utf-8") + "\n\n---\n\n## 历史归档索引\n\n"
                          + "\n".join(idx) + "\n", encoding="utf-8")
        print(f"  ✅ 索引: {LATEST}")

    # 标记会话已归档 (不删, 保留可查)
    try:
        conn.execute("UPDATE sessions SET archived=1 WHERE id=?", (sess["id"],))
        conn.commit()
        print("  ✅ sessions.archived=1")
    except Exception as e:
        print(f"  ⚠️ 标记失败: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
