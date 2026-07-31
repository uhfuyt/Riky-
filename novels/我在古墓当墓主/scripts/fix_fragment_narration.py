#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""碎句修复v2：叙述段内 单字+逗号 修复
模式: X，和，Y → X和Y
      X，是，Y → X是Y (当X是「不是/但/只」等语境)
      X，的，Y → X的Y
      X，在，Y → X在Y
保留: 我，(自称插入语)、曾，是，陆，地(故意)、是，一把弩(强调)
"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

def fix_narration(body):
    """修复叙述段（对话外）的碎句"""
    out = []
    i = 0
    n = len(body)
    in_quote = False
    fixed = 0
    while i < n:
        ch = body[i]
        if ch == '「':
            in_quote = True
            out.append(ch); i += 1; continue
        if ch == '」':
            in_quote = False
            out.append(ch); i += 1; continue
        if not in_quote and ch == '，':
            prev = out[-1] if out else ''
            nxt = body[i+1:i+2]
            # 只修: 前字是 和/是/的/在/地/他/但 且后面还有字
            if prev in '和是的地在他但' and nxt and nxt not in '，。！？；：':
                # 保留「我，」自称（在「他，」处同样谨慎）
                if prev == '他' and body[i+1:i+8] in ('一个守', '一直守'):
                    out.append('，'); i += 1; continue
                if prev == '是':
                    # 强调型「是，」保留（如「不是人拦的，是，一把弩」）
                    # 判断: 前文是否以「不是/不」开头
                    before = ''.join(out)[-6:]
                    if '不是' in before:
                        out.append('，'); i += 1; continue
                # 删逗号，助词连后文
                fixed += 1
                i += 1
                continue
            out.append(ch); i += 1; continue
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
    new_body, fixed = fix_narration(body)
    if fixed:
        open(f, 'w', encoding='utf-8').write(new_body + tail)
        stats.append((n, fixed))

print('=== 叙述段碎句修复 ===')
for n, fixed in stats:
    print(f'Ch{n:03d}: 修复{fixed}处')
if not stats:
    print('无修复')
