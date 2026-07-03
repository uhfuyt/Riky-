# NovelForge — 起点/番茄 双发AI长文流水线 v0.1
"""
[DS-0] 主控CLI — 入口
Usage:
    python3 novelforge.py status                  # 看当前进度+Codex状态
    python3 novelforge.py next                    # 下一章任务卡(自动加载上下文)
    python3 novelforge.py audit <ch_file>         # 跑人设/设定/伏笔/数值 独立审计
    python3 novelforge.py chapter <num>           # 出第N章(写手Agent调用DeepSeek)
    python3 novelforge.py publish <ch_file>       # 发布Agent: 起点/番茄浏览器自动化
    python3 novelforge.py scrape qidian|fanqie    # 数据抓取Agent
    python3 novelforge.py reset [qidian|fanqie]   # 重置到空codex
"""
import sys, json, os
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

import codex, bible, consistency, agents, data_scraper

BOOKS = ['qidian', 'fanqie']

def cmd_status(args):
    print("="*70)
    print("【NovelForge 全局状态】")
    print("="*70)
    for book in BOOKS:
        meta = codex.load_book(book)
        if not meta:
            print(f"\n[{book}] ⚫ 未初始化")
            continue
        ch_count = codex.chapter_count(book)
        next_ch = ch_count + 1
        print(f"\n[{book}] 《{meta.get('title','?')}》")
        print(f"  作者: {meta.get('author','?')}")
        print(f"  进度: 已完成 {ch_count} 章 → 下一章 Ch{next_ch}")
        print(f"  Codex: 角色{len(meta.get('characters',[]))}人 / 事件{len(meta.get('timeline',[]))}条 / 伏笔{len(meta.get('hooks',[]))}条")
        print(f"  当前数值: {meta.get('current_state',{})}")
        # 提示下一章任务
        task = bible.next_task_card(book, next_ch)
        if task:
            print(f"  下一章钩子: {task.get('hook','?')[:60]}")
        else:
            print(f"  下一章钩子: ⚠️ 无任务卡,需生成")

def cmd_next(args):
    if len(args) < 1 or args[0] not in BOOKS:
        print("Usage: novelforge.py next [qidian|fanqie]")
        return
    book = args[0]
    ch_count = codex.chapter_count(book)
    next_ch = ch_count + 1
    print(f"=== [{book}] 第{next_ch}章 任务卡 ===")
    task = bible.next_task_card(book, next_ch)
    if not task:
        print("⚠️ 无任务卡,需要先在大纲里加本章条目")
        return
    print(json.dumps(task, ensure_ascii=False, indent=2))
    # 同时打印一致性引擎上下文
    print("\n=== 一致性引擎:本章强制复读清单 ===")
    consistency.pre_read_checklist(book, next_ch)

def cmd_audit(args):
    if len(args) < 2 or args[0] not in BOOKS:
        print("Usage: novelforge.py audit [qidian|fanqie] <chapter_file>")
        return
    book, ch_file = args[0], args[1]
    # 支持两种路径:相对 chapters/ 或绝对路径
    if '/' in ch_file or ch_file.startswith('~'):
        path = Path(ch_file).expanduser()
    else:
        path = ROOT.parent.joinpath('chapters', ch_file)
    if not path.exists():
        print(f"❌ 文件不存在: {path}")
        return
    text = path.read_text(encoding='utf-8')
    report = consistency.audit_chapter(book, text)
    print(json.dumps(report, ensure_ascii=False, indent=2))

def cmd_chapter(args):
    if len(args) < 2 or args[0] not in BOOKS:
        print("Usage: novelforge.py chapter [qidian|fanqie] <num>")
        return
    book, num = args[0], int(args[1])
    agents.run_writer(book, num)

def cmd_publish(args):
    if len(args) < 2 or args[0] not in BOOKS:
        print("Usage: novelforge.py publish [qidian|fanqie] <chapter_file>")
        return
    print("[DS-0] 发布Agent 触发 — 需用户先登录起点/番茄作家后台")
    agents.run_publisher(args[0], args[1])

def cmd_scrape(args):
    if len(args) < 1 or args[0] not in BOOKS:
        print("Usage: novelforge.py scrape [qidian|fanqie]")
        return
    data_scraper.scrape(args[0])

def cmd_reset(args):
    book = args[0] if args else None
    if book and book not in BOOKS:
        print("Usage: novelforge.py reset [qidian|fanqie]")
        return
    codex.reset(book)
    print(f"✅ 重置完成: {book or '全部'}")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    table = {
        'status': cmd_status,
        'next': cmd_next,
        'audit': cmd_audit,
        'chapter': cmd_chapter,
        'publish': cmd_publish,
        'scrape': cmd_scrape,
        'reset': cmd_reset,
    }
    fn = table.get(cmd)
    if not fn:
        print(__doc__)
        return
    fn(args)

if __name__ == '__main__':
    main()