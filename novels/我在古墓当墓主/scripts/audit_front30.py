#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, os, glob

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

print('=== 全书破折号分段统计 (>30处=超标) ===')
buckets = [(1,15,'Ch01-15'),(16,30,'Ch16-30'),(31,45,'Ch31-45'),(46,60,'Ch46-60'),(61,75,'Ch61-75'),(76,90,'Ch76-90'),(91,105,'Ch91-105'),(106,120,'Ch106-120')]
for a,b,label in buckets:
    cnts = []
    for f in files:
        n = chnum(f)
        if a <= n <= b:
            text = open(f, encoding='utf-8').read()
            cnts.append(len(re.findall('——', text)))
    over30 = sum(1 for c in cnts if c > 30)
    avg = sum(cnts)/len(cnts) if cnts else 0
    flag = '🔴' if over30 > len(cnts)*0.5 else ('🟡' if over30 > 0 else '✅')
    print(f'{flag} {label}: 平均{avg:.0f}处/章, 超标章数 {over30}/{len(cnts)}')

print()
print('=== 引号体例混用检查 ===')
mixed = 0
for f in files:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    cn_q = len(re.findall('「', text))
    en_q = len(re.findall('"', text))
    if cn_q > 0 and en_q > 0:
        mixed += 1
        print(f'  ⚠️ Ch{n:03d} 混用: 「{cn_q}处 + "{en_q}处')
if not mixed:
    print('  无混用')

print()
print('=== 全英文引号章节(无「) ===')
en_only = [chnum(f) for f in files if len(re.findall('「', open(f,encoding="utf-8").read()))==0]
if en_only:
    # 分组显示
    groups = []
    start = prev = en_only[0]
    for n in en_only[1:]:
        if n == prev+1: prev = n
        else:
            groups.append((start,prev)); start = prev = n
    groups.append((start,prev))
    print('  ' + ', '.join(f'{a}-{b}' if a!=b else f'{a}' for a,b in groups))
else:
    print('  无')

print()
print('=== 缺标题章节检查(首行只有章号无标题) ===')
missing = []
for f in files:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    first = lines[0] if lines else ''
    # 首行形如: # 第013章 或 ## 一 (只有编号/序号, 无标题文字)
    stripped = re.sub(r'[#\d章\s·\-]', '', first)
    if first.startswith('#') and not stripped and len(first) < 30:
        missing.append((n, first))
for n, first in missing:
    print(f'  ⚠️ Ch{n:03d}: 首行 "{first}" 无标题')
if not missing:
    print('  无')

print()
print('=== 全书完/本书完/全文完 污染 ===')
hits = []
for f in files:
    text = open(f, encoding='utf-8').read()
    if re.search('全书完|本书完|全文完', text):
        hits.append(chnum(f))
print('  ' + (', '.join(f'Ch{n}' for n in hits) if hits else '无'))

print()
print('=== 标题与大细纲一致性抽查(前10章) ===')
outline_titles = {1:'那把青铜钥匙',2:'第三十七代',3:'墓道里的灯光',4:'规则浮现',5:'第一次交易',6:'守墓奴仆',7:'机关课',8:'专业的和不要命的',9:'第一滴血',10:'墓里的规矩'}
for f in files:
    n = chnum(f)
    if n <= 10:
        actual = f.split('_')[2].replace('.md','')
        ot = outline_titles.get(n,'')
        mark = '✅' if actual == ot else f'❌ 大纲为"{ot}"'
        print(f'  Ch{n:03d} 实际"{actual}" {mark}')
