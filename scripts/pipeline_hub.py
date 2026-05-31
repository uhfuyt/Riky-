#!/usr/bin/env python3
"""
暗黑星火 · 统一数据中枢
========================
每10分钟由cron运行，聚合所有模块输出，给GPT提供统一的市场读数。
不再重复采集数据，只做整合和转发。

输出: analysis/pipeline_status.json
"""
import json, time, os, sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/home/admin/charon')
ANALYSIS = BASE / 'analysis'
BOT_LOGS = BASE / 'bot_logs'
SCRIPTS = BASE / 'scripts'

# ── 路径常量 ──────────────────────────────────────────
ADVISORY_FILE  = BOT_LOGS / 'advisory.json'
SMART_JSON     = Path('/tmp/smart_money_live.json')
RETRO_V2       = BOT_LOGS / 'retro_v2_history.json'
MEMORY_PERF    = BASE / 'memory' / 'strategy_performance.json'
REPORT_FILE    = BOT_LOGS / 'sovereign_gpt_report.json'

def log(msg):
    print(f"[数据中枢 {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── 读取各模块输出 ──────────────────────────────────

def load_advisory():
    """读ds0_analyst的advisory.json（5月18日后停止更新，标记stale）"""
    if not ADVISORY_FILE.exists():
        return {'exists': False, 'stale': True, 'regime': 'unknown'}
    try:
        d = json.loads(ADVISORY_FILE.read_text())
        # 判断是否stale（>24小时未更新）
        updated_at = d.get('time', '')
        if updated_at:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                stale = age_h > 24
            except:
                stale = True
        else:
            stale = True
        return {'exists': True, 'stale': stale, **d}
    except:
        return {'exists': False, 'stale': True, 'regime': 'unknown'}

def load_smart_money():
    """读smart_money_live.py输出的JSON"""
    if not SMART_JSON.exists():
        return {'exists': False, 'signals': []}
    try:
        d = json.loads(SMART_JSON.read_text())
        return {'exists': True, **d}
    except:
        return {'exists': False, 'signals': []}

def load_retro():
    """读每日复盘最新记录"""
    if not RETRO_V2.exists():
        return {'exists': False}
    try:
        hist = json.loads(RETRO_V2.read_text())
        if isinstance(hist, list) and hist:
            latest = hist[-1]
            return {'exists': True, 'latest': latest}
        elif isinstance(hist, dict):
            return {'exists': True, 'latest': hist}
        return {'exists': False}
    except:
        return {'exists': False}

def load_memory():
    """读memory/strategy_performance.json"""
    if not MEMORY_PERF.exists():
        return {'exists': False, 'strategies': {}}
    try:
        d = json.loads(MEMORY_PERF.read_text())
        return {'exists': True, **d}
    except:
        return {'exists': False, 'strategies': {}}

def load_sovereign_report():
    """读虚拟盘最新报告"""
    if not REPORT_FILE.exists():
        return {'exists': False}
    try:
        d = json.loads(REPORT_FILE.read_text())
        return {'exists': True, **d}
    except:
        return {'exists': False}

# ── 构建统一信号评分 ─────────────────────────────────

def build_signal_score(smart_data: dict) -> dict:
    """
    基于聪明钱数据生成信号评分
    返回: {signal: 'long'|'short'|'neutral', score: 0-1, reason: str}
    """
    if not smart_data.get('exists'):
        return {'signal': 'neutral', 'score': 0.0, 'reason': '无数据'}

    signals = smart_data.get('signals', [])
    alerts = smart_data.get('alerts', [])

    # 统计极端信号
    short_signals = [a for a in alerts if a[0] == 'short']  # 极端多头费率→聪明钱做空
    long_signals  = [a for a in alerts if a[0] == 'long']   # 极端空头费率→聪明钱做多

    score = 0.0
    reasons = []

    if short_signals:
        score += len(short_signals) * 0.4
        reasons.append(f'空头信号{len(short_signals)}个(费率极端)')
    if long_signals:
        score += len(long_signals) * 0.4
        reasons.append(f'多头信号{len(long_signals)}个(费率极端)')

    # 额外加分：成交量>$500M
    for s in signals:
        if '📊' in s and 'M' in s:
            score += 0.2
            reasons.append('成交量异常')
        if '⚡' in s:
            score += 0.1
            reasons.append('波动率异常')

    score = min(score, 1.0)

    if score >= 0.6:
        direction = 'short' if short_signals else 'long'
    elif score <= 0.1:
        direction = 'long' if long_signals else 'neutral'
    else:
        direction = 'neutral'

    return {
        'signal': direction,
        'score': round(score, 2),
        'reason': ', '.join(reasons) if reasons else '无极端信号'
    }

# ── 市场概览 ────────────────────────────────────────

def market_overview() -> dict:
    """轻量级市场概览（读取现有数据，不重复采集）"""
    overview = {
        'regime': 'unknown',
        'trend': 'neutral',
        'fear_greed': 50,
        'smart_money_signal': 'neutral',
        'smart_money_score': 0.0,
        'ds0_advisory_stale': True,
        'retro_trades': 0,
        'retro_winrate': 0.0,
    }

    # 1. ds0_advisory
    adv = load_advisory()
    if adv.get('exists'):
        overview['regime'] = adv.get('regime', 'unknown')
        overview['ds0_advisory_stale'] = adv.get('stale', True)

    # 2. 聪明钱
    smart = load_smart_money()
    if smart.get('exists'):
        sig = build_signal_score(smart)
        overview['smart_money_signal'] = sig['signal']
        overview['smart_money_score'] = sig['score']

    # 3. 复盘数据
    retro = load_retro()
    if retro.get('exists'):
        latest = retro.get('latest', {})
        overview['retro_trades'] = latest.get('trades', 0)
        overview['retro_winrate'] = latest.get('winrate', 0.0)
        overview['retro_pnl'] = latest.get('total_pnl', 0.0)

    return overview

# ── 策略状态摘要 ─────────────────────────────────────

def strategy_summary() -> dict:
    """汇总所有策略状态"""
    mem = load_memory()
    strategies = mem.get('strategies', {})

    summary = {
        'total': len(strategies),
        'profitable': sum(1 for s in strategies.values() if s.get('pnl', 0) > 0),
        'losing': sum(1 for s in strategies.values() if s.get('pnl', 0) < 0),
        'active': sum(1 for s in strategies.values() if s.get('has_position', False)),
        'top_performer': None,
        'worst_performer': None,
    }

    if strategies:
        sorted_strategies = sorted(strategies.items(), key=lambda x: x[1].get('pnl', 0), reverse=True)
        summary['top_performer'] = {'name': sorted_strategies[0][0], 'pnl': sorted_strategies[0][1].get('pnl', 0)}
        summary['worst_performer'] = {'name': sorted_strategies[-1][0], 'pnl': sorted_strategies[-1][1].get('pnl', 0)}

    return summary

# ── 主函数 ────────────────────────────────────────────

def main():
    log('启动数据中枢聚合...')

    overview = market_overview()
    strategies = strategy_summary()
    smart = load_smart_money()
    smart_signals = build_signal_score(smart)

    # 读虚拟盘报告
    sovereign = load_sovereign_report()
    sovereign_status = {}
    if sovereign.get('exists'):
        sovereign_status = {
            'cash': sovereign.get('cash', 0),
            'equity': sovereign.get('equity', 0),
            'positions_count': len(sovereign.get('positions', [])),
            'total_pnl': sovereign.get('total_pnl', 0),
            'trades': sovereign.get('trades', 0),
        }

    status = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'market': overview,
        'signals': smart_signals,
        'strategies': strategies,
        'sovereign': sovereign_status,
        'modules': {
            'advisory': load_advisory(),
            'smart_money': {'exists': smart.get('exists'), 'updated': smart.get('updated', ''), 'signal_count': len(smart.get('signals', []))},
        }
    }

    out_file = ANALYSIS / 'pipeline_status.json'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(status, indent=2, ensure_ascii=False))
    log(f"✅ 已写入 {out_file}")
    log(f"   市场: {overview['regime']} | 聪明钱: {smart_signals['signal']}({smart_signals['score']:.0%}) | ds0_advisory: {'⚠️过期' if overview['ds0_advisory_stale'] else '✅正常'}")

    # 打印简洁摘要供cron日志用
    active_pos = strategies.get('active', 0)
    top = strategies.get('top_performer', {})
    print(f"📊 策略: {strategies['profitable']}赢/{strategies['losing']}亏 | 持仓: {active_pos} | 最高: {top.get('name','?')} {top.get('pnl',0):+.2f}u")

if __name__ == '__main__':
    main()
