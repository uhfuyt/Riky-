#!/usr/bin/env python3
"""
成本敏感性 + 资金规模敏感性
============================
1. 不同佣金率下, 动量策略(0.998/MA20/MA20) 的 OOS 表现
2. 不同本金下, 同样的策略表现
   → 回答"2000元到底能不能做"和"佣金必须谈到多少"
"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys, json
from datetime import datetime

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from run_oos_test import load_etf_set, simple_portfolio_backtest
from run_param_robustness import make_momentum



def main():
    data = load_etf_set()
    oos_df = {s: df.iloc[500:].reset_index(drop=True) for s, df in data.items()}
    fn = make_momentum(0.998, 20, 20)

    print("="*88)
    print("① 佣金敏感性 (OOS段, 本金2000元, ETF, 动量0.998/MA20/MA20)")
    print("="*88)
    print(f"{'佣金率':>12}{'最低佣金':>10}{'总费用':>10}{'费用/本金':>11}{'OOS收益':>11}{'判定':>14}")
    print("-"*88)
    for rate, min_fee, desc in [
        (0.0001, 0.0, '万1 无门槛'),
        (0.0001, 5.0, '万1 有5元门槛'),
        (0.00025, 0.0, '万2.5 无门槛'),
        (0.00025, 5.0, '万2.5 有5元门槛'),
        (0.0005, 0.0, '万5 无门槛'),
        (0.0001, 1.0, '万1 最低1元'),
    ]:
        r = simple_portfolio_backtest(oos_df, fn, capital=2000.0,
                                      commission_rate=rate, min_commission=min_fee,
                                      stamp_tax=0.0, slippage=0.001)
        fee_pct = r['total_fees'] / 2000
        ok = r['total_return'] > 0
        print(f"{rate*10000:>10.0f}bp{min_fee:>9.0f}元{r['total_fees']:>9.0f}元"
              f"{fee_pct*100:>10.1f}%{r['total_return']*100:>10.2f}%{'✅正' if ok else '❌负':>14}")

    print("\n" + "="*88)
    print("② 资金规模敏感性 (OOS段, ETF, 佣金万1无门槛)")
    print("="*88)
    print(f"{'本金':>10}{'OOS收益':>11}{'年化':>10}{'回撤':>9}{'交易':>7}{'费用':>9}{'费用占比':>10}")
    print("-"*88)
    for cap in [500, 1000, 2000, 5000, 10000, 50000]:
        r = simple_portfolio_backtest(oos_df, fn, capital=float(cap),
                                      commission_rate=0.0001, min_commission=0.0,
                                      stamp_tax=0.0, slippage=0.001)
        print(f"{cap:>10}{r['total_return']*100:>10.2f}%{r['annual_return']*100:>9.2f}%"
              f"{r['max_drawdown']*100:>8.1f}%{r['n_trades']:>7}"
              f"{r['total_fees']:>8.2f}元{r['total_fees']/cap*100:>9.2f}%")

    print("\n" + "="*88)
    print("③ 个股 vs ETF (OOS段, 2000元, 佣金万1)")
    print("="*88)
    from a_share_backtest_v2 import load_kline
    from run_backtest_v2 import UNIVERSE
    stock_is, stock_oos = {}, {}
    for sym, name in UNIVERSE:
        df = load_kline(sym, 750)
        if df is None or len(df) < 600:
            continue
        stock_is[sym] = df.iloc[:500].reset_index(drop=True)
        stock_oos[sym] = df.iloc[500:].reset_index(drop=True)
    print(f"个股池: {len(stock_oos)}只")
    r_stock = simple_portfolio_backtest(stock_oos, fn, capital=2000.0, is_etf=False,
                                         max_positions=2, max_pct=0.95,
                                         commission_rate=0.0001, min_commission=0.0,
                                         stamp_tax=0.001, slippage=0.001)
    r_etf = simple_portfolio_backtest(oos_df, fn, capital=2000.0,
                                      commission_rate=0.0001, min_commission=0.0,
                                      stamp_tax=0.0, slippage=0.001)
    print(f"{'':<12}{'OOS收益':>11}{'年化':>10}{'回撤':>9}{'交易':>7}{'费用':>10}{'费用/本金':>11}")
    for label, r in [('个股', r_stock), ('ETF', r_etf)]:
        print(f"{label:<12}{r['total_return']*100:>10.2f}%{r['annual_return']*100:>9.2f}%"
              f"{r['max_drawdown']*100:>8.1f}%{r['n_trades']:>7}"
              f"{r['total_fees']:>9.2f}元{r['total_fees']/2000*100:>10.2f}%")


if __name__ == '__main__':
    main()
