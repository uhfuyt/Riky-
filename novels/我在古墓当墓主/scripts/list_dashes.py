#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出指定章剩余破折号的完整上下文"""
import re, os, sys

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
target = int(sys.argv[1]) if len(sys.argv) > 1 else 6
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
f = [x for x in files if chnum(x) == target][0]
text = open(f, encoding='utf-8').read()
ms = list(re.finditer(r'第\d+章\s*完', text))
body = text[:ms[-1].start()] if ms else text
matches = list(re.finditer(r'——', body))
print(f'Ch{target:03d} 共{len(matches)}处:')
for i, m in enumerate(matches):
    p = m.start()
    ctx = body[max(0,p-15):p+15].replace(chr(10),'⏎')
    prefix = body[:p]
    inside = '【对话内】' if prefix.count('「') > prefix.count('」') else ''
    print(f'{i:3d}{inside}: ...{ctx}...')
