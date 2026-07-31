#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引号体例统一：英文引号对 → 中文「」，若对内已含「」则内层转『』"""
import re, os, sys

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

def convert(text):
    """把文本中的英文引号对转成中文引号"""
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '"':
            # 找配对的关闭引号
            j = text.find('"', i+1)
            if j == -1:
                out.append(text[i])
                i += 1
                continue
            inner = text[i+1:j]
            # 如果内层已含「」→ 用『』
            if '「' in inner and '」' in inner:
                new_inner = inner.replace('「', '『').replace('」', '』')
                out.append('「' + new_inner + '」')
            else:
                out.append('「' + inner + '」')
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)

changed = []
for f in files:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    en_q = text.count('"')
    if en_q == 0:
        continue
    if en_q % 2 != 0:
        print(f'⚠️ Ch{n:03d} 英文引号奇数({en_q}个)，跳过需人工处理: {f}')
        continue
    new_text = convert(text)
    # 验证
    if new_text.count('"') != 0:
        print(f'⚠️ Ch{n:03d} 转换后仍有英文引号: {new_text.count(chr(34))}个')
        continue
    open(f, 'w', encoding='utf-8').write(new_text)
    changed.append(n)

print(f'✅ 已转换 {len(changed)} 章: {changed}')
