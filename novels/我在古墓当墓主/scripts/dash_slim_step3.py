#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""破折号瘦身Step3: 
1) 成对插入语 X——Y——Z → X，Y，Z（两破折号间隔<40字，Y为插入说明）
2) 扩展单发规则: ——然后 → ，然后；——而且 → ，而且；——毕竟 → ，毕竟等
"""
import re, os

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))
files = [f for f in os.listdir('.') if f.startswith('我在古墓当墓主_第') and f.endswith('.md')]
def chnum(f):
    m = re.search(r'第(\d+)章', f)
    return int(m.group(1)) if m else 0
files.sort(key=chnum)

# 扩展规则：破折号后跟这些（非对话内）→ 逗号
SAFE_AFTER2 = [
    '然后', '而且', '毕竟', '其实', '终于', '竟然', '居然', '果然', '突然', '忽然',
    '仿佛', '偏偏', '确实', '的确', '当然', '自然', '恐怕', '反倒', '反而',
    '后来', '最后', '最初', '首先', '其次', '可见', '据说', '相传', '听说',
    '一个', '一座', '一件', '一种', '一半', '全部', '整个', '所有',
    '但', '而', '则', '乃', '即', '就', '正', '更', '颇', '尚', '尚', '甚',
]

def is_inside_quote(body, i):
    prefix = body[:i]
    return prefix.count('「') > prefix.count('」')

def process(body):
    """处理成对插入语 + 扩展单发规则"""
    # 先处理成对插入语：找 ——X—— 模式（X<40字，不含换行）
    changed = True
    pair_count = 0
    while changed:
        changed = False
        for m in re.finditer(r'——([^\n——]{1,38})——', body):
            p = m.start()
            inner = m.group(1)
            # 不在对话内，且内文是插入说明（不含「」）
            if not is_inside_quote(body, p) and '「' not in inner and '」' not in inner:
                # 检查内文是否像插入语: 不以标点开头
                if not inner[0] in '。，！？；：、':
                    body = body[:p] + '，' + inner + '，' + body[m.end():]
                    pair_count += 1
                    changed = True
                    break
        # 防止死循环：如果替换后不再匹配就退出
    
    # 再处理单发规则
    single_count = 0
    out = []
    i = 0
    n = len(body)
    while i < n:
        if body[i:i+2] == '——':
            if not is_inside_quote(body, i):
                matched = False
                for w in SAFE_AFTER2:
                    if body[i+2:i+2+len(w)] == w:
                        matched = True
                        break
                if matched:
                    out.append('，')
                    i += 2
                    single_count += 1
                    continue
            out.append('——')
            i += 2
        else:
            out.append(body[i])
            i += 1
    return ''.join(out), pair_count, single_count

stats = []
for f in files[:30]:
    n = chnum(f)
    text = open(f, encoding='utf-8').read()
    ms = list(re.finditer(r'第\d+章\s*完', text))
    body_end = ms[-1].start() if ms else len(text)
    body = text[:body_end]
    tail = text[body_end:]
    before = len(re.findall(r'——', body))
    
    new_body, pairs, singles = process(body)
    after = len(re.findall(r'——', new_body))
    open(f, 'w', encoding='utf-8').write(new_body + tail)
    stats.append((n, before, after, pairs, singles))

print('=== Step3 结果 ===')
for n, before, after, pairs, singles in stats:
    flag = '✅' if after <= 30 else ('🟡' if after <= 45 else '🔴')
    print(f'Ch{n:03d}: {before} → {after} (成对{pairs}+单发{singles}) {flag}')
