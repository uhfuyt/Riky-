#!/usr/bin/env python3
"""
最终裁决: 趋势过滤器 + 基准对比
================================
发现: 纯动量策略滚动窗口超额 ≈ 0 (只是跟着指数beta)
修正方向: 加市场趋势过滤 (只在市场处于上升趋势时才开仓)
       → 经典做法: 个股/ETF 收盘价 > N日均线 且 市场指数 > N日均线

同时对比: 纯买入持有沪深300ETF 的收益 — 看看"啥也不做"能赚多少
"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys
import numpy as np
import pandas as pd

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from a_share_backtest_v2 import load_kline, is_limit_up_or_down, PRICE_LIMIT
from run_param_robustness import make_momentum


CAPITAL = 2000.0
COMMISSION = 0.0005
MIN_COMMISSION = 0.0
SLIPPAGE = 0.001
LOT = 100
MAX_PCT = 0.35
MAX_POS = 3
STOP_LOSS = 0.08
TAKE_PROFIT = 0.25
TRAIL = 0.93
MAX_HOLD = 60

ETF_POOL = [
    ('sh510300', '沪深300ETF'), ('sh510500', '中证500ETF'), ('sh512100', '中证1000ETF'),
    ('sh588000', '科创50ETF'), ('sz159915', '创业板ETF'), ('sh510880', '红利ETF'),
    ('sz159919', '沪深300ETF深'), ('sh513100', '纳指ETF'), ('sh513500', '标普500ETF'),
    ('sh512880', '证券ETF'), ('sh515180', '红利低波ETF'), ('sh516160', '新能源ETF'),
    ('sh515790', '光伏ETF'), ('sh512170', '医疗ETF'), ('sh512690', '酒ETF'),
    ('sz159941', '纳指ETF深'),
]


def buy_fee(g):
    return max(g * COMMISSION, MIN_COMMISSION) + g * SLIPPAGE


def sell_fee(g):
    return max(g * COMMISSION, MIN_COMMISSION) + g * SLIPPAGE


def calc_shares(price, cash, max_pct=None):
    target = cash * (MAX_PCT if max_pct is None else max_pct)
    raw = target / (price * (1 + COMMISSION + SLIPPAGE))
    sh = int(raw // LOT) * LOT
    if sh < LOT:
        sh = LOT if cash >= price * LOT + buy_fee(price * LOT) else 0
    while sh >= LOT:
        g = price * sh
        if g + buy_fee(g) <= cash:
            return sh
        sh -= LOT
    return 0


def load_all():
    data = {}
    for code, name in ETF_POOL:
        df = load_kline(code, 750)
        if df is not None and len(df) >= 100:
            data[code] = df
    bench = load_kline('sh000300', 750)
    return data, bench


def market_filter_on(bench_df, date_str, ma_n):
    """市场趋势过滤: 沪深300收盘 > MA(ma_n) 则允许开仓"""
    idx = bench_df.index[bench_df['日期'].dt.strftime('%Y-%m-%d') == date_str]
    if not len(idx):
        return True
    i = int(idx[0])
    if i < ma_n:
        return True
    c = bench_df['收盘'].values
    ma = c[i-ma_n+1:i+1].mean()
    return c[i] > ma


def run_window(data, bench, start, end, strategy, trend_ma=0, max_pos=MAX_POS,
                max_pct=None):
    """单窗口回放. trend_ma>0 时启用市场趋势过滤"""
    ref = max(data.values(), key=len)
    all_dates = ref['日期'].dt.strftime('%Y-%m-%d').values
    dates = [d for d in all_dates if start <= d <= end]

    cash = CAPITAL
    positions = {}
    trades = []
    eq = []
    day_idx = 0

    for d in dates:
        tm_all = {}
        for code, df in data.items():
            idx = df.index[df['日期'].dt.strftime('%Y-%m-%d') == d]
            if len(idx):
                i = int(idx[0])
                if i >= 25:
                    tm_all[code] = {'i': i, 'close': float(df['收盘'].iloc[i]),
                                     'high': float(df['最高'].iloc[i]), 'df': df}
        if not tm_all:
            continue

        for code in list(positions):
            if code not in tm_all:
                continue
            pos = positions[code]
            tm = tm_all[code]
            price = tm['close']
            pos['high'] = max(pos['high'], tm['high'])
            hold = day_idx - pos['buy_idx']
            sig = strategy(tm['df'].iloc[:tm['i']+1], tm['i'])
            reason = None
            if sig == 'SELL':
                reason = '信号'
            elif price <= pos['cost'] * (1 - STOP_LOSS):
                reason = '止损'
            elif price >= pos['cost'] * (1 + TAKE_PROFIT):
                reason = '止盈'
            elif pos['high'] > 0 and price < pos['high'] * TRAIL:
                reason = '移动止盈'
            elif hold >= MAX_HOLD:
                reason = '时间止损'
            if reason:
                g = price * pos['shares']
                fee = sell_fee(g)
                pnl = g - fee - pos['cost'] * pos['shares']
                cash += g - fee
                trades.append({'date': d, 'side': 'SELL', 'pnl': pnl, 'hold': hold, 'reason': reason})
                del positions[code]

        # 买入(带趋势过滤)
        allow = True
        if trend_ma > 0:
            allow = market_filter_on(bench, d, trend_ma)

        if allow:
            cands = []
            for code, tm in tm_all.items():
                if code in positions:
                    continue
                if strategy(tm['df'].iloc[:tm['i']+1], tm['i']) == 'BUY':
                    cands.append((code, tm))
            cands.sort(key=lambda x: x[0])
            for code, tm in cands:
                if len(positions) >= max_pos:
                    break
                prev = float(tm['df']['收盘'].iloc[tm['i']-1]) if tm['i'] > 0 else tm['close']
                if is_limit_up_or_down(float(tm['df']['开盘'].iloc[tm['i']]), prev, PRICE_LIMIT):
                    continue
                price = tm['close']
                sh = calc_shares(price, cash, max_pct)
                if sh < LOT:
                    continue
                g = price * sh
                fee = buy_fee(g)
                if g + fee > cash:
                    continue
                cash -= (g + fee)
                positions[code] = {'shares': sh, 'cost': price, 'high': tm['high'], 'buy_idx': day_idx}
                trades.append({'date': d, 'side': 'BUY', 'pnl': 0, 'hold': 0, 'reason': '突破'})

        pv = sum(p['shares'] * tm_all[c]['close'] for c, p in positions.items() if c in tm_all)
        eq.append(cash + pv)
        day_idx += 1

    # 期末清仓
    last = dates[-1]
    for code in list(positions):
        df = data[code]
        idx = df.index[df['日期'].dt.strftime('%Y-%m-%d') == last]
        if len(idx):
            i = int(idx[0])
            price = float(df['收盘'].iloc[i])
            g = price * positions[code]['shares']
            cash += g - sell_fee(g)

    values = eq
    peak = values[0]
    mdd = 0
    for v in values:
        peak = max(peak, v)
        mdd = min(mdd, (v - peak) / peak)
    rets = [(values[i]/values[i-1]-1) for i in range(1, len(values))]
    sells = [t for t in trades if t['side'] == 'SELL']
    wins = [t for t in sells if t['pnl'] > 0]
    return {
        'ret': cash / CAPITAL - 1,
        'dd': mdd,
        'n': len(sells),
        'wr': len(wins) / max(len(sells), 1),
        'sharpe': float((np.mean(rets)*252 - 0.015) / (np.std(rets)*np.sqrt(252))) if len(rets) > 5 and np.std(rets) > 0 else 0.0,
    }


def buy_and_hold(bench, start, end, etf_df=None):
    """买入持有沪深300ETF (含成本, 剩余现金计入净值)
    用 ETF 真实价格(可买), 不用指数(指数不可买)
    """
    src = etf_df if etf_df is not None else bench
    bdates = src['日期'].dt.strftime('%Y-%m-%d').values
    idx = [i for i, d in enumerate(bdates) if start <= d <= end]
    if not idx:
        return 0
    c = src['收盘'].values
    i0, i1 = idx[0], idx[-1]
    p0, p_end = float(c[i0]), float(c[i1])
    lots = int(CAPITAL / (p0 * (1 + COMMISSION + SLIPPAGE)) // LOT) * LOT
    if lots < LOT:
        return 0
    gross = p0 * lots
    fee = buy_fee(gross)
    cash_left = CAPITAL - gross - fee
    proceeds = p_end * lots - sell_fee(p_end * lots)
    return (proceeds + cash_left) / CAPITAL - 1


def main():
    data, bench = load_all()
    bdates = bench['日期'].dt.strftime('%Y-%m-%d').values
    strat = make_momentum(0.998, 20, 20)

    configs = [
        ('无趋势过滤', 0),
        ('趋势过滤MA60', 60),
        ('趋势过滤MA120', 120),
        ('趋势过滤MA200', 200),
    ]

    win = 60
    windows = [(bdates[i], bdates[i+win-1]) for i in range(0, len(bdates)-win, win)]

    print("=" * 100)
    print(f"滚动窗口 × 趋势过滤  ({len(windows)}个不重叠窗口, 每窗口{win}交易日, 2000元)")
    print("=" * 100)

    summary = {}
    # 基准 ETF (可买) —— 必须在窗口循环之前取, 循环里要用
    etf300 = data.get('sh510300')
    if etf300 is None:
        raise SystemExit("缺少 sh510300 ETF 数据，基准无法计算")
    for label, tma in configs:
        rets, excs, dds, ns, wrs = [], [], [], [], []
        for s, e in windows:
            r = run_window(data, bench, s, e, strat, trend_ma=tma)
            # ⚠️ 基准必须用【可买的 ETF】(sh510300)，不能用指数(sh000300)。
            # 2000元买不起 1 份指数 → buy_and_hold(bench) 恒返回 0
            # → excs = rets - 0 = rets → "超额"永远等于策略收益(假结果)。
            b = buy_and_hold(bench, s, e, etf_df=etf300)
            rets.append(r['ret'])
            excs.append(r['ret'] - b)
            dds.append(r['dd'])
            ns.append(r['n'])
            wrs.append(r['wr'])
        pos = sum(1 for x in rets if x > 0)
        posexc = sum(1 for x in excs if x > 0)
        summary[label] = (rets, excs)
        print(f"\n【{label}】")
        print(f"  为正 {pos}/{len(windows)} ({pos/len(windows)*100:.0f}%) | "
              f"超额为正 {posexc}/{len(windows)} ({posexc/len(windows)*100:.0f}%)")
        print(f"  平均 {np.mean(rets)*100:+.2f}% | 中位 {np.median(rets)*100:+.2f}% | "
              f"平均超额 {np.mean(excs)*100:+.2f}% | 中位超额 {np.median(excs)*100:+.2f}%")
        print(f"  平均回撤 {np.mean(dds)*100:.1f}% | 平均交易 {np.mean(ns):.1f}笔 | 平均胜率 {np.mean(wrs)*100:.0f}%")

    # 基准: 纯买入持有沪深300ETF (用ETF真实价格)
    bhs = [buy_and_hold(bench, s, e, etf_df=etf300) for s, e in windows]
    print(f"\n【基准】买入持有沪深300ETF (2000元, 万0.5免五)")
    print(f"  为正 {sum(1 for x in bhs if x>0)}/{len(windows)} | "
          f"平均 {np.mean(bhs)*100:+.2f}% | 中位 {np.median(bhs)*100:+.2f}%")

    print("\n" + "=" * 100)
    print("各窗口明细 (最优配置 vs 基准)")
    print("=" * 100)
    best_label = max(summary.items(), key=lambda kv: np.median(kv[1][1]))
    print(f"最优(按中位超额): {best_label[0]}")
    rets, excs = best_label[1]
    print(f"{'窗口':<26}{'策略':>10}{'基准':>10}{'超额':>10}")
    for i, (s, e) in enumerate(windows):
        print(f"{s}~{e:<12}{rets[i]*100:>9.2f}%{bhs[i]*100:>9.2f}%{excs[i]*100:>9.2f}%")


if __name__ == '__main__':
    main()
