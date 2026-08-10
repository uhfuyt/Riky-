#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全书引号体例统一：弯引号“” + ASCII双引号 → 「」，嵌套内层转『』
用法: python3 unify_quotes_v2.py   (在 chapters/ 下运行, 自动备份到 /tmp/quotes_backup/)
"""
import re, os, shutil, sys

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f): return int(re.search(r'第(\d+)章', f).group(1))
files.sort(key=chnum)

BACKUP = '/tmp/quotes_backup'
os.makedirs(BACKUP, exist_ok=True)

def fix_nesting(text):
    """修复嵌套：外层是「」时，内层的「」转『』。
    循环处理: 「A「B」C」 → 「A『B』C」；处理到无嵌套为止"""
    while True:
        # 找 「...「...」...」 模式：外层「后、内层「出现
        m = re.search(r'「([^「」]{0,300})「([^「」]{0,300})」', text)
        if not m:
            break
        start, mid_end = m.start(), m.end()
        outer_open = m.start()
        inner_open = m.start() + 1 + len(m.group(1))
        inner_close = m.end() - 1
        # 内层「X」→『X』
        text = text[:inner_open] + '『' + text[inner_open+1:inner_close] + '』' + text[inner_close+1:]
    return text

changed = []
for f in files:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    orig = text
    # 1. ASCII双引号成对替换（交替开/关）
    parts = text.split('"')
    if len(parts) > 1:
        if len(parts) % 2 == 0:
            print(f'⚠️ Ch{n:03d} ASCII引号奇数({len(parts)-1}个)，跳过')
            continue
        text = ''
        for idx, p in enumerate(parts):
            if idx == len(parts) - 1:
                text += p
            elif idx % 2 == 0:
                text += p + '「'
            else:
                text += p + '」'
    # 2. 弯引号直接替换
    text = text.replace('“', '「').replace('”', '」')
    # 3. 嵌套修复
    text = fix_nesting(text)
    # 4. 验证
    if text.count('「') != text.count('」'):
        print(f'⚠️ Ch{n:03d} 引号不成对: 「{text.count("「")} vs 」{text.count("」")}，跳过')
        continue
    if '“' in text or '”' in text or '"' in text:
        print(f'⚠️ Ch{n:03d} 仍有弯引号/ASCII残留，跳过')
        continue
    if text != orig:
        shutil.copy2(f, os.path.join(BACKUP, f))
        open(f, 'w', encoding='utf-8').write(text)
        changed.append(n)

print(f'✅ 已统一 {len(changed)} 章: {changed}')
print(f'备份目录: {BACKUP}')
