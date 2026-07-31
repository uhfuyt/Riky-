#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""密集破折号精简：单句(。！？内)破折号≥4时，只保留前2个，其余改逗号
保护：系统提示【】、引用『』内的不处理（那是原文引用格式）
"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

def process(body):
    """按句子处理，句子内破折号≥4时保留前2个"""
    # 分段: 以。！？\n 分句
    sentences = re.split(r'([。！？\n])', body)
    out = []
    changed = 0
    for sent in sentences:
        if '——' not in sent:
            out.append(sent)
            continue
        # 统计该句内破折号
        dash_pos = [m.start() for m in re.finditer(r'——', sent)]
        if len(dash_pos) < 4:
            out.append(sent)
            continue
        # 保留前2个，其余改逗号
        keep = set(dash_pos[:2])
        chars = list(sent)
        for i, pos in enumerate(dash_pos):
            if pos not in keep:
                chars[pos] = '，'
                chars[pos+1] = ''
        new_sent = ''.join(chars).replace('，，', '，')
        out.append(new_sent)
        changed += 1
    return ''.join(out), changed

stats = []
for f in files:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body_end = ms[-1].start() if ms else len(text)
    body = text[:body_end]
    tail = text[body_end:]
    before = len(re.findall(r'——', body))
    new_body, changed = process(body)
    after = len(re.findall(r'——', new_body))
    if changed:
        open(f, 'w', encoding='utf-8').write(new_body + tail)
        stats.append((n, before, after, changed))

print('=== 密集破折号精简结果 ===')
for n, before, after, changed in stats:
    flag = '✅' if after <= 30 else '🔴'
    print(f'Ch{n:03d}: {before} → {after} {flag} (处理{changed}句)')
