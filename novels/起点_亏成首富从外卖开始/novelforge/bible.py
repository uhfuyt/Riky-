# Story Bible — 任务卡 / 风格 / 大纲 读取
"""
[DS-0] 核心：从大纲细纲中抽取"本章任务卡"喂给写手Agent

存储:
- bible/books/{book}/chapters_meta.json — 每章任务卡(自动从卷细纲生成)
- bible/books/{book}/style.json — 风格指南
"""
import json, re
from pathlib import Path
import codex

ROOT = Path(__file__).parent.resolve()

def book_dir(book):
    return ROOT.joinpath('books', book)

def read_outline_text(book):
    """读取用户的卷一细纲 .md"""
    p = ROOT.parent.joinpath('outline', f'起点_卷一细纲.md' if book=='qidian' else f'番茄_卷一细纲.md')
    if not p.exists():
        return ''
    return p.read_text(encoding='utf-8')

def parse_chapter_tasks(book):
    """从卷一细纲解析每章任务卡 → 写入 chapters_meta.json"""
    text = read_outline_text(book)
    if not text:
        return []
    # 匹配 Ch\d+ 章节块
    pattern = re.compile(r'### (Ch\d+)\s*·\s*([^\n]+)\n(.*?)(?=\n###|\Z)', re.S)
    tasks = []
    for m in pattern.finditer(text):
        num_label, title, body = m.group(1), m.group(2).strip(), m.group(3).strip()
        # 提取爽点/钩子/情感/字数
        hook = ''
        pleasure = ''
        for line in body.split('\n'):
            if '**爽点**' in line or '爽点:' in line:
                pleasure = line.split(':')[-1].strip() if ':' in line else line
            if '**钩子**' in line or '钩子:' in line:
                hook = line.split(':')[-1].strip() if ':' in line else line
        # 数字章节号
        num = int(num_label[2:])
        tasks.append({
            'num': num, 'title': title, 'body': body,
            'hook': hook, 'pleasure': pleasure
        })
    # 写入 chapters_meta.json
    out = book_dir(book) / 'chapters_meta.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')
    return tasks

def load_chapter_tasks(book):
    p = book_dir(book) / 'chapters_meta.json'
    if not p.exists():
        return parse_chapter_tasks(book)
    return json.loads(p.read_text(encoding='utf-8'))

def next_task_card(book, ch_num):
    """2026-07-04 修复: 优先读codex.chapters_meta(完整body), 其次读旧chapters_meta.json"""
    import codex as _codex
    # 优先从 codex.json 读(完整body/hook/pleasure/word_target)
    meta = _codex.load_book(book) or {}
    for c in meta.get('chapters_meta', []):
        if c.get('num') == ch_num:
            return c
    # 退化到旧文件
    tasks = load_chapter_tasks(book)
    for t in tasks:
        if t.get('num') == ch_num:
            return t
    # 都没找到 — 默认空卡
    return {
        'num': ch_num, 'title': f'第{ch_num}章',
        'hook': '待生成', 'pleasure': '待生成', 'body': ''
    }

def load_style(book):
    p = book_dir(book) / 'style.json'
    if not p.exists():
        default = {
            'tone': '男频爽文,都市脑洞',
            'voice': '主角嘴贱腹黑心软',
            'avg_sentence_len': '15-25字',
            'banned_words': ['肏', '屌', '牛逼(可保留)', '草泥马'],
            'signature_phrases': [],
            'pleasure_density': '每5章1个小高潮',
            'hook_density': '每章末必有钩子'
        }
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding='utf-8')
        return default
    return json.loads(p.read_text(encoding='utf-8'))

def style_prompt_block(book):
    s = load_style(book)
    return f"""【风格指南】
- 语调: {s.get('tone')}
- 主角声线: {s.get('voice')}
- 句长: {s.get('avg_sentence_len')}
- 禁用词: {', '.join(s.get('banned_words', []))}
- 爽点密度: {s.get('pleasure_density')}
- 钩子密度: {s.get('hook_density')}
"""

def _load_recent_chapters(book, n=3, tail_chars=200):
    """加载最近N章原文(防遗忘铁律 2026-07-04焊死, 2026-07-04 v2省token优化)
    省token: 原文尾从500字→200字, N章总输入从1500字符→600字符 (-60%)
    智能N: Ch1-3写时n=0(没历史), Ch4+写时n=min(2, 已发布数-1)(避免无谓浪费)
    """
    import codex as _codex
    meta = _codex.load_book(book) or {}
    chapters_meta = meta.get('chapters_meta', [])
    # 取最近N章(按num倒序)
    sorted_meta = sorted([c for c in chapters_meta if c.get('status') == 'published'],
                         key=lambda x: x.get('num', 0), reverse=True)[:n]
    if not sorted_meta:
        return []
    # 章节正文从多个可能位置找(优先级: novelforge chapters → 项目根 chapters → Desktop 真源)
    candidates = [
        ROOT.joinpath('chapters'),
        ROOT.parent.joinpath('chapters'),
        Path('/home/admin/.hermes/mempalace/novel/chapters'),
        Path(f'/home/admin/Desktop/我的网文/{"起点_亏成首富从外卖开始" if book=="qidian" else "番茄_破财转运牌"}/chapters'),
        Path(f'/home/admin/Riky-/novels/{"起点_亏成首富从外卖开始" if book=="qidian" else "番茄_破财转运牌"}/chapters'),
    ]
    results = []
    for c_meta in sorted_meta:
        num = c_meta.get('num')
        title = c_meta.get('title', '').replace('/', '_').replace(' ', '_')
        prefix = '起点' if book == 'qidian' else '番茄'
        fname_patterns = [
            f"{prefix}_第{num}章_{title}.md",
            f"{prefix}_第{num}章_{title}.txt",
        ]
        found = None
        for d in candidates:
            if not d.exists(): continue
            for pattern in fname_patterns:
                p = d / pattern
                if p.exists():
                    found = p.read_text(encoding='utf-8')
                    break
            if found: break
        if found:
            # 2026-07-04 省token: 500字→200字
            tail = found[-tail_chars:] if len(found) > tail_chars else found
            results.append({
                'num': num,
                'title': title,
                'tail': tail
            })
    return sorted(results, key=lambda x: x['num'])

def _smart_recent_n(book, ch_num):
    """智能选最近N章(省token, 2026-07-04)
    Ch1-3: n=0 (写前3章没必要喂原文)
    Ch4+:   n=min(2, ch_num-1) (避免越界)
    Ch10+:  n=2 (固定2章, 不喂全部历史)
    """
    if ch_num <= 3: return 0
    return min(2, ch_num - 1)

def _characters_block(book, recent_chars=None):
    """强制复述角色表(防幻觉 2026-07-04焊死, v2省token)
    v2: 只列主角+最近N章出现过的角色, 不是全部(-40%字符)
    recent_chars: set/list of 角色名 → 优先列
    """
    import codex as _codex
    meta = _codex.load_book(book) or {}
    chars = meta.get('characters', [])
    if not chars: return ''
    # 主角永远第一
    protagonist = next((c for c in chars if c.get('role') == '主角'), chars[0])
    others = [c for c in chars if c != protagonist]
    # 如果给了recent_chars, 排前面的优先
    if recent_chars:
        recent_set = set(recent_chars)
        def rank(c):
            return 0 if c.get('name') in recent_set else 1
        others = sorted(others, key=rank)
    # 取主角+前3个其他角色 (省token: 6角色→4角色)
    shown = [protagonist] + others[:3]
    lines = ['【🔒 角色锁定】主角必叫 '+protagonist.get('name','?')+'. 其他: ' + ', '.join(c.get('name','?') for c in shown[1:])]
    return '\n'.join(lines) + '\n'

def _open_hooks_block(book, ch_num=None):
    """未回收伏笔表(防丢伏笔 2026-07-04焊死, v2省token)
    v2: 只列最近10章+本章相关的伏笔
    """
    import codex as _codex
    meta = _codex.load_book(book) or {}
    hooks = [h for h in meta.get('hooks', []) if h.get('status') != 'redeemed']
    if not hooks: return ''
    # 优先最近10章的伏笔
    if ch_num:
        recent = [h for h in hooks if abs(h.get('planted_ch', 0) - ch_num) <= 10]
        rest = [h for h in hooks if h not in recent]
        hooks = recent + rest[:3]  # 最多recent+3 = 13条
    lines = [f'【🔒 伏笔(未回收)】' + '; '.join(f"{h.get('id','')} (Ch{h.get('planted_ch','')}):{h.get('content','')[:40]}" for h in hooks[:8])]
    return '\n'.join(lines) + '\n'

def _recent_chapters_block(book, ch_num):
    """最近N章原文尾段(防遗忘 2026-07-04焊死, v2智能N+省token)"""
    n = _smart_recent_n(book, ch_num)
    recents = _load_recent_chapters(book, n=n, tail_chars=200)
    if not recents: return ''
    lines = [f'【🔒 最近{len(recents)}章尾200字】']
    for r in recents:
        lines.append(f'Ch{r["num"]} {r["title"]}: ...{r["tail"][-150:]}')
    return '\n'.join(lines) + '\n'

def _word_count_constraint(ch_num):
    """字数硬约束(防字数飘 2026-07-04焊死, 2026-07-04 v2按真实已发布字数校准)

    用户原话"字数你查下前面文章的,再修改":
    起点已发布6章: 3303/3464/3203/4198/4086/4584字, 平均3535, 范围3203-4584
    番茄已发布3章: 2109/1536/2435字, 平均1974, 范围1536-2435

    新约束: 起点后续 3500-4500字, 番茄后续 1800-2300字 (跟已发布区间对齐)
    """
    return {
        'qidian': {
            1: (3000, 3500), 2: (3000, 3500), 3: (3000, 3500),  # 头3章锁定(已发布)
            4: (3500, 4500), 5: (3500, 4500), 6: (3500, 4500),  # Ch4-6锁定(已发布)
            'default': (3500, 4500),  # Ch7+ 跟已发布区间对齐
        },
        'fanqie': {
            1: (2500, 3000), 2: (2000, 2500), 3: (1500, 2000),  # 头3章锁定(已发布)
            'default': (1800, 2300),  # Ch4+ 跟已发布区间对齐
        },
    }

def _state_block(state):
    """压缩数值状态(省token v2) - 只给关键字段"""
    if not state: return ''
    keys = ['cash', 'level', 'multiple', 'daily_quota_used', 'daily_quota_remaining',
            'pending_total', 'last_chapter']
    compact = {k: state.get(k) for k in keys if k in state}
    return f'【数值】{json.dumps(compact, ensure_ascii=False)}\n'

def task_card_prompt(book, ch_num):
    """生成喂给写手Agent的完整prompt块(2026-07-04 v2生产级+省token版)
    省token对比 v1→v2:
      - 原文尾 500字→200字 (-60%)
      - 角色 6个→4个 (-33%)
      - 伏笔 全列→只列最近+3 (-50%)
      - 数值 全字段→7关键字段 (-40%)
      - 铁律 7条→5条合并 (-30%)
      总输入: ~1000 tokens → ~450 tokens (-55%)
    """
    import codex as _codex
    task = next_task_card(book, ch_num)
    meta = _codex.load_book(book) or {}
    state = meta.get('current_state', {})

    # 字数硬约束
    wc_map = _word_count_constraint(ch_num).get(book, {})
    wc = wc_map.get(ch_num, wc_map.get('default', (800, 1000)))
    wc_min, wc_max = wc

    # 找最近N章出现过的角色名
    recent_chars = set()
    for r in _load_recent_chapters(book, n=_smart_recent_n(book, ch_num)):
        # 从原文里找角色名 (粗略扫一下)
        for c in meta.get('characters', []):
            if c.get('name') in r.get('tail', ''):
                recent_chars.add(c.get('name'))

    return f"""【第{ch_num}章】{task.get('title','?')} ({wc_min}-{wc_max}字)
钩子:{task.get('hook','?')} | 爽点:{task.get('pleasure','?')}

{task.get('body','')[:500]}

{_characters_block(book, recent_chars=recent_chars)}

{_open_hooks_block(book, ch_num=ch_num)}

{_recent_chapters_block(book, ch_num)}

{_state_block(state)}

【🔒 铁律】①主角名锁定不许改 ②场景接续上章不许重置 ③数值直接用上面JSON ④伏笔不许凭空消失 ⑤字数{wc_min}-{wc_max},章末有钩子,禁日期/数据卡开头,第一人称
"""