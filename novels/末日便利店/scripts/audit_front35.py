#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""末日便利店 前35章机械扫描 — 番茄推荐评估被拒取证"""
import re, os

CH_DIR = os.path.expanduser('~/Riky-/novels/末日便利店/chapters')

chapters = {}
for f in sorted(os.listdir(CH_DIR), key=lambda x: int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0):
    if not f.endswith('.md'):
        continue
    num = int(re.search(r'(\d+)', f).group(1))
    if num > 35:
        continue
    text = open(os.path.join(CH_DIR, f), encoding='utf-8').read()
    m = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:m[-1].start()] if m else text
    chapters[num] = (f, text, body)

print(f'扫描章节数: {len(chapters)} (Ch001-035)')
print('=' * 70)

issues = {'title': [], 'dash': [], 'nodlg': [], 'en_only': [], 'under2400': []}
for num in sorted(chapters):
    f, text, body = chapters[num]
    # 1. 缺标题
    first = text.split('\n')[0].strip()
    if not re.match(r'^#\s*第\d+章\s+\S+', first):
        issues['title'].append(num)
    # 2. 破折号
    dashes = text.count('——')
    if dashes > 30:
        issues['dash'].append((num, dashes))
    # 3. 对话占比
    cn = len(re.findall(r'[\u4e00-\u9fff]', body))
    dlg_cn = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'「([^」]*)」', body))
    dlg_en = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'"([^"]*)"', body))
    pct = (dlg_cn + dlg_en) / cn * 100 if cn else 0
    if pct < 15:
        issues['nodlg'].append((num, round(pct, 1)))
    # 4. 全英文引号章
    if not re.search(r'「', text) and re.search(r'"', text):
        issues['en_only'].append(num)
    # 5. 字数
    if cn < 2400:
        issues['under2400'].append((num, cn))
    # 打印每章概览
    dlg_total = dlg_cn + dlg_en
    dash_flag = '🔴' if dashes > 30 else ('🟡' if dashes > 20 else '✅')
    dlg_flag = '🔴' if pct < 15 else ('🟡' if pct < 25 else '✅')
    wc_flag = '🔴' if cn < 2400 else '✅'
    print(f'Ch{num:03d} | 字数{cn:5d} {wc_flag} | 破折号{dashes:3d} {dash_flag} | 对话{pct:5.1f}% {dlg_flag}')

print('=' * 70)
print(f'缺标题: {len(issues["title"])}章 -> {issues["title"]}')
print(f'破折号>30: {len(issues["dash"])}章 -> {issues["dash"]}')
print(f'对话<15%: {len(issues["nodlg"])}章 -> {issues["nodlg"]}')
print(f'全英文引号章: {len(issues["en_only"])}章 -> {issues["en_only"]}')
print(f'字数<2400: {len(issues["under2400"])}章 -> {issues["under2400"]}')
