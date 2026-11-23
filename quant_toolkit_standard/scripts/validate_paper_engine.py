#!/usr/bin/env python3
"""
模拟盘引擎历史回放验证
========================
用 2026-08-20 ~ 2026-11-20 (最近60交易日) 逐日重放 etf_paper_engine 的逻辑,
验证引擎复现回测结果 (OOS +9.01%)。
若回放结果 ≈ 回测结果 → 引擎可信, 可用于未来30天模拟盘。
"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys, json, csv
from datetime import datetime, timedelta

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

import pandas as pd
import numpy as np

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

STRATEGY = make_momentum(0.998, 20, 20)


def buy_fee(g):
    return max(g * COMMISSION, MIN_COMMISSION) + g * SLIPPAGE


def sell_fee(g):
    return max(g * COMMISSION, MIN_COMMISSION) + g * SLIPPAGE


def calc_shares(price, cash):
    target = cash * MAX_PCT
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


def replay(start_date='2026-08-20', end_date='2026-11-20', capital=CAPITAL,
           sort_mode='price_desc', max_pct=MAX_PCT, max_pos=MAX_POS):
    data = {}
    for code, name in ETF_POOL:
        df = load_kline(code, 750)
        if df is None or len(df) < 100:
            continue
        data[code] = df

    ref = max(data.values(), key=len)
    all_dates = ref['日期'].dt.strftime('%Y-%m-%d').values
    dates = [d for d in all_dates if start_date <= d <= end_date]

    cash = capital
    positions = {}
    trades = []
    equity_curve = []
    day_idx = 0
    total_fees = 0.0

    for d in dates:
        today_map = {}
        for code, df in data.items():
            idx = df.index[df['日期'].dt.strftime('%Y-%m-%d') == d]
            if len(idx):
                i = int(idx[0])
                if i < 25:
                    continue
                today_map[code] = {
                    'i': i, 'close': float(df['收盘'].iloc[i]),
                    'high': float(df['最高'].iloc[i]),
                    'df': df,
                }
        if not today_map:
            continue

        # 卖出
        for code in list(positions):
            if code not in today_map:
                continue
            pos = positions[code]
            tm = today_map[code]
            price = tm['close']
            pos['high'] = max(pos['high'], tm['high'])
            hold = day_idx - pos['buy_idx']
            sig = STRATEGY(tm['df'].iloc[:tm['i']+1], tm['i'])
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
                total_fees += fee
                trades.append({'date': d, 'code': code, 'side': 'SELL', 'price': price,
                               'shares': pos['shares'], 'pnl': pnl, 'reason': reason,
                               'hold': hold, 'fee': fee})
                del positions[code]

        # 买入
        cands = []
        for code, tm in today_map.items():
            if code in positions:
                continue
            if STRATEGY(tm['df'].iloc[:tm['i']+1], tm['i']) == 'BUY':
                cands.append((code, tm))
        if sort_mode == 'pool':
            cands.sort(key=lambda x: [c for c, _ in ETF_POOL].index(x[0]))
        elif sort_mode == 'price_desc':
            cands.sort(key=lambda x: -x[1]['close'])
        elif sort_mode == 'code':
            cands.sort(key=lambda x: x[0])
        for code, tm in cands:
            if len(positions) >= max_pos:
                break
            # 涨跌停检查(与回测一致)
            prev = float(tm['df']['收盘'].iloc[tm['i']-1]) if tm['i'] > 0 else tm['close']
            if is_limit_up_or_down(float(tm['df']['开盘'].iloc[tm['i']]), prev, PRICE_LIMIT):
                continue
            price = tm['close']
            sh = calc_shares(price, cash)
            if sh < LOT:
                continue
            g = price * sh
            fee = buy_fee(g)
            if g + fee > cash:
                continue
            cash -= (g + fee)
            total_fees += fee
            positions[code] = {'shares': sh, 'cost': price, 'high': tm['high'],
                               'buy_idx': day_idx, 'buy_date': d}
            trades.append({'date': d, 'code': code, 'side': 'BUY', 'price': price,
                           'shares': sh, 'pnl': 0, 'reason': '突破', 'hold': 0, 'fee': fee})

        pos_val = sum(p['shares'] * today_map[c]['close'] for c, p in positions.items() if c in today_map)
        equity = cash + pos_val
        day_idx += 1
        equity_curve.append({'date': d, 'equity': equity, 'cash': cash,
                             'n': len(positions), 'fees': total_fees})

    # 期末清仓
    last_d = dates[-1]
    for code in list(positions):
        df = data[code]
        idx = df.index[df['日期'].dt.strftime('%Y-%m-%d') == last_d]
        if len(idx):
            i = int(idx[0])
            price = float(df['收盘'].iloc[i])
            pos = positions[code]
            g = price * pos['shares']
            fee = sell_fee(g)
            cash += g - fee
            total_fees += fee

    values = [e['equity'] for e in equity_curve]
    rets = [(values[i]/values[i-1]-1) for i in range(1, len(values))]
    peak = values[0]
    mdd = 0
    for v in values:
        peak = max(peak, v)
        mdd = min(mdd, (v-peak)/peak)
    sells = [t for t in trades if t['side'] == 'SELL']
    wins = [t for t in sells if t['pnl'] > 0]

    return {
        'period': f'{dates[0]} ~ {dates[-1]}',
        'days': len(equity_curve),
        'initial': capital,
        'final': cash,
        'total_return': cash / capital - 1,
        'max_drawdown': mdd,
        'n_trades': len(sells),
        'win_rate': len(wins) / max(len(sells), 1),
        'total_fees': total_fees,
        'sharpe': float((np.mean(rets)*252 - 0.015) / (np.std(rets)*np.sqrt(252))) if len(rets) > 5 and np.std(rets) > 0 else 0,
        'trades': trades,
        'equity_curve': equity_curve,
    }


if __name__ == '__main__':
    r = replay()
    print("=" * 78)
    print(f"模拟盘引擎历史回放验证  {r['period']}  ({r['days']}个交易日)")
    print("=" * 78)
    print(f"初始 {r['initial']}元 → 期末 {r['final']:.2f}元")
    print(f"总收益 {r['total_return']*100:+.2f}% | 年化 {((1+r['total_return'])**(252/r['days'])-1)*100:+.2f}%")
    print(f"最大回撤 {r['max_drawdown']*100:.2f}% | Sharpe {r['sharpe']:.2f}")
    print(f"交易 {r['n_trades']}笔 | 胜率 {r['win_rate']*100:.1f}% | 累计费用 {r['total_fees']:.2f}元")
    print(f"\n对比回测(同一策略, 全周期3年): +16.49% | OOS(后250天): +9.01%")
    print("\n--- 交易明细 ---")
    for t in r['trades']:
        mark = f"{t['pnl']:+8.2f}" if t['side'] == 'SELL' else "        "
        print(f"  {t['date']} {t['side']:<4} {t['code']} {t['shares']:>5}份 @{t['price']:>7.3f} "
              f"{mark} {t['reason']} (持{t['hold']}日)")

    with open(os.path.join(ENGINE_DIR, 'logs', 'paper_replay_validation.json'), 'w') as f:
        json.dump(r, f, ensure_ascii=False, indent=1, default=float)
