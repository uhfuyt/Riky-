#!/usr/bin/env python3
"""完整个股池(30只真实中证100) × ETF 的 OOS 成本对比"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a_share_backtest_v2 import load_kline
from run_backtest_v2 import UNIVERSE
from run_oos_test import simple_portfolio_backtest, load_etf_set
from run_param_robustness import make_momentum


def main():
    stock = {}
    for sym, name in UNIVERSE:
        df = load_kline(sym, 750)
        if df is not None and len(df) >= 600:
            stock[sym] = df
    oos_s = {s: df.iloc[500:].reset_index(drop=True) for s, df in stock.items()}
    is_s = {s: df.iloc[:500].reset_index(drop=True) for s, df in stock.items()}
    print(f"完整个股池: {len(stock)} 只")

    etf = load_etf_set()
    oos_e = {s: df.iloc[500:].reset_index(drop=True) for s, df in etf.items()}
    is_e = {s: df.iloc[:500].reset_index(drop=True) for s, df in etf.items()}
    print(f"ETF池: {len(etf)} 只")

    fn = make_momentum(0.998, 20, 20)

    print("\n" + "=" * 96)
    print("动量突破(0.998/MA20/MA20) · 2000元 · IS前500天 / OOS后250天")
    print("=" * 96)
    print(f"{'模式':<22}{'IS收益':>11}{'OOS收益':>11}{'OOS回撤':>10}{'交易':>7}{'OOS费用':>11}{'费用占比':>10}")
    print("-" * 96)

    cases = [
        ('个股 万1 无门槛',   is_s, oos_s, dict(is_etf=False, max_positions=2, max_pct=0.95,
                                   commission_rate=0.0001,  min_commission=0.0, stamp_tax=0.001, slippage=0.001)),
        ('个股 万1 最低1元',  is_s, oos_s, dict(is_etf=False, max_positions=2, max_pct=0.95,
                                   commission_rate=0.0001,  min_commission=1.0, stamp_tax=0.001, slippage=0.001)),
        ('个股 万2.5 有5元',  is_s, oos_s, dict(is_etf=False, max_positions=2, max_pct=0.95,
                                   commission_rate=0.00025, min_commission=5.0, stamp_tax=0.001, slippage=0.001)),
        ('ETF  万1 无门槛',   is_e, oos_e, dict(is_etf=True,  max_positions=3, max_pct=0.35,
                                   commission_rate=0.0001,  min_commission=0.0, stamp_tax=0.0,  slippage=0.001)),
        ('ETF  万1 最低1元',  is_e, oos_e, dict(is_etf=True,  max_positions=3, max_pct=0.35,
                                   commission_rate=0.0001,  min_commission=1.0, stamp_tax=0.0,  slippage=0.001)),
        ('ETF  万2.5 有5元',  is_e, oos_e, dict(is_etf=True,  max_positions=3, max_pct=0.35,
                                   commission_rate=0.00025, min_commission=5.0, stamp_tax=0.0,  slippage=0.001)),
    ]

    for label, d_is, d_oos, kw in cases:
        ri = simple_portfolio_backtest(d_is, fn, capital=2000.0, **kw)
        ro = simple_portfolio_backtest(d_oos, fn, capital=2000.0, **kw)
        fee_pct = ro['total_fees'] / 2000 * 100
        flag = '✅' if ro['total_return'] > 0 else '❌'
        print(f"{label:<22}{ri['total_return']*100:>10.2f}%{ro['total_return']*100:>10.2f}% "
              f"{ro['max_drawdown']*100:>9.1f}%{ro['n_trades']:>7}{ro['total_fees']:>10.2f}元{fee_pct:>9.2f}% {flag}")


if __name__ == '__main__':
    main()
