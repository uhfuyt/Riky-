#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析文字——文字的上下文模式，找可安全批量替换的规律"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

# 收集所有"汉字——汉字"模式的前后各2字
patterns = {}
total = 0
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:ms[-1].start()] if ms else text
    for m in re.finditer(r'([\u4e00-\u9fff])——([\u4e00-\u9fff])', body):
        total += 1
        key = m.group(1) + '|' + m.group(2)
        patterns[key] = patterns.get(key, 0) + 1

print(f'共{total}处"文字——文字"模式')
print(f'不同前后字组合: {len(patterns)}种')
print()
# 按频率排序，看高频组合
for k, v in sorted(patterns.items(), key=lambda x: -x[1])[:40]:
    print(f'{k} × {v}')
