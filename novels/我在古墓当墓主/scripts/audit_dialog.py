#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

print('=== 前35章真实对话占比(中英文引号内汉字/总汉字) ===')
for f in files[:35]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:ms[-1].start()] if ms else text
    cn = len(re.findall(r'[\u4e00-\u9fff]', body))
    # 中文引号
    dlg_cn = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'「([^」]*)」', body))
    # 英文引号成对
    dlg_en = 0
    for m in re.finditer(r'"([^"]*)"', body):
        dlg_en += len(re.findall(r'[\u4e00-\u9fff]', m.group(1)))
    total_dlg = dlg_cn + dlg_en
    ratio = total_dlg/cn*100 if cn else 0
    flag = '🟡' if ratio < 15 else '✅'
    print(f'{flag} Ch{n:03d} 对话{ratio:.0f}% (「{dlg_cn}字 + "{dlg_en}字)')

print()
print('=== 前35章各章引号体例 ===')
for f in files[:35]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    cn_q = len(re.findall('「', text))
    en_q = len(re.findall('"', text))
    style = '中文「' if cn_q >= en_q else '英文"'
    if cn_q > 0 and en_q > 0: style += ' ⚠️混用'
    print(f'  Ch{n:03d}: 「{cn_q} vs "{en_q} → {style}')
