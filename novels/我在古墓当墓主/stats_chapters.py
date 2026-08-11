#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计章节汉字数、对话%(引号内汉字)与系统%(【】内汉字)。"""
import re
import sys

HAN = re.compile(r'[\u4e00-\u9fff]')


def count(text: str, pattern: str) -> int:
    return len(HAN.findall(pattern))


def stats(path: str):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    total = len(HAN.findall(text))

    # 对话:成对“ ”之间的汉字
    dia = 0
    for m in re.finditer(r'“[^”]*”', text):
        dia += len(HAN.findall(m.group(0)))

    # 系统:【 】之间的汉字
    sysn = 0
    for m in re.finditer(r'【[^】]*】', text):
        sysn += len(HAN.findall(m.group(0)))

    # 破折号(——)数量
    dash = text.count('——')

    return {
        'total': total,
        'dia': dia,
        'sys': sysn,
        'dia_pct': dia / total * 100 if total else 0,
        'sys_pct': sysn / total * 100 if total else 0,
        'comb_pct': (dia + sysn) / total * 100 if total else 0,
        'dash': dash,
    }


def main():
    for path in sys.argv[1:]:
        s = stats(path)
        print(f'{path}')
        print(f'  汉字总数: {s["total"]}')
        print(f'  对话汉字: {s["dia"]} ({s["dia_pct"]:.1f}%)')
        print(f'  系统汉字: {s["sys"]} ({s["sys_pct"]:.1f}%)')
        print(f'  对话+系统: {s["dia"] + s["sys"]} ({s["comb_pct"]:.1f}%)')
        print(f'  破折号(——): {s["dash"]}')


if __name__ == '__main__':
    main()
