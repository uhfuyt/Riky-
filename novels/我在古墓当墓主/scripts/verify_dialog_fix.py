#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补对话后验收脚本: 字数/对话%/系统%/方法论口径/引号成对/破折号"""
import re, sys, glob

def check(files):
    print(f'{"章":>4} {"汉字":>5} {"对话":>5} {"系统":>5} {"方法论":>6} {"破折":>4} 状态')
    for f in files:
        text = open(f, encoding='utf-8').read()
        m = list(re.finditer(r'第\d+章\s*完', text))
        body = text[:m[-1].start()] if m else text
        cn = len(re.findall(r'[\u4e00-\u9fff]', body))
        dlg = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'“([^”]*)”', body))
        sys_ = sum(len(re.findall(r'[\u4e00-\u9fff]', s)) for s in re.findall(r'【([^】]*)】', body))
        met = (dlg+sys_)*100/cn
        dash = body.count('——')
        kaku = text.count('「')+text.count('」')
        ascii_q = text.count('"')
        ok = met >= 15 and dash <= 30 and kaku == 0 and ascii_q == 0
        n = re.search(r'第(\d+)章', f).group(1)
        print(f'Ch{n:>3} {cn:>5} {dlg/cn*100:>4.1f}% {sys_/cn*100:>4.1f}% {met:>5.1f}% {dash:>4}  {"✅" if ok else "❌"}')
        if not ok:
            if met < 15: print(f'      ↓ 方法论口径{met:.1f}% < 15%')
            if dash > 30: print(f'      ↓ 破折号{dash} > 30')
            if kaku: print(f'      ↓ 残留「」{kaku}个')
            if ascii_q: print(f'      ↓ ASCII引号{ascii_q}个')

if __name__ == '__main__':
    d = sys.argv[1] if len(sys.argv) > 1 else '/home/admin/Riky-/novels/我在古墓当墓主/chapters'
    nums = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else None
    files = sorted(glob.glob(f'{d}/*.md'), key=lambda f: int(re.search(r'第(\d+)章', f).group(1)))
    if nums:
        files = [f for f in files if int(re.search(r'第(\d+)章', f).group(1)) in nums]
    check(files)
