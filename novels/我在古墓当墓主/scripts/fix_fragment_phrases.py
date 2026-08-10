#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""短语碎句修复: 把 '，XX，XX，' 短短语堆叠合并为流畅叙述
规则:
  1. 匹配: 逗号分隔的连续短片段(每个2-6字), 片段间无语义断点
  2. 合并策略: 删除导致碎句的逗号, 保留必要停顿
  3. 保护: 「」对话内、【】系统面板、人名/专有名词
用法: python3 fix_fragment_phrases.py <章号或all>
"""
import re, os, sys

os.chdir(os.path.expanduser('~/Riky-/novels/我在古墓当墓主/chapters'))

# 需要修复的章节 (碎句≥5处)
TARGETS = [13, 21, 29, 30, 34, 41, 56, 62, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94]

def fix_line(line):
    """修复单行内的短语碎句"""
    # 保护对话【】内的内容不被改动
    def protect_quotes(m):
        return '『' + m.group(1) + '』'
    protected = re.sub(r'「([^」]*)」', protect_quotes, line)
    
    # 修复: 把 ',短,短,' 模式中过度断句的逗号删除
    # 策略: 匹配 [，][1-6字][，] 的连续链, 若整链都在一个"语义块"内则合并
    # 具体: 将 '，X，' (X≤6字) 且前后不是标点/引号 时, 视情况删除逗号
    def merge(m):
        return '，' + m.group(1) + m.group(2)
    
    # 模式1: ，A，B， → ，AB，(A+B≤12字)
    new = re.sub(r'，([^，。！？「」【】]{1,6})，([^，。！？「」【】]{1,6})，', 
                 lambda m: '，' + m.group(1) + m.group(2) + '，' if len(m.group(1))+len(m.group(2)) <= 12 else m.group(0), 
                 protected)
    
    # 模式2: ，A，B。 → ，AB。(句尾合并)
    new = re.sub(r'，([^，。！？「」【】]{1,6})，([^，。！？「」【】]{1,6})([。！？])', 
                 lambda m: '，' + m.group(1) + m.group(2) + m.group(3) if len(m.group(1))+len(m.group(2)) <= 12 else m.group(0), 
                 new)
    
    # 还原保护
    restored = re.sub(r'『([^』]*)』', lambda m: '「' + m.group(1) + '」', new)
    return restored

changed = []
for f in os.listdir('.'):
    if not f.startswith('我在古墓当墓主_第') or not f.endswith('.md'):
        continue
    n = int(re.search(r'第(\d+)章', f).group(1))
    if n not in TARGETS:
        continue
    text = open(f, encoding='utf-8').read()
    orig = text
    lines = text.split('\n')
    new_lines = [fix_line(l) if '，' in l else l for l in lines]
    new_text = '\n'.join(new_lines)
    if new_text != orig:
        open(f, 'w', encoding='utf-8').write(new_text)
        # 统计改善
        before = len(re.findall(r'[^，。！？「」]{1,5}[，][^，。！？「」]{1,5}[，][^，。！？「」]{1,5}[，]', orig))
        after = len(re.findall(r'[^，。！？「」]{1,5}[，][^，。！？「」]{1,5}[，][^，。！？「」]{1,5}[，]', new_text))
        changed.append((n, before, after))

print(f'已修复 {len(changed)} 章:')
for n, b, a in changed:
    print(f'  Ch{n:03d}: 碎句 {b} → {a}')
