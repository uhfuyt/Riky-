# 合理化检测器 — 检查剧情是否"经得起推敲"
"""
[DS-0] 8维度合理化检测,防"剧情崩塌":
1. 数字一致性: 返利倍数 × 亏损 = 返利,数学对不对?
2. 数值膨胀: 相邻章主角资产/能力,跨度是否合理?
3. 升级曲线: 等级提升阈值,是否过快/过慢?
4. 时间逻辑: 同一日/同一时段,事件是否能都发生?
5. 因果链: 反派行动→主角应对,是否合理?
6. 系统规则一致性: 禁区/限制是否被违反?
7. 角色行为: 角色性格/能力,做的事是否匹配?
8. 开篇格式(2026-07-03 新增):禁日期/作者注/数据卡/方括号剧透/setup
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import codex

def check(book, text, ch_num):
    """主检测函数"""
    data = codex.load_book(book)

    # 开篇格式独立检测 — 不依赖codex(2026-07-03)
    opening_score = _check_opening_format(text)

    if not data:
        return {
            'total': 50,
            'verdict': '⚠️ 无codex数据',
            'details': {},
            'opening_format_score': opening_score,
            'opening_format_failed': getattr(_check_opening_format, 'failed', False),
            'opening_format_issues': getattr(_check_opening_format, 'issues', []),
            'issues': [f'⚠️ 无codex数据, 仅运行开篇格式检测'],
        }

    report = {
        'math_score': _check_math(text, data, ch_num),
        'inflation_score': _check_inflation(book, data, ch_num),
        'level_curve_score': _check_level_curve(data, ch_num),
        'time_logic_score': _check_time_logic(text),
        'causality_score': _check_causality(text),
        'rule_score': _check_rule_violation(book, text, data),
        'character_score': _check_character_consistency(book, text, data),
        'opening_format_score': opening_score,
    }

    weights = [0.20, 0.13, 0.12, 0.10, 0.12, 0.08, 0.10, 0.15]  # 8维加权, 开篇格式15%
    total = sum(s * w for s, w in zip(report.values(), weights))
    report['total'] = round(total, 1)
    report['verdict'] = _verdict(total)
    report['issues'] = _issues(report, book, ch_num)

    # 开篇格式FAIL硬告警 (2026-07-03 新增)
    if _check_opening_format.failed:
        report['opening_format_failed'] = True
        report['opening_format_issues'] = _check_opening_format.issues

    return report

def _check_math(text, data, ch_num):
    """维度1:数字一致性 — 返利 = 亏损 × 倍数,数学必须对"""
    rules = data.get('rules', {})
    multiple = data.get('current_state', {}).get('multiple', 1)
    daily_limit = data.get('current_state', {}).get('daily_limit')
    
    # 提取章节里的亏损+返利数字 - 单位必须捕获
    pattern = re.compile(r'(?:亏(?:损)?|花(?:了)?|支(?:出)?|投(?:入)?)\s*(\d+(?:\.\d+)?\s*[万亿千百元块]?)\s*[.,]?\s*(?:.{0,40}?)(?:返(?:利)?|到账|得到|收(?:到)?|返)\s*(\d+(?:\.\d+)?\s*[万亿千百元块]?)', re.S)
    
    score = 100
    issues_count = 0
    
    for m in pattern.finditer(text):
        loss_raw, ret_raw = m.group(1), m.group(2)
        loss = _parse_money(loss_raw)
        ret = _parse_money(ret_raw)
        if loss is None or ret is None or loss == 0:
            continue
        
        # 期望返利 = 亏损 × 倍数 (允许±30%误差)
        expected = loss * multiple
        actual_ratio = ret / loss
        expected_ratio = multiple
        
        # 如果有"待补"或"分期"关键词,允许超过(因为日限额机制)
        if '待补' in m.group(0) or '分期' in m.group(0) or '日限' in m.group(0):
            continue
        
        if actual_ratio < expected_ratio * 0.5 or actual_ratio > expected_ratio * 2.0:
            score -= 25
            issues_count += 1
        elif abs(actual_ratio - expected_ratio) / expected_ratio > 0.2:
            score -= 10
            issues_count += 1
        
        # 检查日限额(只对"今天到账"判断,不是"理论返利")
        if daily_limit and ret > daily_limit:
            if '分期' not in text and '次日' not in text and '陆续' not in text and '待入账' not in text and '明日' not in text:
                score -= 20
                issues_count += 1
    
    return max(score, 0)

def _check_inflation(book, data, ch_num):
    """维度2:数值膨胀 — 相邻章主角资产跨度"""
    state = data.get('current_state', {})
    cash = state.get('cash', 0)
    
    # 历史现金记录
    history = data.get('history', [])
    if len(history) < 2:
        return 85  # 样本不足
    
    last_cash = history[-1].get('cash', cash) if history else 0
    if last_cash == 0:
        return 85
    
    ratio = cash / last_cash if last_cash > 0 else 1
    # 跨度 < 5x 正常, 5-20x 略快, > 20x 异常
    if ratio < 5:
        return 95
    elif ratio < 20:
        return 75
    elif ratio < 100:
        return 50
    else:
        return 25  # 严重通胀

def _check_level_curve(data, ch_num):
    """维度3:升级曲线 — 等级提升是否合理"""
    state = data.get('current_state', {})
    level = state.get('level', 'Lv.1')
    cumulative_loss = state.get('cumulative_loss', 0)
    
    rules = data.get('rules', {})
    thresholds = rules.get('level_curve', {})
    
    # 起点本: 6章到Lv.3, 番茄: 1章到Lv.1
    # 番茄Lv.1阈值=1万亏损,累计亏损19.6万 → 已超阈值
    # 但1章就升Lv.2 = 太快?
    
    # 提取当前等级和阈值
    cur_thresh = thresholds.get(level, {}).get('upgrade_threshold', 0)
    if cur_thresh == 0:
        return 80
    
    # 实际亏损 / 阈值
    progress = cumulative_loss / cur_thresh if cur_thresh > 0 else 0
    
    # 番茄Ch1已超阈值20倍 — 太快,应升级
    score = 90
    if progress > 10 and ch_num <= 3:
        score -= 30  # 太快
    elif progress > 50 and ch_num <= 5:
        score -= 20
    
    return max(score, 30)

def _check_time_logic(text):
    """维度4:时间逻辑 — 同一日/时段事件是否能都发生?"""
    # 找时间标记
    time_markers = re.findall(r'(上午\d+点|下午\d+点|早上\d+点|中午\d+点|晚上\d+点|凌晨\d+点|夜里|深夜)', text)
    # 找"立刻""马上""随即"等时间词
    immediate = re.findall(r'(立刻|马上|随即|瞬间|一眨眼|不到\d+分钟)', text)
    
    # 简单检查: 一天内是否出现3个以上不同时段(暗示主角在1天内做了太多事)
    score = 90
    if len(set(time_markers)) > 5:
        score -= 25  # 一天5个时段,剧情太赶
    elif len(set(time_markers)) > 3:
        score -= 10
    return max(score, 0)

def _check_causality(text):
    """维度5:因果链 — 反派行动→主角应对,是否合理"""
    # 找反派动作
    villain_actions = re.findall(r'(王大龙.{0,15}(告|打|抓|威胁|派人|设局|断|封)|周公子.{0,15}(告|打|抓|威胁|派人|设局|断|封))', text)
    if not villain_actions:
        return 90
    
    # 找主角应对
    hero_responses = re.findall(r'(林北[舟辰].{0,15}(反|怼|挡|化解|反制|接招|打脸|反诉|当场))', text)
    
    # 每个反派动作应该至少有1个主角应对
    ratio = len(hero_responses) / max(len(villain_actions), 1)
    if ratio >= 1:
        return 90
    elif ratio >= 0.5:
        return 70
    else:
        return 40

def _check_rule_violation(book, text, data):
    """维度6:系统规则一致性 — 禁区/限制是否被违反"""
    rules = data.get('rules', {})
    ban_list = rules.get('ban_list', [])
    
    score = 95
    for ban in ban_list:
        # 排除常见的非违规用法
        if ban == '黄' and '黄了' in text: continue
        if ban == '骗' and '被骗' in text: continue
        if ban == '高利贷': continue
        
        # 只检测"主角靠xx赚钱/获得返利"模式,排除"对话中提到"
        violation_patterns = [
            rf'(林北[舟辰].{{0,20}}靠.{{0,10}}{ban}.{{0,10}}(赚|返|得))',
            rf'(林北[舟辰].{{0,20}}{ban}.{{0,10}}(赚了|返了|得了))',
        ]
        for vp in violation_patterns:
            if re.search(vp, text):
                score -= 30
                break
    return max(score, 0)

def _check_character_consistency(book, text, data):
    """维度7:角色行为 — 主角/反派做的事是否匹配人设"""
    chars = data.get('characters', [])
    main_char = None
    for c in chars:
        if c.get('role') == '主角':
            main_char = c
            break

    if not main_char:
        return 80

    personality = main_char.get('personality', '')
    voice_quotes = main_char.get('voice_quotes', [])

    score = 90
    # 主角有"嘴贱/腹黑"性格,应该出现调侃/吐槽
    if '嘴' in personality or '腹黑' in personality or '贫' in personality:
        if not re.search(r'(我.{0,5}(林北[舟辰]|穷)|唉|靠|操|呵|嘿|哼)', text):
            score -= 15

    # 主角有"心软/善良",应该出现帮助他人
    if '心软' in personality or '善良' in personality:
        if not re.search(r'(给了|帮助|捐|送|帮)', text):
            score -= 10

    return max(score, 30)


def _check_opening_format(text):
    """维度8(2026-07-03 新增):章节开头7禁 — 禁日期/作者注/数据卡/方括号剧透/章节名+分隔线/元叙述/setup段落

    用户原话:"日期是每个章节开头都是年月日,很尴尬"
    详见 web-novel-production SKILL.md → "🚨 章节开头7禁铁律"

    评分:
    - 100分起,触发1条 -25,触发2条 -50,触发3条+ → 0分(FAIL)
    - 检测维度:
      1. 日期开头 (YYYY年MM月DD日 / MM月DD日 / N月N日 / 周X)
      2. 章节内【本章数据】块
      3. 章节内【下一章预告】段
      4. 方括号剧透 ([DS-0] / [F00X] / [备注]等)
      5. 元叙述 (本章数据: / 五幕: / 字数:)
      6. 章节名+分隔线格式 (# 标题\n\n---)
      7. 开篇大段setup (故事发生在...)
    """
    score = 100
    issues = []

    # 取章节前30行作为开头检测范围
    lines = text.split('\n')
    head = '\n'.join(lines[:30])

    # 1. 日期开头
    date_patterns = [
        r'^\s*\d{4}年\d{1,2}月\d{1,2}日',  # 2026年7月4日
        r'^\s*\d{1,2}月\d{1,2}日',          # 7月4日
        r'^\s*周[一二三四五六日天]',           # 周一
        r'^\s*\d{4}\.\d{1,2}\.\d{1,2}',      # 2026.7.4
    ]
    for p in date_patterns:
        if re.search(p, head, re.MULTILINE):
            score -= 25
            issues.append('日期开头')
            break

    # 2. 章节内【本章数据】块 (含变体)
    if re.search(r'【本章数据】|【本章数据】|【数据卡】', text):
        score -= 25
        issues.append('作者注/数据卡')

    # 3. 章节内【下一章预告】段
    if re.search(r'【下一章预告】|【下章预告】|第二章《', text):
        score -= 25
        issues.append('下一章预告剧透')

    # 4. 方括号剧透(DS-0备注/F编号/审计标签)
    spoiler_patterns = [
        r'\[DS-0[^\]]*\]',
        r'\[F\d{3}[^\]]*\]',
        r'\[备注[^\]]*\]',
        r'\[审计[^\]]*\]',
        r'\[回收[^\]]*\]',
    ]
    for p in spoiler_patterns:
        if re.search(p, text):
            score -= 25
            issues.append('方括号剧透')
            break

    # 5. 元叙述(本章数据:/五幕:/字数:)
    meta_patterns = [
        r'本章数据[:：]',
        r'五幕[:：]',
        r'字数[:：].*\d+',
        r'爽点[:：].*\d+',
        r'钩子[:：].*\d+',
    ]
    meta_hit = 0
    for p in meta_patterns:
        if re.search(p, text):
            meta_hit += 1
    if meta_hit >= 1:
        score -= 25
        issues.append('元叙述(数据卡)')
    if meta_hit >= 2:
        score -= 25  # 二次扣分

    # 6. 章节名+分隔线(## + ---)
    if re.search(r'^# .+\n\n---', text, re.MULTILINE):
        score -= 15
        issues.append('章节名+分隔线格式')

    # 7. 开篇大段setup(故事发生在...)
    setup_patterns = [
        r'^\s*故事发生在',
        r'^\s*这是一[个段]',
        r'^\s*背景[:：]',
        r'^\s*话说',
    ]
    for p in setup_patterns:
        if re.search(p, head, re.MULTILINE):
            score -= 15
            issues.append('开篇setup')
            break

    # 记录issue到全局report
    _check_opening_format.issues = issues
    _check_opening_format.score = max(score, 0)
    _check_opening_format.failed = score < 60
    return max(score, 0)

def _parse_money(s):
    """把'1.5万' '20' '1000' '1万'解析成数字"""
    if not s:
        return None
    try:
        s = s.replace(',', '')
        if '万' in s:
            # 多种写法:'1.5万' '1万' '15万'
            val = s.replace('万', '')
            return float(val) * 10000
        elif '亿' in s:
            val = s.replace('亿', '')
            return float(val) * 100000000
        elif '千' in s:
            val = s.replace('千', '')
            return float(val) * 1000
        elif '百' in s:
            val = s.replace('百', '')
            return float(val) * 100
        else:
            return float(s)
    except:
        return None

def _verdict(total):
    if total >= 90: return '🟢 合理'
    if total >= 75: return '🟡 略有不合理'
    if total >= 60: return '🟠 需修'
    return '🔴 崩了'

def _issues(report, book, ch_num):
    issues = []
    if report['math_score'] < 70:
        issues.append(f'数学错误: 返利数字与亏损×倍数不匹配')
    if report['inflation_score'] < 50:
        issues.append(f'数值膨胀: 主角资产涨幅超20倍,需加限制')
    if report['level_curve_score'] < 60:
        issues.append(f'升级过快: Ch{ch_num}已超等级阈值,应升级或放慢')
    if report['time_logic_score'] < 70:
        issues.append(f'时间逻辑: 一天内5+时段,剧情太赶')
    if report['causality_score'] < 60:
        issues.append(f'因果链弱: 反派出招但主角应对不足')
    if report['rule_score'] < 70:
        issues.append(f'违反规则: 主角行为触碰金手指禁区')
    if report['character_score'] < 70:
        issues.append(f'人设不符: 主角行为与性格不匹配')
    # 开篇格式硬告警 (2026-07-03 新增)
    # 注: 函数属性 _check_opening_format.failed 是check()里赋值的, 但_issues()内不一定有
    # 直接用 report.opening_format_score 判断更可靠 (Ch6 = 0分 → 违规)
    if report.get('opening_format_score', 100) < 60:
        items = _check_opening_format.issues or ['开篇格式违规']
        # 锁死判断: 起点Ch1-3已发布(2026-07-03); 番茄全未发布(全新书, 全部可改)
        # book参数: 'qidian' = 起点 / 'fanqie' = 番茄
        locked_chapters = {'qidian': 3, 'fanqie': 0}
        max_locked = locked_chapters.get(book, 0)
        if ch_num <= max_locked:  # 在锁死范围内
            note = ' (⚠️ Ch1-{}已发布锁死, 无法改正文, 仅记录)'.format(max_locked)
        else:
            note = ' (🚨 新章节必须重写, 详见 web-novel-production SKILL.md → 章节开头7禁铁律)'
        issues.append(f'🚨 开篇格式违规: {", ".join(items)}{note}')
    if not issues:
        issues.append('✅ 合理')
    return issues


# 命令行测试
if __name__ == '__main__':
    import sys, os
    if len(sys.argv) < 3:
        print("Usage: python3 plausibility.py [qidian|fanqie] <chapter_file> [ch_num]")
        sys.exit(1)
    book = sys.argv[1]
    f = sys.argv[2]
    ch_num = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    text = open(f).read()
    report = check(book, text, ch_num)
    
    print(f"=== 合理化检测 [{book}] Ch{ch_num} ===")
    for k, v in report.items():
        if k in ['total', 'verdict']:
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: {v}")
    print(f"\n=== 问题清单 ===")
    for i in report['issues']:
        print(f"  {i}")