#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""碎句修复：对话内的 单字+逗号 组合还原
修复模式（仅在「」对话内）：
  X，但，Y → X——但Y (或 X，但Y)
  X，是，Y → X——是Y
  X，和，Y → X和Y
  X，在，Y → X在Y
  X，的，Y → X的Y
  X，地，Y → X地Y
  X，我，Y → X，我Y (插入语保留)
"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

# 单字+逗号 → 修复映射（逗号前是单字时）
FIX_MAP = {
    '和，': '和',
    '但，': '但',
    '是，': '是',
    '在，': '在',
    '的，': '的',
    '地，': '地',
    '他，': '他',
    '因为，': '因为',
}

def fix_dialog(body):
    """只在「」内修复 单字+逗号"""
    out = []
    i = 0
    n = len(body)
    in_quote = False
    fixed = 0
    while i < n:
        ch = body[i]
        if ch == '「':
            in_quote = True
            out.append(ch)
            i += 1
            continue
        if ch == '」':
            in_quote = False
            out.append(ch)
            i += 1
            continue
        if in_quote and ch == '，':
            # 检查前一个字符是否是单字助词（在已输出的内容里）
            prev = out[-1] if out else ''
            # 检查后文
            nxt = body[i+1:i+2]
            # 模式: 前字是助词/连词 → 删掉这个逗号（让助词紧跟后文）
            if prev in '和但而是因为那这他它在有地中下上的了' and nxt:
                # 特殊: 「他，」在自称场景保留；「我，」自称保留
                if prev == '我':
                    out.append('，')
                else:
                    # 删掉逗号，助词直接连后文
                    fixed += 1
                    i += 1
                    continue
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return ''.join(out), fixed

stats = []
for f in files:
    n = chnum(f)
    if n <= 30: continue
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body_end = ms[-1].start() if ms else len(text)
    body = text[:body_end]
    tail = text[body_end:]
    new_body, fixed = fix_dialog(body)
    if fixed:
        open(f, 'w', encoding='utf-8').write(new_body + tail)
        stats.append((n, fixed))

print('=== 碎句修复结果 ===')
for n, fixed in stats:
    print(f'Ch{n:03d}: 修复{fixed}处')
if not stats:
    print('无修复')
