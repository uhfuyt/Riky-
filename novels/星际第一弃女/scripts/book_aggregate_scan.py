#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全书聚合质量扫描器 — 专抓「拼装书指纹」（单章检测抓不到的跨章问题）

背景：末日便利店被拒根因=引号体例3连跳(「」→弯引号→ASCII)，诡异复苏被拒根因=破折号均142/章+卷四对话0%。
单章检测器每章内部都"统一"，查不出跨章拼接。本扫描器补上「聚合模式」检测。

用法: python3 book_aggregate_scan.py <chapters目录> [书名前缀]
"""
import re, os, sys, glob
from collections import Counter

def count_han(s): return len(re.findall(r'[\u4e00-\u9fff]', s))

def extract_body(text):
    m = list(re.finditer(r'第\d+章\s*完', text))
    return text[:m[-1].start()] if m else text

def scan(ch_dir):
    files = sorted(glob.glob(os.path.join(ch_dir, '*.md')), key=lambda f: int(re.search(r'(\d+)', os.path.basename(f)).group(1)) if re.search(r'(\d+)', os.path.basename(f)) else 0)
    if not files:
        print('❌ 无章节文件'); return

    rows = []
    for f in files:
        text = open(f, encoding='utf-8').read()
        body = extract_body(text)
        name = os.path.basename(f)
        num_match = re.search(r'(\d+)', name)
        num = int(num_match.group(1)) if num_match else 0
        cn = count_han(body)
        # 引号体例统计
        jp = body.count('「') + body.count('」')          # 直角引号
        curve = body.count('“') + body.count('”')        # 弯引号
        ascii_d = len(re.findall(r'"', body))            # ASCII双引号
        ascii_s = len(re.findall(r"'", body))            # ASCII单引号
        # 引号体例判定：哪种最多
        styles = {'「」': jp, '“”': curve, 'ASCII"': ascii_d, "ASCII'": ascii_s}
        dominant = max(styles, key=styles.get)
        total_q = sum(styles.values())
        # 破折号
        dash = body.count('——')
        # 对话占比（三种引号内汉字）
        dial = sum(count_han(q) for q in re.findall(r'「([^「」]{1,600}?)」', body, re.S))
        dial += sum(count_han(q) for q in re.findall(r'“([^“”]{1,600}?)”', body, re.S))
        dial += sum(count_han(q) for q in re.findall(r'"([^"\n]{1,600})"', body, re.S))
        pct = dial * 100 / cn if cn else 0
        # 标题完整性（支持 第一章/第1章/第001章，必须有标题文字）
        first = text.strip().split('\n')[0].strip()
        # 中文数字或阿拉伯数字（含零填充）的章标题，且标题后有非空文字
        has_title = bool(re.match(r'^#\s*第[0-9０-９〇一二三四五六七八九十百千]{1,4}章\s*\S+', first))
        rows.append({
            'num': num, 'cn': cn, 'dash': dash, 'pct': pct,
            'jp': jp, 'curve': curve, 'ascii_d': ascii_d, 'ascii_s': ascii_s,
            'style': dominant, 'total_q': total_q, 'has_title': has_title, 'name': name
        })

    print(f'扫描 {len(rows)} 章 | 目录: {ch_dir}')
    print('=' * 88)
    print(f"{'章':>5} | {'字数':>5} | {'破折':>4} | {'对话%':>5} | {'「」':>4} | {'弯引':>4} | {'ASCII':>5} | 体例主用 | 标题")
    print('-' * 88)
    for r in rows:
        flag_dash = '🔴' if r['dash'] > 30 else ('🟡' if r['dash'] > 20 else '✅')
        flag_pct = '🔴' if r['pct'] < 15 else ('🟡' if r['pct'] < 25 else '✅')
        flag_wc = '🔴' if r['cn'] < 2400 else '✅'
        t = '✅' if r['has_title'] else '❌'
        print(f"{r['num']:>5} | {r['cn']:>5}{flag_wc} | {r['dash']:>4}{flag_dash} | {r['pct']:>5.1f}{flag_pct} | {r['jp']:>4} | {r['curve']:>4} | {r['ascii_d']+r['ascii_s']:>5} | {r['style']:<7} | {t}")

    print('=' * 88)
    # ===== 聚合判定 1: 引号体例跳变（拼装指纹）=====
    print('\n🔍 聚合检查1: 引号体例跨章一致性')
    style_runs = []
    for r in rows:
        if style_runs and style_runs[-1]['style'] == r['style']:
            style_runs[-1]['nums'].append(r['num'])
        else:
            style_runs.append({'style': r['style'], 'nums': [r['num']]})
    if len(style_runs) > 1:
        print(f'  ❌ 体例跳变 {len(style_runs)} 段: ' + ' → '.join(f"{s['style']}(Ch{s['nums'][0]}-{s['nums'][-1]})" for s in style_runs))
        print('  ⚠️ 这就是拼装书指纹！编辑翻几章就能识破')
    else:
        print(f"  ✅ 全书统一: {style_runs[0]['style']}")

    # ===== 聚合判定 2: 破折号超标章分布 =====
    print('\n🔍 聚合检查2: 破折号>30章分布（定位重写批次）')
    bad_dash = [r['num'] for r in rows if r['dash'] > 30]
    if bad_dash:
        print(f'  ❌ {len(bad_dash)}章超标: {bad_dash[:20]}...')
        # 找连续区间
        ranges = []
        for n in bad_dash:
            if ranges and n == ranges[-1][-1] + 1: ranges[-1].append(n)
            else: ranges.append([n])
        print(f'  超标区间: ' + ', '.join(f'Ch{r[0]}-{r[-1]}' for r in ranges))
    else:
        print('  ✅ 无超标章')

    # ===== 聚合判定 3: 对话占比<15%章（纯说明文批次）=====
    print('\n🔍 聚合检查3: 对话<15%章（纯说明文=AI拼装）')
    bad_pct = [r['num'] for r in rows if r['pct'] < 15]
    if bad_pct:
        print(f'  ❌ {len(bad_pct)}章: {bad_pct[:20]}...')
    else:
        print('  ✅ 无对话枯竭章')

    # ===== 聚合判定 4: 字数欠账 =====
    print('\n🔍 聚合检查4: 字数<2400章')
    bad_wc = [r['num'] for r in rows if r['cn'] < 2400]
    if bad_wc:
        print(f'  ❌ {len(bad_wc)}章: {bad_wc[:20]}...')
    else:
        print('  ✅ 全部达标')

    # ===== 聚合判定 5: 缺标题 =====
    print('\n🔍 聚合检查5: 缺标题章')
    bad_t = [r['num'] for r in rows if not r['has_title']]
    if bad_t:
        print(f'  ❌ {len(bad_t)}章: {bad_t[:20]}...')
    else:
        print('  ✅ 全部有标题')

    # ===== 聚合判定 6: 字数趋势（后段衰减=批量生成）=====
    print('\n🔍 聚合检查6: 字数趋势（后段衰减检测）')
    if len(rows) >= 20:
        third = len(rows) // 3
        p1 = sum(r['cn'] for r in rows[:third]) / third
        p2 = sum(r['cn'] for r in rows[third:2*third]) / third
        p3 = sum(r['cn'] for r in rows[2*third:]) / (len(rows) - 2*third)
        print(f'  前1/3均{ p1:.0f}字 | 中1/3均{p2:.0f}字 | 后1/3均{p3:.0f}字')
        if p3 < p1 * 0.7:
            print(f'  ❌ 后段衰减 {(1-p3/p1)*100:.0f}% — 疑似批量生成/空壳')
        else:
            print('  ✅ 无显著衰减')
    else:
        print(f'  (仅{len(rows)}章，跳过趋势检测)')

    # ===== 总结 =====
    print('\n' + '=' * 88)
    fails = 0
    if len(style_runs) > 1: fails += 1
    if bad_dash: fails += 1
    if bad_pct: fails += 1
    if bad_wc: fails += 1
    if bad_t: fails += 1
    print(f'聚合判定: {"❌ 有" + str(fails) + "项聚合问题 — 需修复后才可投推荐" if fails else "✅ 全部通过 — 无拼装指纹"}')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python3 book_aggregate_scan.py <chapters目录>'); sys.exit(1)
    scan(sys.argv[1])
