#!/usr/bin/env python3
"""
暗黑星火 · 30天回测引擎 V2.0 (2026-06-26)
适配 intel_data/{coin}_1h_30d.json 数据格式
跑 11 个策略 × 4 币 = 44 组对比
输出: 排名 + 每个策略的 PnL/夏普/胜率/回撤
"""
import json, os, sys, math
import numpy as np

DATA_DIR = '/home/admin/.hermes/mempalace/quant_trading/intel_data'
RESULT_DIR = '/home/admin/.hermes/mempalace/quant_trading/backtest_results'
os.makedirs(RESULT_DIR, exist_ok=True)

CAPITAL = 1000.0
FEE_TAKER = 0.0007
FEE_MAKER = 0.0002

# ── 指标函数 ──
def ema(s, p):
    a = np.array(s, dtype=float)
    if len(a) < p: return None
    k = 2.0/(p+1); o = np.empty_like(a); o[0]=a[0]
    for i in range(1,len(a)): o[i]=a[i]*k+o[i-1]*(1-k)
    return o

def rsi(closes, p=14):
    a = np.array(closes, dtype=float)
    if len(a) < p+1: return np.full(len(a), 50)
    d = np.diff(a); g = np.maximum(d,0); l = np.maximum(-d,0)
    ag = np.convolve(g, np.ones(p)/p, 'valid')
    al = np.convolve(l, np.ones(p)/p, 'valid')
    rs = np.divide(ag, al, out=np.ones_like(ag), where=al>1e-10)
    return np.concatenate([[50]*p, 100 - 100/(1+rs)])

def atr_val(highs, lows, closes, p=14):
    if len(highs) < p+1: return np.zeros(len(highs))
    h = np.array(highs, dtype=float)
    l = np.array(lows, dtype=float)
    c = np.array(closes, dtype=float)
    tr = np.maximum(h[1:]-l[1:], np.maximum(np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])))
    atr = np.concatenate([[np.mean(tr[:p])]*p, np.convolve(tr, np.ones(p)/p, 'valid')])
    return atr[:len(h)]

# ── 策略函数 (entries, exits, sides) ──
def strat_grid_spot(closes, highs, lows):
    """现货网格 - 简单对称网格"""
    entries, exits, sides = [], [], []
    if len(closes) < 50: return entries, exits, sides
    n_levels = 10
    span = (np.max(closes[:200]) - np.min(closes[:200])) * 0.5
    if span == 0: return entries, exits, sides
    grid_size = span / n_levels
    center = np.mean(closes[:200])
    levels = [center + grid_size * (i - n_levels//2) for i in range(n_levels)]
    for i in range(200, len(closes)):
        price = closes[i]
        for lvl in levels:
            if price <= lvl and len(entries) == len(exits):
                entries.append(lvl); sides.append(1)
                break
            elif price >= lvl * 1.02 and len(entries) > len(exits):
                exits.append(price)
                break
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_trend_futures(closes, highs, lows):
    """趋势跟踪 - 双EMA + ATR止损"""
    entries, exits, sides = [], [], []
    if len(closes) < 50: return entries, exits, sides
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    atr = atr_val(highs, lows, closes, 14)
    for i in range(30, len(closes)):
        if np.isnan(e9[i]) or np.isnan(e21[i]): continue
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if e9[i] > e21[i] and e9[i-1] <= e21[i-1]:
                entries.append(closes[i]); sides.append(1)
            elif e9[i] < e21[i] and e9[i-1] >= e21[i-1]:
                entries.append(closes[i]); sides.append(-1)
        else:
            ep = entries[-1]; sd = sides[-1]
            if sd == 1 and (closes[i] < ep - 2*atr[i] or closes[i] > ep + 4*atr[i]):
                exits.append(closes[i])
            elif sd == -1 and (closes[i] > ep + 2*atr[i] or closes[i] < ep - 4*atr[i]):
                exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_meanrev_futures(closes, highs, lows):
    """均值回归 - RSI极端反转"""
    entries, exits, sides = [], [], []
    if len(closes) < 20: return entries, exits, sides
    r = rsi(closes, 14)
    for i in range(20, len(closes)):
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if r[i] < 25:
                entries.append(closes[i]); sides.append(1)
            elif r[i] > 75:
                entries.append(closes[i]); sides.append(-1)
        else:
            sd = sides[-1]
            if sd == 1 and (r[i] > 50 or closes[i] < entries[-1]*0.93):
                exits.append(closes[i])
            elif sd == -1 and (r[i] < 50 or closes[i] > entries[-1]*1.07):
                exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_momentum_breakout(closes, highs, lows):
    """动量突破 - 20根高低点突破"""
    entries, exits, sides = [], [], []
    if len(closes) < 25: return entries, exits, sides
    h_arr = np.array(highs, dtype=float)
    l_arr = np.array(lows, dtype=float)
    atr = atr_val(highs, lows, closes, 14)
    for i in range(20, len(closes)):
        in_pos = len(entries) > len(exits)
        if not in_pos:
            hh = np.max(h_arr[i-20:i])
            ll = np.min(l_arr[i-20:i])
            if closes[i] >= hh:
                entries.append(closes[i]); sides.append(1)
            elif closes[i] <= ll:
                entries.append(closes[i]); sides.append(-1)
        else:
            ep = entries[-1]; sd = sides[-1]
            if sd == 1 and (closes[i] < ep - 2*atr[i] or closes[i] > ep + 4*atr[i]):
                exits.append(closes[i])
            elif sd == -1 and (closes[i] > ep + 2*atr[i] or closes[i] < ep - 4*atr[i]):
                exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_turtle(closes, highs, lows):
    """海龟趋势 - 20日突破 + ATR止损"""
    entries, exits, sides = [], [], []
    if len(closes) < 25: return entries, exits, sides
    h_arr = np.array(highs, dtype=float); l_arr = np.array(lows, dtype=float)
    atr = atr_val(highs, lows, closes, 14)
    for i in range(20, len(closes)):
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if closes[i] > np.max(h_arr[i-20:i]):
                entries.append(closes[i]); sides.append(1)
            elif closes[i] < np.min(l_arr[i-20:i]):
                entries.append(closes[i]); sides.append(-1)
        else:
            ep = entries[-1]; sd = sides[-1]
            sl = ep - 2*atr[i] if sd==1 else ep + 2*atr[i]
            tp = ep + 6*atr[i] if sd==1 else ep - 6*atr[i]
            if (sd==1 and (closes[i] < sl or closes[i] > tp)) or \
               (sd==-1 and (closes[i] > sl or closes[i] < tp)):
                exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_macd_trend(closes):
    """MACD趋势 - 金叉死叉"""
    entries, exits, sides = [], [], []
    if len(closes) < 50: return entries, exits, sides
    e12 = ema(closes, 12); e26 = ema(closes, 26)
    for i in range(30, len(closes)):
        if np.isnan(e12[i]) or np.isnan(e26[i]): continue
        macd = e12[i] - e26[i]; macd_p = e12[i-1] - e26[i-1]
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if macd > 0 and macd_p <= 0:
                entries.append(closes[i]); sides.append(1)
            elif macd < 0 and macd_p >= 0:
                entries.append(closes[i]); sides.append(-1)
        else:
            sd = sides[-1]
            if sd == 1 and macd < 0: exits.append(closes[i])
            elif sd == -1 and macd > 0: exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_macd_rsi(closes):
    """MACD+RSI - 双过滤"""
    entries, exits, sides = [], [], []
    if len(closes) < 50: return entries, exits, sides
    e12 = ema(closes, 12); e26 = ema(closes, 26)
    r = rsi(closes, 14)
    for i in range(30, len(closes)):
        if np.isnan(e12[i]) or np.isnan(e26[i]): continue
        macd = e12[i] - e26[i]; macd_p = e12[i-1] - e26[i-1]
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if macd > 0 and macd_p <= 0 and r[i] < 70:
                entries.append(closes[i]); sides.append(1)
            elif macd < 0 and macd_p >= 0 and r[i] > 30:
                entries.append(closes[i]); sides.append(-1)
        else:
            sd = sides[-1]
            if sd == 1 and (macd < 0 or r[i] > 75): exits.append(closes[i])
            elif sd == -1 and (macd > 0 or r[i] < 25): exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_rsi_meanrev(closes):
    """RSI均值回归"""
    entries, exits, sides = [], [], []
    if len(closes) < 20: return entries, exits, sides
    r = rsi(closes, 14)
    for i in range(15, len(closes)):
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if r[i] < 30:
                entries.append(closes[i]); sides.append(1)
            elif r[i] > 70:
                entries.append(closes[i]); sides.append(-1)
        else:
            sd = sides[-1]
            if sd == 1 and (r[i] > 50 or closes[i] < entries[-1]*0.95): exits.append(closes[i])
            elif sd == -1 and (r[i] < 50 or closes[i] > entries[-1]*1.05): exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_meanrevert(closes, highs, lows):
    """波动率回归 - 价格偏离均线回归"""
    entries, exits, sides = [], [], []
    if len(closes) < 30: return entries, exits, sides
    e20 = ema(closes, 20)
    atr = atr_val(highs, lows, closes, 14)
    for i in range(25, len(closes)):
        if np.isnan(e20[i]): continue
        dev = (closes[i] - e20[i]) / (atr[i]+1e-10)
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if dev < -2: entries.append(closes[i]); sides.append(1)
            elif dev > 2: entries.append(closes[i]); sides.append(-1)
        else:
            sd = sides[-1]
            if sd == 1 and (dev > 0 or closes[i] < entries[-1]*0.93): exits.append(closes[i])
            elif sd == -1 and (dev < 0 or closes[i] > entries[-1]*1.07): exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

def strat_combo31(closes, highs, lows, volumes):
    """31%Combo - 多因子综合"""
    entries, exits, sides = [], [], []
    if len(closes) < 50: return entries, exits, sides
    e10 = ema(closes, 10); e30 = ema(closes, 30)
    r = rsi(closes, 14)
    atr = atr_val(highs, lows, closes, 14)
    for i in range(35, len(closes)):
        if np.isnan(e10[i]) or np.isnan(e30[i]): continue
        trend = 1 if e10[i] > e30[i] else -1
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if trend == 1 and r[i] < 35:
                entries.append(closes[i]); sides.append(1)
            elif trend == -1 and r[i] > 65:
                entries.append(closes[i]); sides.append(-1)
        else:
            sd = sides[-1]
            if sd == 1 and (r[i] > 70 or closes[i] < entries[-1] - 2*atr[i]): exits.append(closes[i])
            elif sd == -1 and (r[i] < 30 or closes[i] > entries[-1] + 2*atr[i]): exits.append(closes[i])
    return entries[:len(exits)], exits, sides[:len(exits)]

# ── 回测引擎 ──
def run_backtest(name, klines, entries, exits, sides):
    prices = np.array([k['c'] for k in klines])
    capital = CAPITAL
    pnl_list = []
    wins = 0; trades = 0
    equity = CAPITAL
    peak = CAPITAL
    dd_max = 0

    n = min(len(entries), len(exits), len(sides))
    for i in range(n):
        ep = entries[i]; xp = exits[i]; sd = sides[i]
        qty = (capital * 0.2) / max(ep, 1e-10)
        fee_entry = qty * ep * FEE_TAKER
        fee_exit = qty * xp * FEE_TAKER
        gross = qty * (xp - ep) * sd
        pnl = gross - fee_entry - fee_exit
        capital += pnl
        pnl_list.append(pnl)
        trades += 1
        if pnl > 0: wins += 1

    eq_curve = [CAPITAL]
    for p in pnl_list:
        eq_curve.append(eq_curve[-1] + p)
        peak = max(peak, eq_curve[-1])
        dd = (peak - eq_curve[-1]) / max(peak, 1e-10) * 100
        dd_max = max(dd_max, dd)

    if trades == 0:
        return {'策略': name, '总PnL': 0, '收益率': '0.0%', '夏普': 0, '胜率': '0%', '回撤': 0, '交易': 0}

    total_pnl = capital - CAPITAL
    win_rate = wins / trades * 100
    sharpe = (np.mean(pnl_list) / (np.std(pnl_list)+1e-10) * np.sqrt(24*30/max(trades,1))) if trades > 1 else 0
    return {
        '策略': name, '总PnL': round(total_pnl,2), '收益率': f'{total_pnl/CAPITAL*100:.1f}%',
        '夏普': round(sharpe,2), '胜率': f'{win_rate:.0f}%',
        '回撤': round(dd_max,1), '交易': trades
    }

# ── 加载K线 ──
COINS = ['BTC', 'ETH', 'SOL', 'DOGE']
RAW = {}
for c in COINS:
    f = f'{DATA_DIR}/{c.lower()}_1h_30d.json'
    if not os.path.exists(f):
        print(f'❌ 缺数据: {f}')
        sys.exit(1)
    with open(f) as fh:
        data = json.load(fh)
    RAW[c] = [{'t': k['time'], 'o': k['open'], 'h': k['high'], 'l': k['low'], 'c': k['close'], 'v': k['volume']} for k in data]
    print(f'  {c:5s}: {len(RAW[c])}根1h K线  起点${RAW[c][0]["c"]:.4f}  终点${RAW[c][-1]["c"]:.4f}  涨跌{(RAW[c][-1]["c"]/RAW[c][0]["c"]-1)*100:+.1f}%')

# ── 跑全部策略 ──
STRATEGIES = [
    ('现货网格', lambda c,h,l,v: strat_grid_spot(c,h,l)),
    ('趋势跟踪', lambda c,h,l,v: strat_trend_futures(c,h,l)),
    ('均值回归', lambda c,h,l,v: strat_meanrev_futures(c,h,l)),
    ('动量突破', lambda c,h,l,v: strat_momentum_breakout(c,h,l)),
    ('海龟趋势', lambda c,h,l,v: strat_turtle(c,h,l)),
    ('MACD趋势', lambda c,h,l,v: strat_macd_trend(c)),
    ('MACD+RSI', lambda c,h,l,v: strat_macd_rsi(c)),
    ('RSI均值回归', lambda c,h,l,v: strat_rsi_meanrev(c)),
    ('波动率回归', lambda c,h,l,v: strat_meanrevert(c,h,l)),
    ('31%Combo', lambda c,h,l,v: strat_combo31(c,h,l)),
]

results = []
for cname, klines in RAW.items():
    closes = np.array([k['c'] for k in klines])
    highs = np.array([k['h'] for k in klines])
    lows = np.array([k['l'] for k in klines])
    volumes = np.array([k['v'] for k in klines])
    for sname, sfunc in STRATEGIES:
        try:
            entries, exits, sides = sfunc(closes, highs, lows, volumes)
            r = run_backtest(f'{sname}@{cname}', klines, entries, exits, sides)
            results.append(r)
        except Exception as e:
            results.append({'策略': f'{sname}@{cname}', '总PnL': 0, '收益率': 'ERR', '夏普': 0, '胜率': '0%', '回撤': 0, '交易': 0, 'err': str(e)})

# 配对套利 BTC vs ETH
try:
    btc_c = np.array([k['c'] for k in RAW['BTC']])
    eth_c = np.array([k['c'] for k in RAW['ETH']])
    ratio = btc_c / eth_c
    e20 = ema(ratio, 20)
    entries, exits, sides = [], [], []
    for i in range(25, len(ratio)):
        if np.isnan(e20[i]): continue
        dev = (ratio[i] - e20[i]) / (e20[i]+1e-10)
        in_pos = len(entries) > len(exits)
        if not in_pos:
            if dev < -0.02: entries.append(eth_c[i]); sides.append(-1)  # BTC/ETH ratio低 → 做空BTC? 简化:做空ETH
            elif dev > 0.02: entries.append(eth_c[i]); sides.append(1)
        else:
            sd = sides[-1]
            if sd == 1 and dev > 0: exits.append(eth_c[i])
            elif sd == -1 and dev < 0: exits.append(eth_c[i])
    r = run_backtest('PairsArb@BTC/ETH', RAW['ETH'], entries[:len(exits)], exits, sides[:len(exits)])
    results.append(r)
except Exception as e:
    pass

# ── 输出 ──
results.sort(key=lambda x: x['总PnL'] if isinstance(x['总PnL'], (int, float)) else -9999, reverse=True)

print('\n' + '='*100)
print(f' 暗黑星火 · 30天回测 (2026-05-27 → 2026-06-26) · 11策略 × 4币 = {len(results)}组')
print(f' 初始资金: ${CAPITAL:.0f} | 手续费taker 0.07% | 仓位20%/笔')
print('='*100)
print(f'{"排名":>3} {"策略":<22} {"总PnL":>9} {"收益率":>8} {"夏普":>6} {"胜率":>5} {"回撤":>6} {"交易":>5}')
print('-'*100)
for i, r in enumerate(results, 1):
    pnl = f"${r['总PnL']:+.2f}" if isinstance(r['总PnL'], (int, float)) else str(r['总PnL'])
    print(f'{i:>3} {r["策略"]:<22} {pnl:>9} {r["收益率"]:>8} {r["夏普"]:>6} {r["胜率"]:>5} {r["回撤"]:>6} {r["交易"]:>5}')

# 按策略平均
print('\n' + '='*100)
print(' 策略平均排名 (跨4币)')
print('='*100)
by_strat = {}
for r in results:
    name = r['策略'].split('@')[0]
    pnl = r['总PnL'] if isinstance(r['总PnL'], (int, float)) else 0
    by_strat.setdefault(name, []).append(pnl)

avg_sorted = sorted(by_strat.items(), key=lambda x: np.mean(x[1]), reverse=True)
for name, pnls in avg_sorted:
    avg = np.mean(pnls)
    wins = sum(1 for p in pnls if p > 0)
    print(f'  {name:<14} 均PnL=${avg:+8.2f}  跨{len(pnls)}币 {wins}/{len(pnls)}盈  ({", ".join(f"${p:+.1f}" for p in pnls)})')

# 最佳单组
print('\n' + '='*100)
print(' 🏆 TOP 5')
print('='*100)
for r in results[:5]:
    pnl = f"${r['总PnL']:+.2f}"
    print(f'  {r["策略"]:<22} {pnl} ({r["收益率"]}) 夏普{r["夏普"]} 胜率{r["胜率"]} 回撤{r["回撤"]}%')

# 保存JSON
out_json = f'{RESULT_DIR}/backtest_30d_20260626.json'
with open(out_json, 'w') as f:
    json.dump({
        'period': '2026-05-27 → 2026-06-26',
        'coins': COINS,
        'capital': CAPITAL,
        'fee_taker': FEE_TAKER,
        'total_combos': len(results),
        'results': results,
        'by_strategy_avg': {k: float(np.mean(v)) for k, v in by_strat.items()},
    }, f, indent=2, ensure_ascii=False)
print(f'\n完整结果: {out_json}')