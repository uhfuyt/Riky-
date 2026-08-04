#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全书120章引号体例 + 破折号 + 对话统计（末日便利店）"""
import re, os

CH_DIR = os.path.expanduser('~/Riky-/novels/末日便利店/chapters')
chapters = {}
for f in sorted(os.listdir(CH_DIR), key=lambda x: int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0):
    if not f.endswith('.md'):
        continue
    num = int(re.search(r'(\d+)', f).group(1))
    text = open(os.path.join(CH_DIR, f), encoding='utf-8').read()
    m = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:m[-1].start()] if m else text
    chapters[num] = (f, text, body)

print('章 | 字数 | 破折号 | 「」 | “”弯 | ASCII" | 对话%')
print('-' * 72)
for num in sorted(chapters):
    f, text, body = chapters[num]
    cn = len(re.findall(r'[\u4e00-\u9fff]', body))
    dashes = text.count('——')
    n_cn = text.count('「')
    n_curly = text.count('“')
    n_ascii = text.count('"')
    dlg_cn = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'「([^」]*)」', body))
    dlg_curly = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'“([^”]*)”', body))
    dlg_ascii = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'"([^"]*)"', body))
    pct = (dlg_cn + dlg_curly + dlg_ascii) / cn * 100 if cn else 0
    # 体例标记
    if n_cn > 0 and n_curly == 0 and n_ascii == 0:
        style = '「」'
    elif n_cn == 0 and n_curly > 0 and n_ascii == 0:
        style = '“”'
    elif n_cn == 0 and n_curly == 0 and n_ascii > 0:
        style = 'ASCII'
    elif n_cn > 0 and n_curly > 0:
        style = '「」+“”混'
    elif n_cn > 0 and n_ascii > 0:
        style = '「」+ASCII'
    elif n_curly > 0 and n_ascii > 0:
        style = '“”+ASCII'
    else:
        style = '无引号'
    vol = 1 + (num-1)//30
    print(f'Ch{num:03d} | {cn:5d} | {dashes:3d} | {n_cn:4d} | {n_curly:4d} | {n_ascii:4d} | {pct:5.1f}% | {style} | 卷{vol}')
