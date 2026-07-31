#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""前30章全面验证"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

print(f'{"章":6s} {"字数":>6s} {"对话":>5s} {"破折":>4s} {"引号":>4s} 状态')
problems = []
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body = text[:ms[-1].start()] if ms else text
    cn = len(re.findall(r'[\u4e00-\u9fff]', body))
    dlg = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'「([^」]*)」', body))
    ratio = dlg/cn*100 if cn else 0
    dashes = len(re.findall(r'——', body))
    left = text.count('「'); right = text.count('」')
    en = text.count('"') + text.count(chr(39))
    
    ok_word = cn >= 2400
    ok_dlg = ratio >= 12  # 终局探索章可放宽
    ok_dash = dashes <= 30
    ok_q = left == right and en == 0
    
    status = []
    if not ok_word: status.append('字数不足')
    if not ok_dlg: status.append('对话低')
    if not ok_dash: status.append('破折号多')
    if not ok_q: status.append('引号异常')
    
    flag = '✅' if not status else '❌ ' + ','.join(status)
    print(f'Ch{n:03d}   {cn:5d}  {ratio:4.0f}%  {dashes:4d}  {left:4d}  {flag}')
    if status:
        problems.append((n, status))

print()
if problems:
    print(f'⚠️ {len(problems)} 章有问题')
else:
    print('🎉 前30章全部通过')
