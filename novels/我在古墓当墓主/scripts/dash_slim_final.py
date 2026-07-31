#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号瘦身Final版：限量保留
策略：
1. 先按出现顺序收集所有破折号的位置
2. 逐处判断：保留 or 替换为逗号/删除
保留规则（优先）：
  a. 对话内且是语气停顿（如「我——我不行」短停顿）
  b. 每章最多保留25处（安全上限内）
替换规则：
  c. 句首破折号 → 删除
  d. 【—— → 删除
  e. 其余 → 逗号
"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

MAX_KEEP = 25  # 每章保留上限

def process(body):
    out = []
    i = 0
    n = len(body)
    kept = 0
    stats = {'保留': 0, '删除': 0, '改逗号': 0}
    while i < n:
        if body[i:i+2] == '——':
            prefix = ''.join(out)
            left = prefix.count('「')
            right = prefix.count('」')
            inside = left > right
            # 判断是否保留（对话内停顿，且未超上限）
            should_keep = inside and kept < MAX_KEEP
            if should_keep:
                out.append('——')
                kept += 1
                stats['保留'] += 1
                i += 2
                continue
            # 句首删除
            if prefix and prefix[-1] in '\n。！？；：' or (prefix and prefix[-1] == '【'):
                i += 2
                stats['删除'] += 1
                continue
            # 对话内但已超上限 → 也改逗号
            out.append('，')
            i += 2
            stats['改逗号'] += 1
        else:
            out.append(body[i])
            i += 1
    return ''.join(out), stats

stats = []
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body_end = ms[-1].start() if ms else len(text)
    body = text[:body_end]
    tail = text[body_end:]
    before = len(re.findall(r'——', body))
    
    new_body, s = process(body)
    after = len(re.findall(r'——', new_body))
    open(f, 'w', encoding='utf-8').write(new_body + tail)
    stats.append((n, before, after, s))

print('=== 破折号瘦身Final结果 ===')
for n, before, after, s in stats:
    flag = '✅' if after <= 30 else '🔴'
    keep_n = s['保留']; del_n = s['删除']; com_n = s['改逗号']
    print(f'Ch{n:03d}: {before} → {after} {flag} (保留{keep_n}/删{del_n}/逗号{com_n})')
