#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ch091 破折号瘦身: 叙述中"——"改逗号, 保留对话内停顿
规则(针对Ch091实测模式):
  1. 叙述段(非「」内): "，——" → "，"  "。——" → "。"  "——，" → "，"
     句中断句 "——" → "，" (保留修辞排比)
  2. 对话内(「」内): 保留中间停顿, 但 "——" 连续多处时精简
  3. 目标: 每章 ≤30 处
"""
import re

f = '/home/admin/Riky-/novels/我在古墓当墓主/chapters/我在古墓当墓主_第091章_缅甸守墓家族.md'
text = open(f, encoding='utf-8').read()
orig = text

def process_body(body):
    """处理正文（含对话，逐段处理）"""
    # 按行处理，保留「」内停顿，叙述中的——改逗号
    lines = body.split('\n')
    out = []
    for line in lines:
        if '「' in line:
            # 对话行: 保留对话内停顿, 但处理叙述部分
            # 简单策略: 对话内保留, 行内其他——改逗号
            # 拆分成 对话片段 + 叙述片段
            parts = re.split(r'(「[^」]*」)', line)
            new_parts = []
            for p in parts:
                if p.startswith('「'):
                    new_parts.append(p)  # 对话保留
                else:
                    # 叙述: 破折号改逗号
                    p = p.replace('，——', '，').replace('。——', '。').replace('——，', '，')
                    p = p.replace('——', '，')
                    new_parts.append(p)
            out.append(''.join(new_parts))
        else:
            # 纯叙述行
            line = line.replace('，——', '，').replace('。——', '。').replace('——，', '，')
            line = line.replace('——', '，')
            out.append(line)
    return '\n'.join(out)

# 分离章末钩子（保留钩子的破折号风格？钩子也瘦身但保留顿号感）
m = list(re.finditer(r'【第\d+章 完', text))
if m:
    head = text[:m[-1].start()]
    tail = text[m[-1].start():]
    new_head = process_body(head)
    # 钩子: 保留一些破折号但瘦身
    tail = tail.replace('——', '，')
    text = new_head + tail
else:
    text = process_body(text)

# 清理残留
text = text.replace('，，', '，').replace('，。', '。').replace('，！', '！')
text = text.replace('，——', '，').replace('——，', '，')

if text != orig:
    open(f, 'w', encoding='utf-8').write(text)
    print(f'✅ Ch091 破折号: {orig.count(chr(8212)*2)} → {text.count(chr(8212)*2)}')
else:
    print('无变化')
