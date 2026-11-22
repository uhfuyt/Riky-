#!/usr/bin/env python3
"""最终成本×本金 二维敏感性 — 回答"2000元到底能不能做" """
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_oos_test import load_etf_set, simple_portfolio_backtest
from run_param_robustness import make_momentum

etf = load_etf_set()
oos = {s: df.iloc[500:].reset_index(drop=True) for s, df in etf.items()}
fn = make_momentum(0.998, 20, 20)

print("="*94)
print("ETF 动量突破(0.998/MA20/MA20) — 佣金方案 × 本金 矩阵 (OOS后250天)")
print("="*94)

COMM_SCENARIOS = [
    ("默认万3+5元门槛", 0.0003, 5.0),
    ("万1+5元门槛",    0.0001, 5.0),
    ("ETF万0.5+5元",   0.00005, 5.0),
    ("ETF万0.5免五",   0.00005, 0.0),
    ("ETF万0.1免五",   0.0001, 0.0),
]

print(f"{'佣金方案':<18}" + "".join(f"{c:>11}" for c in [500, 2000, 5000, 20000, 100000]))
print("-"*94)
for label, rate, min_fee in COMM_SCENARIOS:
    row = f"{label:<18}"
    for cap in [500, 2000, 5000, 20000, 100000]:
        r = simple_portfolio_backtest(oos, fn, capital=float(cap),
                                      commission_rate=rate, min_commission=min_fee,
                                      stamp_tax=0.0, slippage=0.001,
                                      max_positions=3, max_pct=0.35, is_etf=True)
        row += f"{r['total_return']*100:>10.2f}%"
    print(row)

print("\n注: 负数=亏损。'免五'指免掉单笔最低5元佣金门槛(部分券商可协商,灰色地带)")
