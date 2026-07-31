#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把英文单引号对 '...' 转成中文「...」，若在「」内部则转『...』"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]

def convert_single(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "'":
            j = text.find("'", i+1)
            if j == -1:
                out.append(text[i])
                i += 1
                continue
            inner = text[i+1:j]
            # 判断是否在「」内部: 统计从行首到i的「」配对
            # 简单方法: 如果inner和i之前的「比」多 → 在「内部
            left_before = text[:i].count('「') - text[:i].count('」')
            if left_before > 0:
                out.append('『' + inner + '』')
            else:
                out.append('「' + inner + '」')
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)

changed = []
for f in files:
    text = open(f, encoding='utf-8').read()
    if "'" not in text:
        continue
    cnt = text.count("'")
    if cnt % 2 != 0:
        print(f'⚠️ {f} 单引号奇数({cnt})，跳过: 需人工')
        continue
    new_text = convert_single(text)
    open(f, 'w', encoding='utf-8').write(new_text)
    changed.append(f.split('_')[2].replace('.md',''))

print(f'✅ 转换单引号 {len(changed)} 章')
