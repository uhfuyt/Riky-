# Codex 圣经 — 角色/规则/事件/伏笔 CRUD
"""
存储路径: codex/books/{book}/codex.json
schema:
{
  "title": "...",
  "author": "...",
  "platform": "qidian|fanqie",
  "created_at": "...",
  "updated_at": "...",
  "characters": [{id, name, role, age, identity, personality, voice_quotes, hidden_attrs, relations}],
  "rules": {key: value},           # 金手指规则
  "timeline": [{date, event, ch}],  # 已发生事件
  "hooks": [{id, planted_ch, content, planned_redeem_ch, status}],
  "current_state": {cash, debt, level, ...},
  "world_anchors": {city, location, ...},
  "voice_style": {sentence_len, tone, banned_words, signature_phrases},
  "outline": {volumes: [{vol_num, title, word_target, core_pleasure, plot_arc}]},
  "chapters_meta": [{num, title, word_count, status, hook_summary, posted_at}]
}
"""
import json, os, time
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

def book_dir(book):
    return ROOT.joinpath('books', book)

def codex_path(book):
    return book_dir(book) / 'codex.json'

def load_book(book):
    p = codex_path(book)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8'))

def save_book(book, data):
    data['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    p = codex_path(book)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def init_book(book, title, author, platform):
    data = {
        'title': title, 'author': author, 'platform': platform,
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'characters': [], 'rules': {}, 'timeline': [], 'hooks': [],
        'current_state': {}, 'world_anchors': {},
        'voice_style': {'sentence_len': '短', 'tone': '男频爽文', 
                       'banned_words': [], 'signature_phrases': []},
        'outline': {'volumes': []},
        'chapters_meta': []
    }
    save_book(book, data)
    return data

def reset(book):
    if book:
        p = codex_path(book)
        if p.exists():
            p.unlink()
    else:
        for b in ['qidian', 'fanqie']:
            p = codex_path(b)
            if p.exists():
                p.unlink()

# === 角色CRUD ===
def add_character(book, char):
    data = load_book(book) or {}
    chars = data.get('characters', [])
    if 'id' not in char:
        char['id'] = f"c{len(chars)+1:03d}"
    chars.append(char)
    data['characters'] = chars
    save_book(book, data)
    return char['id']

def get_character(book, char_id):
    data = load_book(book) or {}
    for c in data.get('characters', []):
        if c.get('id') == char_id or c.get('name') == char_id:
            return c
    return None

def update_character(book, char_id, updates):
    data = load_book(book) or {}
    for c in data.get('characters', []):
        if c.get('id') == char_id:
            c.update(updates)
            save_book(book, data)
            return True
    return False

# === 伏笔CRUD ===
def add_hook(book, hook):
    data = load_book(book) or {}
    hooks = data.get('hooks', [])
    if 'id' not in hook:
        hook['id'] = f"F{len(hooks)+1:03d}"
    if 'status' not in hook:
        hook['status'] = 'planted'
    hooks.append(hook)
    data['hooks'] = hooks
    save_book(book, data)
    return hook['id']

def redeem_hook(book, hook_id, redeem_ch):
    data = load_book(book) or {}
    for h in data.get('hooks', []):
        if h.get('id') == hook_id:
            h['status'] = 'redeemed'
            h['redeemed_ch'] = redeem_ch
            save_book(book, data)
            return True
    return False

def open_hooks(book):
    """所有未回收的伏笔 — 审计Agent检查必用"""
    data = load_book(book) or {}
    return [h for h in data.get('hooks', []) if h.get('status') == 'planted']

# === 时间线CRUD ===
def add_event(book, date, event, ch=None):
    data = load_book(book) or {}
    tl = data.get('timeline', [])
    tl.append({'date': date, 'event': event, 'ch': ch})
    data['timeline'] = tl
    save_book(book, data)

# === 数值状态 ===
def update_state(book, key, value):
    data = load_book(book) or {}
    state = data.get('current_state', {})
    state[key] = value
    data['current_state'] = state
    save_book(book, data)

# === 章节元数据 ===
def register_chapter(book, num, title, word_count, hook_summary, posted_at=None):
    data = load_book(book) or {}
    cm = data.get('chapters_meta', [])
    # 覆盖同名章
    cm = [c for c in cm if c.get('num') != num]
    cm.append({
        'num': num, 'title': title, 'word_count': word_count,
        'hook_summary': hook_summary, 'posted_at': posted_at,
        'status': 'posted' if posted_at else 'draft'
    })
    data['chapters_meta'] = sorted(cm, key=lambda x: x['num'])
    save_book(book, data)

def chapter_count(book):
    data = load_book(book)
    if not data: return 0
    return len(data.get('chapters_meta', []))