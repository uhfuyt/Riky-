# NovelForge — 全分类AI长文流水线 v0.3 (2026-07-04 加入 5 分类支持)
"""
[DS-0] 主控CLI — 入口 (v0.3: 全分类, --genre 参数, 知识库引用)

Usage:
    python3 novelforge.py status                                  # 看全部书的进度
    python3 novelforge.py next <book>                             # 下一章任务卡
    python3 novelforge.py audit <book> <ch_file>                  # 跑一致性审计
    python3 novelforge.py chapter <book> <num>                    # 出第N章
    python3 novelforge.py publish <book> <ch_file>                # 发布
    python3 novelforge.py scrape <book>                           # 数据抓取
    python3 novelforge.py reset [book]                            # 重置
    python3 novelforge.py list-genres                             # 列出支持的6分类
    python3 novelforge.py list-books                              # 列出所有已建书
    python3 novelforge.py kb <genre>                              # 读某分类知识库索引
    python3 novelforge.py init <book_id> --genre=<genre> --title=<t>  # 新建书

GENRES (2026-07-04):
    xuanhuan(玄幻) | kehuan(科幻) | wuxianliu(无限流) | lishi(历史) | junshi(军事) | dushi(都市)

举例:
    python3 novelforge.py init new_xuanhuan_1 --genre=xuanhuan --title='万古签到:系统觉醒的凡人流'
    python3 novelforge.py status --genre=xuanhuan
    python3 novelforge.py kb xuanhuan
"""
import sys, json, os, argparse
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

# === 自动加载 .env(2026-07-04焊死) ===
# 跟 agents.py 同样的根因: 子进程不会自动加载 .env
try:
    from dotenv import load_dotenv
    _ENV_PATH = Path('/home/admin/.env')
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except ImportError:
    _ENV_PATH = Path('/home/admin/.env')
    if _ENV_PATH.exists():
        for _line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
            if '=' in _line and not _line.startswith('#'):
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k, _v)

import codex, bible, consistency, agents, data_scraper

BOOKS = ['qidian', 'fanqie']

# 5 分类支持 (2026-07-04)
GENRES = {
    'xuanhuan': '玄幻',
    'kehuan': '科幻',
    'wuxianliu': '无限流',
    'lishi': '历史',
    'junshi': '军事',
    'dushi': '都市',
}

# 知识库路径 (2026-07-04 双路径)
KNOWLEDGE_BASE_DIRS = [
    '/home/admin/Desktop/我的网文/_knowledge_base/',
    '/home/admin/Riky-/novels/_knowledge_base/',
]

def cmd_status(args):
    # 过滤参数
    target_genre = None
    if args and args[0].startswith('--genre='):
        target_genre = args[0].split('=',1)[1]
    print("="*70)
    print(f"【NovelForge 全局状态】{'(过滤: '+GENRES.get(target_genre, target_genre)+')' if target_genre else ''}")
    print("="*70)
    # 列出已建的书(扫 books/ 目录)
    for book in BOOKS:
        meta = codex.load_book(book)
        if not meta:
            print(f"\n[{book}] ⚫ 未初始化")
            continue
        genre = meta.get('genre', '?')
        if target_genre and genre != target_genre:
            continue
        ch_count = codex.chapter_count(book)
        next_ch = ch_count + 1
        print(f"\n[{book}] 《{meta.get('title','?')}》")
        print(f"  作者: {meta.get('author','?')}")
        print(f"  分类: {GENRES.get(genre, genre)}")
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

# === v0.3 新增: 全分类命令 ===

def cmd_list_genres(args):
    print("="*70)
    print("【全分类知识库支持】")
    print("="*70)
    print("\n支持的分类(2026-07-04 6 分类):")
    for gid, gname in GENRES.items():
        # 扫知识库目录文件
        for kb_dir in KNOWLEDGE_BASE_DIRS:
            g_dir = Path(kb_dir) / gname
            if g_dir.exists():
                files = sorted(g_dir.glob('*.md'))
                print(f"  {gid:12s} | {gname:6s} | 文件数: {len(files)} | 路径: {g_dir}/")
                break
    print("\n知识库总入口:")
    print(f"  Desktop: /home/admin/Desktop/我的网文/_knowledge_base/00_全分类整合总入口_2026-07-04.md")
    print(f"  Riky-:   /home/admin/Riky-/novels/_knowledge_base/00_全分类整合总入口_2026-07-04.md")

def cmd_kb(args):
    if len(args) < 1 or args[0] not in GENRES:
        print(f"Usage: novelforge.py kb <genre>")
        print(f"GENRES: {list(GENRES.keys())}")
        return
    genre = args[0]
    gname = GENRES[genre]
    # 找分类目录
    kb_dir = None
    for d in KNOWLEDGE_BASE_DIRS:
        g_dir = Path(d) / gname
        if g_dir.exists():
            kb_dir = g_dir
            break
    if not kb_dir:
        print(f"❌ 知识库目录不存在: {genre} ({gname})")
        return
    files = sorted(kb_dir.glob('*.md'))
    print(f"="*70)
    print(f"【{gname} 知识库索引】 ({kb_dir}/)")
    print(f"="*70)
    print(f"\n文件数: {len(files)}\n")
    total_size = 0
    for f in files:
        sz = f.stat().st_size
        total_size += sz
        print(f"  📄 {f.name} ({sz//1024}K)")
    print(f"\n总字数: {total_size//1024}K")
    print(f"\n💡 建议先读: 00_全分类整合总入口_2026-07-04.md (在父目录)")

def cmd_list_books(args):
    print("="*70)
    print("【已建书列表】")
    print("="*70)
    count = 0
    for book in BOOKS:
        meta = codex.load_book(book)
        if not meta:
            continue
        count += 1
        genre = meta.get('genre', '?')
        ch_count = codex.chapter_count(book)
        print(f"\n[{book}] 《{meta.get('title','?')}》")
        print(f"  作者: {meta.get('author','?')} / 分类: {GENRES.get(genre, genre)}")
        print(f"  进度: {ch_count} 章")
    if count == 0:
        print("\n⚫ 还没建书。请用 init 命令新建:")
        print("   python3 novelforge.py init <book_id> --genre=<genre> --title=<title>")
    print(f"\n💡 支持的分类: {list(GENRES.keys())}")

def cmd_init(args):
    # 简单解析 --genre=xxx --title=yyy
    book_id = None
    genre = None
    title = None
    for a in args:
        if a.startswith('--genre='):
            genre = a.split('=',1)[1]
        elif a.startswith('--title='):
            title = a.split('=',1)[1]
        elif not a.startswith('--'):
            book_id = a
    if not book_id or not genre or not title:
        print("Usage: novelforge.py init <book_id> --genre=<genre> --title=<title>")
        print(f"GENRES: {list(GENRES.keys())}")
        return
    if genre not in GENRES:
        print(f"❌ 未知 genre: {genre}。支持的: {list(GENRES.keys())}")
        return
    # 引用对应分类知识库
    gname = GENRES[genre]
    print(f"="*70)
    print(f"【新建书】{book_id}")
    print(f"="*70)
    # 检查知识库
    kb_ref = None
    for d in KNOWLEDGE_BASE_DIRS:
        g_dir = Path(d) / gname
        if g_dir.exists():
            kb_ref = g_dir
            break
    if kb_ref:
        print(f"✅ 知识库引用: {kb_ref}/")
        print(f"   文件数: {len(list(kb_ref.glob('*.md')))}")
    # 创建 books/<book_id>/
    books_root = ROOT.parent / 'books'
    book_path = books_root / book_id
    book_path.mkdir(parents=True, exist_ok=True)
    # 初始化 codex.json
    codex_data = {
        'book_id': book_id,
        'title': title,
        'author': 'rikky',
        'genre': genre,
        'genre_name': gname,
        'kb_ref': str(kb_ref) if kb_ref else None,
        'created_at': '2026-07-04',
        'platform': 'qidian+fanqie',
        'characters': [],
        'timeline': [],
        'hooks': [],
        'current_state': {},
    }
    codex_path = book_path / 'codex.json'
    codex_path.write_text(json.dumps(codex_data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✅ Codex 初始化: {codex_path}")
    print(f"\n下一步:")
    print(f"  1. 读 {kb_ref}/00_总入口.md 拿到 3 推荐开坑方向")
    print(f"  2. 创建大纲 + bible.md")
    print(f"  3. python3 novelforge.py chapter {book_id} 1")

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
        # v0.3 新增
        'list-genres': cmd_list_genres,
        'list-books': cmd_list_books,
        'kb': cmd_kb,
        'init': cmd_init,
    }
    fn = table.get(cmd)
    if not fn:
        print(__doc__)
        return
    fn(args)

if __name__ == '__main__':
    main()