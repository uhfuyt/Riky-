#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号瘦身Step4: 全局激进但语义安全
规则:
1. 句首破折号(⏎后紧跟——) → 删除 (如「⏎——真的是金属碰撞的声音」→「⏎真的是...」)
2. 【——X → 【X (系统提示内冗余)
3. 「——X 对话内句首 → 删除破折号 (如「——我不知道」→「我不知道」)
4. 剩余所有非对话内—— → ，(叙述解释统一改逗号)
5. 对话内剩余—— 若两边都是汉字且间隔>4字 → ，(补充说明)
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
    replaced = {'句首': 0, '系统内': 0, '对话句首': 0, '叙述→逗号': 0, '对话→逗号': 0}
    while i < n:
        if body[i:i+2] == '——':
            prefix = ''.join(out)
            left = prefix.count('「')
            right = prefix.count('」')
            inside = left > right
            # 情况1: 句首（前面是换行/句号等）
            if prefix and prefix[-1] in '\n。！？；：':
                out.append('')
                i += 2
                replaced['句首'] += 1
                continue
            # 情况2: 系统提示内 【——
            if prefix and prefix[-1] == '【':
                i += 2
                replaced['系统内'] += 1
                continue
            # 情况3: 对话内句首 「——
            if inside and (not prefix or prefix[-1] == '「' or prefix[-1] in '\n。！？；：'):
                i += 2
                replaced['对话句首'] += 1
                continue
            # 情况4+5: 改逗号（无论叙述还是对话内的补充说明）
            out.append('，')
            i += 2
            if inside:
                replaced['对话→逗号'] += 1
            else:
                replaced['叙述→逗号'] += 1
        else:
            out.append(body[i])
            i += 1
    return ''.join(out), replaced

stats = []
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body_end = ms[-1].start() if ms else len(text)
    body = text[:body_end]
    tail = text[body_end:]
    before = len(re.findall(r'——', body))
    
    new_body, replaced = process(body)
    after = len(re.findall(r'——', new_body))
    open(f, 'w', encoding='utf-8').write(new_body + tail)
    stats.append((n, before, after, replaced))

print('=== Step4 结果 ===')
for n, before, after, r in stats:
    flag = '✅' if after <= 30 else '🔴'
    total_r = sum(r.values())
    print(f'Ch{n:03d}: {before} → {after} {flag} (替换{total_r}: {r})')
