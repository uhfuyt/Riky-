#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号瘦身Step2: 非对话内解释性破折号→逗号（安全规则，逐字符扫描版）"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

# 规则: 破折号后跟这些词，且不在「」内 → 改为逗号
SAFE_AFTER = [
    '不是', '但是', '而是', '还是', '就是', '只是', '都是', '却是', '更是', '倒是',
    '因为', '所以', '如果', '只要', '甚至', '尤其', '特别', '至少', '而是',
    '应该', '可能', '大概', '也许', '似乎', '仿佛', '好像', '正好', '刚刚',
    '那个', '这个', '这些', '那些', '其中', '包括', '比如', '例如', '所谓',
    '也', '又', '还', '再', '才', '就', '都', '只', '却', '则',
]

def process_body(body):
    """逐字符扫描，安全替换非对话内的破折号"""
    out = []
    i = 0
    n = len(body)
    replaced = 0
    while i < n:
        if body[i:i+2] == '——':
            # 判断是否在「」内
            prefix = ''.join(out)
            left = prefix.count('「')
            right = prefix.count('」')
            inside = left > right
            # 检查破折号后的词
            matched = False
            if not inside:
                for w in SAFE_AFTER:
                    if body[i+2:i+2+len(w)] == w:
                        matched = True
                        break
            if matched:
                out.append('，')
                i += 2
                replaced += 1
            else:
                out.append('——')
                i += 2
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
    
    new_body, replaced = process_body(body)
    after = len(re.findall(r'——', new_body))
    open(f, 'w', encoding='utf-8').write(new_body + tail)
    stats.append((n, before, after, replaced))

print('=== Step2 结果 ===')
for n, before, after, repl in stats:
    flag = '✅' if after <= 30 else ('🟡' if after <= 45 else '🔴')
    print(f'Ch{n:03d}: {before} → {after} (替换{repl}) {flag}')
