#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号瘦身Step1: 删除标点+破折号冗余组合（绝对安全，不改变语义）"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

# 安全替换规则: 标点后/前紧跟破折号 → 只保留标点（破折号冗余）
REPLACEMENTS = [
    ('，——', '，'),
    ('。——', '。'),
    ('？——', '？'),
    ('！——', '！'),
    ('：——', '：'),
    ('；——', '；'),
    ('、——', '、'),
    ('——，', '，'),
    ('——。', '。'),
    ('——？', '？'),
    ('——！', '！'),
    ('——：', '：'),
    ('——；', '；'),
    ('——、', '、'),
]

summary = []
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body_end = ms[-1].start() if ms else len(text)
    body = text[:body_end]
    tail = text[body_end:]
    before = len(re.findall(r'——', body))
    for old, new in REPLACEMENTS:
        body = body.replace(old, new)
    after = len(re.findall(r'——', body))
    open(f, 'w', encoding='utf-8').write(body + tail)
    if before != after:
        summary.append((n, before, after))

print('=== Step1 结果（仅标点冗余） ===')
for n, before, after in summary:
    flag = '✅' if after <= 30 else '🟡'
    print(f'Ch{n:03d}: {before} → {after} {flag}')
print()
print(f'共处理 {len(summary)} 章')
