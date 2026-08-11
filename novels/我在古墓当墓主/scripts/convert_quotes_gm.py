#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""《我在古墓当墓主》全书引号体例切换：『 』→ “ ”
规则：
- 外层「」 → “”
- 内层『』 → ‘’
- 转换后必须成对，不成对立即报错停止（不落盘）
- ASCII " 残留 → “” (成对)
用法: python3 convert_quotes_gm.py chapters/
"""
import sys, glob, re, os

def convert_text(text: str) -> tuple[str, list[str]]:
    errors = []
    # 1) 先处理『』嵌套 → ‘’（此时它们在外层「」内部）
    t = text.replace('『', '‘').replace('』', '’')
    # 2) 再处理外层「」 → “”
    t = t.replace('「', '“').replace('」', '”')
    # 3) ASCII 双引号 → “” (成对替换)
    if '"' in t:
        parts = t.split('"')
        # 奇数个片段 = 成对
        if len(parts) % 2 == 0:
            errors.append(f'ASCII引号数量为奇数: {t.count(chr(34))}')
        else:
            t = '“'.join(parts)
    # 校验
    if t.count('“') != t.count('”'):
        errors.append(f'“{t.count("“")} ≠ ”{t.count("”")}')
    if t.count('‘') != t.count('’'):
        errors.append(f'‘{t.count("‘")} ≠ ’{t.count("’")}')
    return t, errors

def main():
    if len(sys.argv) < 2:
        print('用法: convert_quotes_gm.py <chapters_dir>')
        sys.exit(1)
    d = sys.argv[1]
    files = sorted(glob.glob(os.path.join(d, '*.md')), key=lambda f: int(re.search(r'第(\d+)章', f).group(1)))
    total_changed = 0
    for f in files:
        text = open(f, encoding='utf-8').read()
        new_text, errors = convert_text(text)
        if errors:
            print(f'🔴 跳过 {os.path.basename(f)}: {errors}')
            sys.exit(2)
        if new_text != text:
            open(f, 'w', encoding='utf-8').write(new_text)
            total_changed += 1
    print(f'✅ 转换完成: {total_changed}/{len(files)} 章有改动, 全部成对校验通过')

if __name__ == '__main__':
    main()
