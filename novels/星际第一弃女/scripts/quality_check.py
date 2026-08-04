#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星际第一弃女 · 质量检测脚本（适配零填充+跨行对话）"""
import re, glob, os, sys

WC_MIN, WC_MAX = 2400, 3600
D_PCT_MIN, D_PCT_MAX = 30, 50
LONG_NARR_MIN = 3
MAX_DASH = 25

def count_han(s): return len(re.findall(r'[\u4e00-\u9fff]', s))

def body_of(text):
    m = list(re.finditer(r'第\d+章\s*完', text))
    return text[:m[-1].start()] if m else text

def check(f):
    text = open(f, encoding='utf-8').read()
    body = body_of(text)
    han = count_han(body)
    issues = []

    # 1 字数
    if han < WC_MIN: issues.append(('FAIL', f'字数不足 {han}<{WC_MIN}'))
    elif han > WC_MAX: issues.append(('WARN', f'字数偏多 {han}>{WC_MAX}'))

    # 2 对话占比（匹配「」含跨行）
    quotes = re.findall(r'「([^「」]{1,600}?)」', body, re.S)
    dial = sum(count_han(q) for q in quotes)
    pct = dial*100/max(han,1)
    if pct < D_PCT_MIN: issues.append(('FAIL', f'对话占比 {pct:.1f}% < {D_PCT_MIN}%'))
    elif pct > D_PCT_MAX: issues.append(('WARN', f'对话占比 {pct:.1f}% > {D_PCT_MAX}%'))

    # 3 长叙事段（≥80汉字段落数）
    paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip() and not p.strip().startswith(('#','>'))]
    long_n = sum(1 for p in paras if count_han(p) >= 80)
    if long_n < LONG_NARR_MIN: issues.append(('WARN', f'长叙事段 {long_n} < {LONG_NARR_MIN}'))

    # 4 破折号
    dash = len(re.findall('——', body))
    if dash > MAX_DASH: issues.append(('FAIL', f'破折号 {dash} > {MAX_DASH}'))

    # 5 引号污染
    curve = body.count('“') + body.count('”')
    ascii_q = len(re.findall(r'["\x27]', body))
    if curve: issues.append(('FAIL', f'弯引号 {curve}'))
    if ascii_q: issues.append(('FAIL', f'ASCII引号 {ascii_q}'))

    # 6 「」配对
    if body.count('「') != body.count('」'): issues.append(('FAIL', f'「」不配对 {body.count("「")}/{body.count("」")}'))

    # 7 章末钩子（末段非对话悬念）
    last_para = [p for p in paras if count_han(p) > 5][-1] if paras else ''
    has_hook = any(k in last_para for k in ['完','明天','等','会','却','将','？']) or '？' in last_para[-15:]
    if not has_hook: issues.append(('WARN', '章末钩子弱'))

    verdict = '✅' if not any(i[0]=='FAIL' for i in issues) else ('⚠️' if any(i[0]=='WARN' for i in issues) else '❌')
    print(f'{os.path.basename(f)}: {han}字 | 对话{pct:.1f}% | 叙事{long_n}段 | 破折号{dash} {verdict}')
    for lvl, msg in issues: print(f'    [{lvl}] {msg}')
    return verdict == '✅'

if __name__ == '__main__':
    files = sorted(glob.glob('chapters/*.md'))
    ok = sum(1 for f in files if check(f))
    print(f'--- 通过 {ok}/{len(files)} 章')
