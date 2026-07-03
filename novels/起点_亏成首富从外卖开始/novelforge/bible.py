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
    """读取用户的卷一细纲 .md - 支持桌面(大纲设定)和服务器(outline)两种布局"""
    p1 = ROOT.parent.joinpath('大纲设定', f'起点_卷一细纲.md' if book=='qidian' else f'番茄_卷一细纲.md')
    p2 = ROOT.parent.joinpath('outline', f'起点_卷一细纲.md' if book=='qidian' else f'番茄_卷一细纲.md')
    for p in [p1, p2]:
        if p.exists():
            return p.read_text(encoding='utf-8')
    return ''

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
    tasks = load_chapter_tasks(book)
    for t in tasks:
        if t.get('num') == ch_num:
            return t
    # 没找到细纲里的 — 退到默认空卡
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

def task_card_prompt(book, ch_num):
    """生成喂给写手Agent的完整prompt块"""
    task = next_task_card(book, ch_num)
    meta = codex.load_book(book) or {}
    style = style_prompt_block(book)
    state = meta.get('current_state', {})
    return f"""【第{ch_num}章 任务卡】
书名: {meta.get('title', '?')}
字数目标: {3000 if ch_num <= 3 else 1500 if ch_num <= 5 else 1000}

标题: {task.get('title', '?')}
本章钩子: {task.get('hook', '?')}
本章爽点: {task.get('pleasure', '?')}

详细要求:
{task.get('body', '')}

【当前数值状态】
{json.dumps(state, ensure_ascii=False, indent=2)}

{style}
"""