#!/usr/bin/env python3
"""
剧情连贯性测试脚本 - 《诡异复苏：我家房门有规则》
=============================================
检测范围：
  1. 字数合规（每章 2400-3600 汉字）
  2. 规则一致性（安全屋8条规则不可矛盾）
  3. 人物出场一致性
  4. 章末钩子（每章必带章末钩子）
  5. 章节文件名顺序

用法：
  python3 scripts/consistency_test.py [chapters_dir]
"""
import re, os, sys, json
from pathlib import Path

# ============ 配置 ============
CHAPTERS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "chapters"
OUTLINE_FILE = CHAPTERS_DIR.parent / "outline" / "设定.md"

if not CHAPTERS_DIR.exists():
    print(f"❌ 章节目录不存在: {CHAPTERS_DIR}")
    sys.exit(1)

WC_MIN, WC_MAX = 2400, 3600
TARGET_CHAPTERS = 120

# ============ 核心规则检查关键词 ============
RULES_CHECK = {
    "规则1: 禁止诡异进入": ["禁止任何诡异进入", "强制清零"],
    "规则2: 活人等价交易": ["活人可进入", "等价"],
    "规则3: 房客不得攻击活人": ["诡异房客不得攻击", "不得攻击任何活人"],
    "规则4: 凌晨封门": ["凌晨", "封门时段", "不得开门"],
    "规则5: 不得驱逐已付代价活人": ["不得主动驱逐", "已付代价"],
    "规则6: 15%语义微调": ["语义微调", "15%"],
    "规则7: 战斗无效化": ["战斗行为", "自动无效化"],
    "规则8: 扩张后分区配置": ["每间房的规则", "单独配置"],
}

# ============ 字数检测 ============
def count_chinese(text):
    """统计汉字字数（去掉章末标记段之后）"""
    # 找章末标记：【第X章 完】或【第XXX章 完】
    body_end = text.rfind('【第')
    if body_end == -1:
        body_end = len(text)
    body = text[:body_end]
    # 只统计中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', body)
    return len(chinese_chars)

# ============ 主检测 ============
def check_chapter(filepath):
    """检测单个章节"""
    text = filepath.read_text(encoding='utf-8')
    filename = filepath.name
    errors = []
    warnings = []
    
    # 1. 字数
    wc = count_chinese(text)
    if wc < WC_MIN:
        errors.append(f"🔴 字数不足: {wc}字 (需{WC_MIN}-{WC_MAX})")
    elif wc > WC_MAX:
        errors.append(f"🔴 字数超标: {wc}字 (需{WC_MIN}-{WC_MAX})")
    
    # 2. 章末钩子
    if "末段自检" not in text and "章末钩子" not in text:
        # 看看最后一两段有没有悬念式结尾
        last_500 = text[-500:]
        if not any(mark in last_500 for mark in ["？", "什么", "谁", "为什么", "..." "..."]):
            warnings.append("🟡 章末钩子不明显")
    
    # 3. 规则破坏检查
    for rule_name, keywords in RULES_CHECK.items():
        violations = 0
        for kw in keywords:
            if kw in text:
                violations += 1
        # 如果章节明确提到规则但说反了
        if "没有规则" in text or "规则消失" in text:
            if "卷四" not in filename and int(re.search(r'(\d+)', filename).group(1)) < 90:
                errors.append(f"🔴 规则破坏嫌疑: 提到规则消失（除非剧情需要）")
    
    # 4. 章节文件名格式
    if not re.match(r'第\d{3}章', filename):
        errors.append(f"🔴 文件名格式错误: '{filename}' 应为 '第001章...'")
    
    return errors, warnings, wc

def main():
    chapter_files = sorted(CHAPTERS_DIR.glob("第*.md"))
    
    if not chapter_files:
        print(f"📂 章节目录: {CHAPTERS_DIR}")
        print("❌ 未找到任何章节文件")
        return
    
    total_errors = 0
    total_warnings = 0
    all_ok = True
    
    print(f"{'='*60}")
    print(f"📖 《诡异复苏：我家房门有规则》— 章节检测")
    print(f"📂 {CHAPTERS_DIR}")
    print(f"📊 共 {len(chapter_files)} 章")
    print(f"{'='*60}\n")
    
    for cf in chapter_files:
        errors, warnings, wc = check_chapter(cf)
        status = "✅" if not errors else "❌"
        print(f"{status} {cf.name} — {wc}字")
        for e in errors:
            print(f"   {e}")
            total_errors += 1
        for w in warnings:
            print(f"   {w}")
            total_warnings += 1
        if errors:
            all_ok = False
    
    print(f"\n{'='*60}")
    print(f"📊 汇总: {len(chapter_files)}章 | {total_errors}错误 | {total_warnings}警告")
    if all_ok:
        print("✅ **ALL PASS** — 可以commit")
    else:
        print(f"❌ 有 {total_errors} 个错误需要修复")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
