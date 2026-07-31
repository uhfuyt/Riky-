#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析剩余破折号模式：成对 vs 单发，对话内 vs 对话外"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

# 对几个重灾章节做详细分析
for target in [5, 6, 10, 22, 26, 28]:
    f = [x for x in files if chnum(x) == target][0]
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:ms[-1].start()] if ms else text
    matches = [m.start() for m in re.finditer(r'——', body)]
    total = len(matches)
    
    # 统计: 在对话内 vs 对话外
    in_q = 0
    out_q = 0
    pairs = 0  # 成对（两破折号之间间隔<30字）
    singles = 0
    i = 0
    while i < total:
        p = matches[i]
        prefix = body[:p]
        inside = prefix.count('「') > prefix.count('」')
        if inside:
            in_q += 1
        else:
            out_q += 1
        # 检查是否成对
        if i+1 < total and matches[i+1] - p < 40:
            pairs += 1
            i += 2
        else:
            singles += 1
            i += 1
    
    print(f'Ch{target:03d}: 共{total}处 | 对话内{in_q} 对话外{out_q} | 成对插入语{pairs} 单发{singles}')
