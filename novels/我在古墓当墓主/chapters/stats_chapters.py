# -*- coding: utf-8 -*-
"""统计每章汉字数、对话%与系统%(面板%)。"""
import re, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def is_hanzi(ch):
    return '\u3400' <= ch <= '\u4dbf' or '\u4e00' <= ch <= '\u9fff'

def analyze(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    total = sum(1 for ch in text if is_hanzi(ch))
    # 系统面板【】内的汉字
    sys_chars = 0
    in_sys = False
    for ch in text:
        if ch == '【':
            in_sys = True
            continue
        if ch == '】':
            in_sys = False
            continue
        if in_sys and is_hanzi(ch):
            sys_chars += 1
    # 对话“”内(不在面板内)的汉字
    dial_chars = 0
    in_dial = False
    in_sys = False
    for ch in text:
        if ch == '【':
            in_sys = True
            continue
        if ch == '】':
            in_sys = False
            continue
        if ch == '\u201c':
            in_dial = True
            continue
        if ch == '\u201d':
            in_dial = False
            continue
        if in_dial and not in_sys and is_hanzi(ch):
            dial_chars += 1
    # 破折号计数
    dash = text.count('——')
    return {
        'file': path.split('/')[-1],
        'hanzi': total,
        'dial': dial_chars,
        'sys': sys_chars,
        'dial_pct': dial_chars / total * 100 if total else 0,
        'sys_pct': sys_chars / total * 100 if total else 0,
        'sum_pct': (dial_chars + sys_chars) / total * 100 if total else 0,
        'dash': dash,
    }

if __name__ == '__main__':
    files = [
        '/home/admin/Riky-/novels/我在古墓当墓主/chapters/我在古墓当墓主_第040章_钥匙猎人.md',
        '/home/admin/Riky-/novels/我在古墓当墓主/chapters/我在古墓当墓主_第041章_青铜匕首.md',
        '/home/admin/Riky-/novels/我在古墓当墓主/chapters/我在古墓当墓主_第042章_燃烧的都城.md',
    ]
    print('%-40s %6s %7s %7s %6s %6s %6s %5s' % ('章', '汉字', '对话', '系统', '对%', '系%', '合%', '——'))
    for f in files:
        r = analyze(f)
        print('%-40s %6d %7d %7d %5.1f%% %5.1f%% %5.1f%% %5d' % (
            r['file'], r['hanzi'], r['dial'], r['sys'],
            r['dial_pct'], r['sys_pct'], r['sum_pct'], r['dash']))
