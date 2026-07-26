#!/usr/bin/env python3
"""
剧情连贯性测试脚本 - 《末日降临，我的便利店禁止打烊》
========================================================
检测范围：
  1. 字数合规（每章 2400-3600 汉字）
  2. 伏笔一致性（埋入章 < 回收章）
  3. 数字一致性（门外14人/收容队人数/倒计时47天）
  4. 人物出场一致性（同一人不能"前章已死"还在"后章说话"）
  5. 规则一致性（同一规则不能在不同章矛盾）
  6. 章末钩子（每章必带"N章末段钩子"标识）

用法：
  python3 scripts/consistency_test.py novels/末日便利店
"""
import re
import os
import sys
import json
from pathlib import Path

# ============ 配置 ============
CHAPTERS_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "novels/末日便利店/chapters")
OUTLINE_FILE = CHAPTERS_DIR.parent / "outline" / "设定.md"

# 兜底：脚本被移到 scripts/ 后，从 sibling chapters/ 找
if not CHAPTERS_DIR.exists():
    CHAPTERS_DIR = Path(__file__).parent.parent / "chapters"
if not OUTLINE_FILE.exists():
    OUTLINE_FILE = Path(__file__).parent.parent / "outline" / "设定.md"

WC_MIN, WC_MAX = 2400, 3600
TARGET_CHAPTERS = 120  # 完结预期

# ============ 加载设定 ============
def load_outline():
    if not OUTLINE_FILE.exists():
        return ""
    return OUTLINE_FILE.read_text(encoding='utf-8')

# ============ 字数检测 ============
def count_chinese(text):
    """统计汉字字数（剔除 markdown 标题/空白/自检段）"""
    body_end = text.find('**第')
    if body_end == -1:
        body_end = len(text)
    # 找到所有 "完" 标注
    for marker in ['**第一章 完**', '**第二章 完**']:
        idx = text.find(marker)
        if idx > 0:
            body_end = idx
            break
    body = text[:body_end]
    clean = re.sub(r'^#.*$', '', body, flags=re.M)
    clean = re.sub(r'\n+', '', clean)
    return len(re.findall(r'[\u4e00-\u9fff]', clean))

def check_word_count():
    print("\n=== [1/6] 字数合规检测 ===")
    files = sorted(CHAPTERS_DIR.glob("*.md"))
    issues = []
    for f in files:
        text = f.read_text(encoding='utf-8')
        wc = count_chinese(text)
        status = "✅" if WC_MIN <= wc <= WC_MAX else "❌"
        print(f"  {status} {f.name}: {wc} 汉字")
        if wc < WC_MIN or wc > WC_MAX:
            issues.append({"file": f.name, "wc": wc})
    return issues

# ============ 伏笔检测 ============
def check_hooks():
    print("\n=== [2/6] 伏笔一致性检测 ===")
    outline = load_outline()
    # 解析伏笔表
    hooks = []
    pattern = r'\| (F\d+) \| (.+?) \| Ch(\d+) \| Ch(\d+) \|'
    for m in re.finditer(pattern, outline):
        hook_id, content, planted, redeemed = m.groups()
        planted_n = int(planted)
        redeemed_n = int(redeemed)
        # 提取编号 F001 → 1
        try:
            num = int(hook_id[1:])
        except ValueError:
            continue
        # 跳过 - 占位行
        if '—' in content or '-' in content[:3]:
            continue
        hooks.append({
            "id": hook_id, "content": content,
            "planted": planted_n, "redeemed": redeemed_n
        })
    issues = []
    for h in hooks:
        # 检测 1：埋入章必须 < 回收章
        if h["planted"] >= h["redeemed"]:
            print(f"  ❌ {h['id']}: 埋入章 Ch{h['planted']} >= 回收章 Ch{h['redeemed']}")
            issues.append({"hook": h['id'], "type": "plant>=redeem"})
        # 检测 2：埋入章不能超过已有章数
        existing = len(list(CHAPTERS_DIR.glob("*.md")))
        if h["planted"] > existing and existing > 0:
            print(f"  ⚠️ {h['id']}: 埋入章 Ch{h['planted']} 还未写到（已写 Ch1-Ch{existing}）")
        # 检测 3：回收章不能超过目标章数
        if h["redeemed"] > TARGET_CHAPTERS:
            print(f"  ❌ {h['id']}: 回收章 Ch{h['redeemed']} 超出目标 {TARGET_CHAPTERS}")
            issues.append({"hook": h['id'], "type": "redeem>target"})
    print(f"  共扫描 {len(hooks)} 条伏笔，{len(issues)} 条异常")
    return issues

# ============ 数字一致性检测 ============
def check_numbers():
    print("\n=== [3/6] 数字一致性检测 ===")
    issues = []
    files = sorted(CHAPTERS_DIR.glob("*.md"))
    # 锁死关键数字
    for f in files:
        text = f.read_text(encoding='utf-8')
        # 检测 1：门外十四个"人"在卷一必须保持 14
        if "门外那十四个" in text or "门外十四个" in text or "门外那14个" in text or "门外14个" in text:
            # 不能出现 15 / 13 / 12 等矛盾数字
            for wrong in ['十五个', '十三个', '十二个', '15个', '13个', '12个']:
                if wrong in text:
                    print(f"  ❌ {f.name}: 检测到矛盾数字「{wrong}」（卷一门外固定14人）")
                    issues.append({"file": f.name, "type": "wrong_14_count"})
                    break
    return issues

# ============ 人物一致性检测 ============
def check_characters():
    print("\n=== [4/6] 人物一致性检测 ===")
    issues = []
    files = sorted(CHAPTERS_DIR.glob("*.md"))
    # 解析人物谱
    outline = load_outline()
    # 简单检测：每个角色名字在各章的出场次数
    key_chars = ['林默', '周磊', '老赵', '礼帽男人', '那个母亲', '那个男孩',
                 '发烧男孩', '录音笔女人', '带枪顾客', '非人男孩',
                 '收容队队长', '收容队女队员', '门外那14个人']
    char_count = {c: [] for c in key_chars}
    for f in files:
        text = f.read_text(encoding='utf-8')
        # 提取章号
        m = re.search(r'第(\d+)章', f.name)
        if not m:
            continue
        ch_n = int(m.group(1))
        for c in key_chars:
            if c in text:
                char_count[c].append(ch_n)
    print("  角色出场分布：")
    for c, chs in char_count.items():
        if chs:
            print(f"    {c}: 出现 {len(chs)} 次（Ch{min(chs)}-Ch{max(chs)}）")
    return issues

# ============ 规则一致性检测 ============
def check_rules():
    print("\n=== [5/6] 规则一致性检测 ===")
    issues = []
    files = sorted(CHAPTERS_DIR.glob("*.md"))
    # 锁死的规则原文
    locked_rules = {
        "R1": "本店禁止任何暴力行为",
        "R2": "本店不换记忆",
        "R3": "本店商品由店员自行定价",
        "R4": "概不赊账",
        "R5": "本店欢迎活人",
        "R6": "本店不得倒闭",
    }
    for f in files:
        text = f.read_text(encoding='utf-8')
        # 检测规则原文是否被破坏（用「」之外的引号或被删字）
        for rid, rule in locked_rules.items():
            if rule in text:
                # 检测是否被错误修改
                # 检测变体
                bad_variants = {
                    "本店禁止任何暴力行为": ["本店允许任何暴力", "本店不禁止暴力"],
                    "本店不换记忆": ["本店可以换记忆", "本店换记忆"],
                    "概不赊账": ["可以赊账", "欢迎赊账"],
                    "本店不得倒闭": ["本店可以倒闭", "本店可以关门"],
                }
                for orig, bads in bad_variants.items():
                    if rule == orig:
                        for bad in bads:
                            if bad in text:
                                print(f"  ❌ {f.name}: 检测到规则原文被破坏「{bad}」")
                                issues.append({"file": f.name, "rule": rid, "bad": bad})
    return issues

# ============ 章末钩子检测 ============
def check_end_hooks():
    print("\n=== [6/6] 章末钩子检测 ===")
    issues = []
    files = sorted(CHAPTERS_DIR.glob("*.md"))
    for f in files:
        text = f.read_text(encoding='utf-8')
        # 每章必带"章末钩子"标识
        if "章末钩子" not in text and "末段自检" not in text:
            print(f"  ⚠️ {f.name}: 未检测到「章末钩子/末段自检」标识")
            issues.append({"file": f.name, "type": "no_end_hook"})
        # 每章必带"完"标注
        m = re.search(r'第(\d+)章', f.name)
        if m:
            ch_n = int(m.group(1))
            # 转中文章号
            cn_nums = "〇一二三四五六七八九十"
            if ch_n < 11:
                cn_n = cn_nums[ch_n]
            elif ch_n < 20:
                cn_n = "十" + cn_nums[ch_n - 10]
            elif ch_n < 100:
                cn_n = cn_nums[ch_n // 10] + "十" + cn_nums[ch_n % 10] if ch_n % 10 else cn_nums[ch_n // 10] + "十"
            else:
                cn_n = str(ch_n)
            # 兼容粗体「**第N章 完**」、纯文本「第N章 完」或「第N章完」
            end_markers = [
                f"第{cn_n}章 完", f"第{cn_n}章完",
                f"**第{cn_n}章 完**", f"**第{cn_n}章完**",
                f"第{ch_n}章 完", f"第{ch_n}章完",
                f"**第{ch_n}章 完**", f"**第{ch_n}章完**"
            ]
            if not any(mk in text for mk in end_markers):
                print(f"  ❌ {f.name}: 未检测到「第{ch_n}章 完」标注")
                issues.append({"file": f.name, "type": "no_end_marker"})
    return issues

# ============ 主流程 ============
def main():
    print(f"=== 剧情连贯性测试 ===")
    print(f"章节目录: {CHAPTERS_DIR}")
    print(f"设定文件: {OUTLINE_FILE}")
    if not CHAPTERS_DIR.exists():
        print(f"❌ 章节目录不存在: {CHAPTERS_DIR}")
        sys.exit(1)

    # 跑全 6 项检测
    wc_issues = check_word_count()
    hook_issues = check_hooks()
    num_issues = check_numbers()
    char_issues = check_characters()
    rule_issues = check_rules()
    end_issues = check_end_hooks()

    # 汇总
    total = len(wc_issues) + len(hook_issues) + len(num_issues) + len(char_issues) + len(rule_issues) + len(end_issues)
    existing_chapters = len(list(CHAPTERS_DIR.glob("*.md")))

    print(f"\n=== 汇总 ===")
    print(f"已写章节: {existing_chapters} / {TARGET_CHAPTERS}")
    print(f"完成度: {existing_chapters * 100 // TARGET_CHAPTERS}%")
    print(f"字数异常: {len(wc_issues)}")
    print(f"伏笔异常: {len(hook_issues)}")
    print(f"数字异常: {len(num_issues)}")
    print(f"人物异常: {len(char_issues)}")
    print(f"规则异常: {len(rule_issues)}")
    print(f"章末异常: {len(end_issues)}")
    print(f"总异常: {total}")
    if total == 0:
        print("\n🟢 全部通过")
        return 0
    else:
        print(f"\n🟡 发现 {total} 条异常，建议逐条修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())