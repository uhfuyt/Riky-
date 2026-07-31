#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全书120章综合验证"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

print(f'{"段":8s} {"字数":>7s} {"破折":>4s} {"引号":>4s} {"碎句":>3s}')
buckets = [(1,15,'Ch01-15'),(16,30,'Ch16-30'),(31,45,'Ch31-45'),(46,60,'Ch46-60'),(61,75,'Ch61-75'),(76,90,'Ch76-90'),(91,105,'Ch91-105'),(106,120,'Ch106-120')]
for a,b,label in buckets:
    words = dashes = q_issues = frag = 0
    dash_over = 0
    for f in files:
        n = chnum(f)
        if a <= n <= b:
            text = open(f, encoding='utf-8').read()
            ms = list(re.finditer(r'第\d+章\s*完', text))
            body = text[:ms[-1].start()] if ms else text
            words += len(re.findall(r'[\u4e00-\u9fff]', body))
            d = len(re.findall(r'——', body))
            dashes += d
            if d > 30: dash_over += 1
            if text.count('「') != text.count('」') or text.count('"') > 0:
                q_issues += 1
            frag += len(re.findall(r'[，][和是的地在他但用][，]', body))
    flag = '✅' if dash_over == 0 and q_issues == 0 and frag == 0 else '⚠️'
    print(f'{label}: {words:6d}字 {dashes:4d}处 {q_issues:4d} {frag:3d} {flag} (破折超标章:{dash_over})')

print()
# 汇总
all_words = 0
dash_total = 0
over = 0
frag_total = 0
for f in files:
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:ms[-1].start()] if ms else text
    all_words += len(re.findall(r'[\u4e00-\u9fff]', body))
    d = len(re.findall(r'——', body))
    dash_total += d
    if d > 30: over += 1
    frag_total += len(re.findall(r'[，][和是的地在他但用][，]', body))
print(f'全书总字数: {all_words}')
print(f'全书破折号: {dash_total}处, 超标章: {over}/120')
print(f'残留碎句: {frag_total}处')
