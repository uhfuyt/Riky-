#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号瘦身Final v2：精准保留
保留：对话中间的停顿（「我——我不行」）
删除：对话句首（「——X」）、叙述句首、【—— 
改逗号：其余叙述解释
目标：每章10-30处，全部是"中间停顿"质量
"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

def process(body):
    out = []
    i = 0
    n = len(body)
    stats = {'保留': 0, '删除': 0, '改逗号': 0}
    while i < n:
        if body[i:i+2] == '——':
            prefix = ''.join(out)
            left = prefix.count('「')
            right = prefix.count('」')
            inside = left > right
            # 前后字符
            prev_ch = prefix[-1] if prefix else ''
            next_ch = body[i+2] if i+2 < n else ''
            
            # 规则1: 对话句首或叙述句首 → 删除
            if prev_ch in '\n。！？；：「' or prev_ch == '【':
                i += 2
                stats['删除'] += 1
                continue
            # 规则2: 对话内中间停顿（前是汉字后是汉字/标点）→ 保留
            if inside and prev_ch and (prev_ch.isalpha() or prev_ch in '。！？；：') :
                out.append('——')
                i += 2
                stats['保留'] += 1
                continue
            # 规则3: 其余 → 逗号
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

print('=== 破折号瘦身v2结果 ===')
for n, before, after, s in stats:
    flag = '✅' if after <= 30 else '🔴'
    keep_n = s['保留']; del_n = s['删除']; com_n = s['改逗号']
    print(f'Ch{n:03d}: {before} → {after} {flag} (保留{keep_n}/删{del_n}/逗号{com_n})')
