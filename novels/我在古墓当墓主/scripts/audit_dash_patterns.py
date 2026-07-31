#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号瘦身：统计前30章破折号，按类型分类"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

# 分析前30章破折号的上下文模式
patterns = {}
samples = {}
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:ms[-1].start()] if ms else text
    for m in re.finditer(r'——', body):
        p = m.start()
        before = body[max(0,p-3):p]
        after = body[p+2:p+5]
        # 分类
        key = None
        if before and before[-1] in '。！？，、：；':
            key = 'A.标点后(冗余)'
        elif after and after[0] in '「':
            key = 'B.引号前(对话引导)'
        elif after and after[0] in '，。！？':
            key = 'C.标点前(停顿)'
        elif re.match(r'[\u4e00-\u9fff]', after):
            key = 'D.文字前(解释)'
        else:
            key = 'E.其他'
        patterns[key] = patterns.get(key, 0) + 1
        if key not in samples:
            samples[key] = (n, body[max(0,p-15):p+15])

print('=== 前30章破折号类型分布 ===')
for k, v in sorted(patterns.items(), key=lambda x: -x[1]):
    n, ctx = samples[k]
    print(f'{k}: {v}处 | 例(Ch{n:03d}): ...{ctx}...')

# 每章分布
print()
print('=== 每章破折号数 ===')
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:ms[-1].start()] if ms else text
    cnt = len(re.findall(r'——', body))
    print(f'Ch{n:03d}: {cnt}')
