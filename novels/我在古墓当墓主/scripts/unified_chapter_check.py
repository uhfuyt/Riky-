#!/usr/bin/env python3
"""
unified_chapter_check.py — 网文章节统一验收脚本 (2026-07-27 创建)

替代: check_dash_stack_v6.py + check_4dim.py + check_expansion_v5.py + consistency_test.py
优化: 1次文件读 → 全项检测 → 1个输出

用法:
  python3 scripts/unified_chapter_check.py <chapter.md> [--book 末日便利店]
  
批量:
  python3 scripts/unified_chapter_check.py chapters/*.md

输出: 每章一行 verdict，详细问题逐项列出
"""
import re
import sys
import os
from pathlib import Path

# ============ 配置 ============
WC_MIN, WC_MAX = 2400, 3600           # 3000±20%
DIALOGUE_PCT_MIN, DIALOGUE_PCT_MAX = 30, 50
DASH_STACK_THRESHOLD = 10
TRIVIA_DIALOGUE_THRESHOLD = 0.30
LONG_NARRATIVE_MIN = 3                 # ≥80字叙事段最少数量
MAX_DASH_TOTAL = 30                    # 全文破折号总数上限

# 越界角色（当前书特有）
FORBIDDEN_CHARS = ['林建业', '沈昭', '程晚棠', '王大龙']

# ============ 核心中文统计 ============
def count_han(text):
    """汉字字数"""
    return len(re.findall(r'[\u4e00-\u9fff]', text))

def count_cn(text):
    """中文字符（含标点）"""
    return len(re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', text))

def extract_body(text):
    """提取正文（去掉标题/自检段）"""
    for marker in ['**第一章 完**', '**第二章 完**']:
        idx = text.find(marker)
        if idx > 0:
            return text[:idx]
    return text

# ============ 维度1: 字数 ============
def check_word_count(text, fname):
    issues = []
    body = extract_body(text)
    han = count_han(body)
    if han < WC_MIN:
        issues.append(('FAIL', f'字数不足: {han} 汉字 < {WC_MIN}'))
    elif han > WC_MAX:
        issues.append(('WARN', f'字数偏多: {han} 汉字 > {WC_MAX}'))
    else:
        issues.append(('PASS', f'字数: {han} 汉字 [{WC_MIN}-{WC_MAX}]'))
    return issues, {'han': han}

# ============ 维度2: 对话质量 ============
def check_dialogue(text):
    issues = []
    han = count_han(text)
    
    # 引号对话
    quotes = re.findall(r'[""「」]([^""「」\n]{1,500})[""「」]', text)
    dial_chars = sum(count_han(q) for q in quotes)
    dial_pct = dial_chars * 100 / max(han, 1)
    
    if dial_pct > DIALOGUE_PCT_MAX:
        issues.append(('WARN', f'对话占比过高: {dial_pct:.1f}% > {DIALOGUE_PCT_MAX}%'))
    elif dial_pct < DIALOGUE_PCT_MIN:
        issues.append(('WARN', f'对话占比偏低: {dial_pct:.1f}% < {DIALOGUE_PCT_MIN}%'))
    else:
        issues.append(('PASS', f'对话占比: {dial_pct:.1f}% [{DIALOGUE_PCT_MIN}-{DIALOGUE_PCT_MAX}%]'))
    
    # 短废话对话
    trivia = sum(1 for q in quotes if count_han(q) <= 3)
    total_dial = len(quotes)
    trivia_pct = trivia / max(total_dial, 1)
    if trivia_pct > TRIVIA_DIALOGUE_THRESHOLD:
        issues.append(('FAIL', f'废话对话: {trivia}/{total_dial} ({trivia_pct*100:.0f}%) > {TRIVIA_DIALOGUE_THRESHOLD*100:.0f}%'))
    
    return issues, {'dial_pct': round(dial_pct, 1), 'dial_turns': total_dial}

# ============ 维度3: 破折号堆 + 反模式 ============
def check_antipatterns(text, lines):
    issues = []
    
    # 3.1 破折号堆（连续3+行以——开头）
    in_stack = False
    stack_start = 0
    stacks = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('——'):
            if not in_stack:
                in_stack = True
                stack_start = i
        else:
            if in_stack and (i - stack_start) >= 3:
                stacks += 1
            in_stack = False
    if in_stack and (len(lines) - stack_start) >= 3:
        stacks += 1
    
    if stacks > DASH_STACK_THRESHOLD:
        issues.append(('WARN', f'破折号堆: {stacks} 处 > {DASH_STACK_THRESHOLD}'))
    
    # 3.2 全文破折号总数
    dash_total = text.count('——')
    if dash_total > MAX_DASH_TOTAL:
        issues.append(('WARN', f'破折号总数: {dash_total} > {MAX_DASH_TOTAL}'))
    
    # 3.3 同一角色称呼连续
    prev_call = None
    call_count = 0
    call_issues = 0
    for line in lines:
        s = line.strip()
        m = re.match(r'^["""」]?(.{1,8})[""」]?\s*[—\-—]', s)
        if m:
            call = m.group(1)
            if call == prev_call:
                call_count += 1
            else:
                if call_count >= 5:
                    call_issues += 1
                call_count = 1
                prev_call = call
        else:
            if call_count >= 5:
                call_issues += 1
            call_count = 0
            prev_call = None
    if call_issues > 0:
        issues.append(('WARN', f'称呼回声: {call_issues} 处连续重复'))
    
    # 3.4 ≤3字短回声连续堆
    short_runs = 0
    cur_count = 0
    for line in lines:
        clean = re.sub(r'[——。""'']', '', line.strip())
        if 0 < len(clean) <= 3:
            cur_count += 1
        else:
            if cur_count >= 3:
                short_runs += 1
            cur_count = 0
    if short_runs > 0:
        issues.append(('WARN', f'{short_runs} 处短回声连续堆(≥3行)'))
    
    return issues, {'stacks': stacks, 'dash_total': dash_total}

# ============ 维度4: 叙事段密度 ============
def check_narrative(text):
    issues = []
    paragraphs = [p.strip() for p in re.split(r'\n\n+', text) 
                  if p.strip() and not p.strip().startswith('>') 
                  and not p.strip().startswith('#')]
    long_narr = sum(1 for p in paragraphs if count_han(p) >= 80)
    if long_narr < LONG_NARRATIVE_MIN:
        issues.append(('WARN', f'长叙事段: {long_narr} 段 ≥80字 < {LONG_NARRATIVE_MIN}'))
    else:
        issues.append(('PASS', f'长叙事段: {long_narr} 段'))
    return issues, {'long_narrative': long_narr}

# ============ 维度5: 章末钩子 ============
def check_end_hooks(text, fname, ch_num=None):
    issues = []
    if '章末钩子' not in text and '末段自检' not in text:
        issues.append(('WARN', '未检测到「章末钩子/末段自检」标识'))
    
    # 提取章号
    if ch_num is None:
        m = re.search(r'第(\d+)章', fname)
        ch_num = int(m.group(1)) if m else 0
    
    if ch_num > 0:
        cn_nums = "〇一二三四五六七八九十"
        if ch_num < 11:
            cn_n = cn_nums[ch_num]
        elif ch_num < 20:
            cn_n = "十" + cn_nums[ch_num - 10]
        else:
            cn_n = str(ch_num)
        
        markers = [
            f'第{cn_n}章 完', f'第{cn_n}章完',
            f'第{ch_num}章 完', f'第{ch_num}章完',
        ]
        if not any(mk in text for mk in markers):
            issues.append(('FAIL', f'未检测到「第{ch_num}章 完」标注'))
    
    return issues, {'has_hook': '章末钩子' in text}

# ============ 维度6: 越界角色 ============
def check_forbidden_chars(text):
    issues = []
    found = []
    for char in FORBIDDEN_CHARS:
        count = text.count(char)
        if count > 0:
            found.append(f'{char}({count}次)')
    if found:
        issues.append(('FAIL', f'越界角色: {", ".join(found)}'))
    else:
        issues.append(('PASS', '越界角色: 无'))
    return issues

# ============ 维度7: 开头禁项 ============
def check_opening(text):
    issues = []
    first_line = ''
    for line in text.split('\n'):
        if line.strip() and not line.strip().startswith('#'):
            first_line = line.strip()
            break
    if re.match(r'^\d+年\d+月\d+日', first_line):
        issues.append(('FAIL', '开头违规: 日期开头'))
    if '【本章数据】' in text:
        issues.append(('FAIL', '开头违规: 数据卡'))
    return issues

# ============ 维度8: 伏笔一致性（读取设定文件） ============
def check_hooks_from_outline(text, outline_text):
    """从设定.md检测伏笔一致性（仅在有设定文件时跑）"""
    issues = []
    if not outline_text:
        return issues, {}
    
    hooks = []
    for m in re.finditer(r'\| (F\d+) \| (.+?) \| Ch(\d+) \| Ch(\d+) \|', outline_text):
        hook_id, content, planted, redeemed = m.groups()
        if '—' not in content[:3]:
            hooks.append({
                'id': hook_id, 'content': content.strip(),
                'planted': int(planted), 'redeemed': int(redeemed)
            })
    
    for h in hooks:
        if h['planted'] >= h['redeemed'] and h['redeemed'] != 0:
            issues.append(('WARN', f"伏笔 {h['id']}: 埋入Ch{h['planted']} >= 回收Ch{h['redeemed']}"))
    
    return issues, {'hooks': len(hooks)}

# ============ 维度9: 规则一致性 ============
LOCKED_RULES = {
    "R1": "本店禁止任何暴力行为",
    "R2": "本店不换记忆",
    "R3": "本店商品由店员自行定价",
    "R4": "概不赊账",
    "R5": "本店欢迎活人",
    "R6": "本店不得倒闭",
}
RULE_BAD_VARIANTS = {
    "本店禁止任何暴力行为": ["本店允许任何暴力", "本店不禁止暴力"],
    "本店不换记忆": ["本店可以换记忆", "本店换记忆"],
    "概不赊账": ["可以赊账", "欢迎赊账"],
    "本店不得倒闭": ["本店可以倒闭", "本店可以关门"],
}

def check_rules(text):
    issues = []
    for rid, rule in LOCKED_RULES.items():
        bads = RULE_BAD_VARIANTS.get(rule, [])
        for bad in bads:
            if bad in text:
                issues.append(('FAIL', f'规则破坏「{rid}」: 出现「{bad}」'))
    return issues

# ============ 主函数 ============
def check_chapter(filepath, outline_text=''):
    text = filepath.read_text(encoding='utf-8')
    lines = text.split('\n')
    fname = filepath.name
    
    all_issues = []
    all_summary = {}
    
    # 维度1: 字数
    wc_issues, wc_sum = check_word_count(text, fname)
    all_issues.extend(wc_issues)
    all_summary.update(wc_sum)
    
    # 维度2: 对话
    dl_issues, dl_sum = check_dialogue(text)
    all_issues.extend(dl_issues)
    all_summary.update(dl_sum)
    
    # 维度3: 反模式
    ap_issues, ap_sum = check_antipatterns(text, lines)
    all_issues.extend(ap_issues)
    all_summary.update(ap_sum)
    
    # 维度4: 叙事段
    nr_issues, nr_sum = check_narrative(text)
    all_issues.extend(nr_issues)
    all_summary.update(nr_sum)
    
    # 维度5: 钩子
    eh_issues, eh_sum = check_end_hooks(text, fname)
    all_issues.extend(eh_issues)
    all_summary.update(eh_sum)
    
    # 维度6: 越界角色
    fc_issues = check_forbidden_chars(text)
    all_issues.extend(fc_issues)
    
    # 维度7: 开头
    op_issues = check_opening(text)
    all_issues.extend(op_issues)
    
    # 维度8: 伏笔
    hk_issues, hk_sum = check_hooks_from_outline(text, outline_text)
    all_issues.extend(hk_issues)
    all_summary.update(hk_sum)
    
    # 维度9: 规则
    rl_issues = check_rules(text)
    all_issues.extend(rl_issues)
    
    # 计算 verdict
    fails = [i for i in all_issues if i[0] == 'FAIL']
    warns = [i for i in all_issues if i[0] == 'WARN']
    
    if len(fails) >= 2:
        verdict = '🔴🔴 必须重写'
    elif len(fails) >= 1:
        verdict = '🔴 不合格'
    elif warns:
        verdict = '🟡 建议精修'
    else:
        verdict = '✅ 通过'
    
    return verdict, all_issues, all_summary

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    files = []
    outline_text = ''
    
    for arg in sys.argv[1:]:
        if arg.startswith('--book='):
            book = arg.split('=', 1)[1]
            outline_path = Path.cwd() / 'outline' / '设定.md'
            if outline_path.exists():
                outline_text = outline_path.read_text(encoding='utf-8')
            continue
        p = Path(arg)
        if p.exists():
            files.append(p)
    
    if not files:
        # 默认扫 chapters/
        chapters_dir = Path('chapters')
        if chapters_dir.exists():
            files = sorted(chapters_dir.glob('*.md'))
    
    if not files:
        print('未找到章节文件')
        sys.exit(1)
    
    # 表头
    print(f"{'章节':<35} {'汉字':>5} {'对话%':>5} {'破折':>4} {'叙事':>4} {'判定'}")
    print('-' * 70)
    
    all_fails = 0
    for f in files:
        verdict, issues, summary = check_chapter(f, outline_text)
        han = summary.get('han', 0)
        dial_pct = summary.get('dial_pct', 0)
        stacks = summary.get('stacks', 0)
        long_narr = summary.get('long_narrative', 0)
        
        print(f"{f.name:<35} {han:>5} {dial_pct:>4}% {stacks:>4} {long_narr:>4} {verdict}")
        
        for status, detail in issues:
            icon = '❌' if status == 'FAIL' else ('⚠️' if status == 'WARN' else '✅')
            print(f"    {icon} {detail}")
        
        if 'FAIL' in verdict:
            all_fails += 1
    
    # 汇总
    print(f"\n=== 汇总 ===")
    print(f"检查文件: {len(files)}")
    print(f"不合格: {all_fails}")
    
    if all_fails == 0:
        print("\n🟢 全部通过")
        return 0
    else:
        print(f"\n🔴 {all_fails} 个文件需要修复")
        return 1

if __name__ == '__main__':
    sys.exit(main())
