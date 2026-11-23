#!/usr/bin/env python3
"""
样本外检验 (Out-of-Sample) + 参数稳健性
=========================================
把 750 天切成两段:
  IS  (样本内): 前 500 天 → 选参数
  OOS (样本外): 后 250 天 → 验证参数是否有效
OOS 亏损 = 过拟合, 不可实盘
"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys, json
import numpy as np
from datetime import datetime

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from a_share_backtest_v2 import (
    load_kline, STRATEGIES_V2, calc_max_drawdown, calc_sharpe,
    COMMISSION_RATE, MIN_COMMISSION, STAMP_TAX, SLIPPAGE, ETF_STAMP_TAX,
)
from run_backtest_v2 import ETF_POOL, UNIVERSE


DATA_DIR = os.path.join(ENGINE_DIR, 'data')


def load_etf_set():
    data = {}
    for code, name in ETF_POOL:
        df = load_kline(code, 750)
        if df is None:
            continue
        data[code] = df
    return data


def split_data(df, split_idx):
    return df.iloc[:split_idx].reset_index(drop=True), df.iloc[split_idx:].reset_index(drop=True)


def simple_portfolio_backtest(data, strategy_fn, capital=2000.0, is_etf=True,
                              stop_loss=0.08, take_profit=0.25, max_hold=60,
                              max_positions=3, max_pct=0.35,
                              commission_rate=0.0001, min_commission=0.0,
                              stamp_tax=0.0, slippage=0.001):
    """简化版组合回测(直接用df, 便于样本外切片)"""
    from a_share_backtest_v2 import Portfolio, is_limit_up_or_down, PRICE_LIMIT

    if not data:
        return None
    ref = max(data.keys(), key=lambda s: len(data[s]))
    dates = data[ref]['日期'].dt.strftime('%Y-%m-%d').values

    arr = {}
    for sym, df in data.items():
        arr[sym] = {
            'dates': df['日期'].dt.strftime('%Y-%m-%d').values,
            'open': df['开盘'].values, 'close': df['收盘'].values,
            'high': df['最高'].values, 'low': df['最低'].values,
            'idx_of': dict(zip(df['日期'].dt.strftime('%Y-%m-%d').values, range(len(df)))),
        }

    pf = Portfolio(capital, is_etf, commission_rate, min_commission, stamp_tax, slippage, max_pct)
    price_map = {}

    for i, date in enumerate(dates):
        if i < 25:
            continue
        active = [(s, arr[s]['idx_of'][date]) for s in arr if date in arr[s]['idx_of']]
        if not active:
            continue
        today = {s: arr[s]['close'][j] for s, j in active}
        prev = {s: (arr[s]['close'][j-1] if j > 0 else arr[s]['close'][j]) for s, j in active}

        for sym, pos in pf.positions.items():
            if sym in today:
                pos.high_since_buy = max(pos.high_since_buy, arr[sym]['high'][arr[sym]['idx_of'][date]])

        for sym, j in active:
            if sym not in pf.positions:
                continue
            pos = pf.positions[sym]
            price = today[sym]
            import pandas as pd
            view = pd.DataFrame({'收盘': arr[sym]['close'][:j+1], '最高': arr[sym]['high'][:j+1],
                                 '最低': arr[sym]['low'][:j+1], '成交量': arr[sym]['close'][:j+1]})
            sig = strategy_fn(view, j)
            reason = None
            if sig == 'SELL':
                reason = '信号'
            elif price <= pos.cost * (1 - stop_loss):
                reason = '止损'
            elif price >= pos.cost * (1 + take_profit):
                reason = '止盈'
            elif pos.high_since_buy > 0 and price < pos.high_since_buy * 0.93:
                reason = '移动止盈'
            elif i - pos.buy_idx >= max_hold:
                reason = '时间止损'
            if reason and not is_limit_up_or_down(arr[sym]['open'][j], prev[sym], PRICE_LIMIT):
                pf.close_pos(sym, price, date, reason)

        for sym, j in active:
            if sym in pf.positions or len(pf.positions) >= max_positions:
                continue
            import pandas as pd
            view = pd.DataFrame({'收盘': arr[sym]['close'][:j+1], '最高': arr[sym]['high'][:j+1],
                                 '最低': arr[sym]['low'][:j+1], '成交量': arr[sym]['close'][:j+1]})
            if strategy_fn(view, j) != 'BUY':
                continue
            if is_limit_up_or_down(arr[sym]['open'][j], prev[sym], PRICE_LIMIT):
                continue
            price = today[sym]
            sh = pf.buy_shares(price, pf.cash)
            if sh >= pf.lot:
                pf.open_pos(sym, sh, price, date, i, is_etf)

        price_map.update(today)
        for sym in list(pf.positions):
            price_map.setdefault(sym, pf.positions[sym].cost)
        pf.daily_value.append({'date': date, 'total': pf.total_value(price_map),
                               'cash': pf.cash, 'n_pos': len(pf.positions)})

    for sym in list(pf.positions):
        j = arr[sym]['idx_of'].get(dates[-1])
        if j is not None:
            pf.close_pos(sym, arr[sym]['close'][j], dates[-1], '期末清仓')

    values = [d['total'] for d in pf.daily_value]
    rets = [(values[i]/values[i-1]-1) for i in range(1, len(values))]
    sells = [t for t in pf.trades if t.side == 'SELL']
    wins = [t for t in sells if t.pnl > 0]
    gross_w = sum(t.pnl for t in wins)
    gross_l = abs(sum(t.pnl for t in sells if t.pnl <= 0))
    return {
        'total_return': values[-1]/capital - 1,
        'annual_return': (values[-1]/capital)**(252/max(len(values),1)) - 1,
        'max_drawdown': calc_max_drawdown(values),
        'sharpe': calc_sharpe(rets),
        'n_trades': len(sells),
        'win_rate': len(wins)/max(len(sells),1),
        'total_fees': sum(t.fee for t in pf.trades),
        'days': len(values),
        'final': values[-1],
    }


def main():
    print("="*86)
    print("样本外检验 (IS: 前500天 / OOS: 后250天)  本金2000元 ETF")
    print("="*86)

    data = load_etf_set()
    print(f"ETF池: {len(data)}只")

    is_df, oos_df = {}, {}
    for s, df in data.items():
        a, b = split_data(df, 500)
        if len(a) > 100 and len(b) > 50:
            is_df[s] = a
            oos_df[s] = b
    print(f"IS: {len(is_df)}只 | OOS: {len(oos_df)}只")

    # 基准
    bench = load_kline('sh000300', 750)
    if bench is not None:
        for label, bdf in [('IS', bench.iloc[:500]), ('OOS', bench.iloc[500:])]:
            c = bdf['收盘'].values
            v = [c[i]/c[0] for i in range(len(c))]
            print(f"基准{label} 沪深300: {v[-1]*100-100:+.2f}% | 回撤 {calc_max_drawdown(v)*100:.1f}%")

    print()
    results = {}
    for key, (sname, fn) in STRATEGIES_V2.items():
        is_r = simple_portfolio_backtest(is_df, fn)
        oos_r = simple_portfolio_backtest(oos_df, fn)
        if not is_r or not oos_r:
            continue
        results[key] = {'name': sname, 'IS': is_r, 'OOS': oos_r}
        verdict = "✅ OOS正" if oos_r['total_return'] > 0 else "❌ OOS负(过拟合?)"
        print(f"{sname:<12} IS {is_r['total_return']*100:>7.2f}% → OOS {oos_r['total_return']*100:>7.2f}%  {verdict}")
        print(f"{'':<12}   IS: {is_r['n_trades']}笔 费{is_r['total_fees']:.0f}元 | "
              f"OOS: {oos_r['n_trades']}笔 费{oos_r['total_fees']:.0f}元")

    # 保存
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(ENGINE_DIR, 'logs', f'oos_test_{stamp}.json')
    with open(out, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n已保存: {out}")


if __name__ == '__main__':
    main()
