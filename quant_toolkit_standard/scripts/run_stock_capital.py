#!/usr/bin/env python3
"""个股 + 5元门槛: 需要多少本金才可行"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a_share_backtest_v2 import load_kline
from run_backtest_v2 import UNIVERSE
import run_trend_filter_test as T
from run_param_robustness import make_momentum


T.COMMISSION = 0.0001
T.MIN_COMMISSION = 5.0   # 国信标准
T.SLIPPAGE = 0.001
STAMP = 0.001            # 个股卖出印花税

data = {}
for sym, name in UNIVERSE:
    df = load_kline(sym, 750)
    if df is not None and len(df) >= 600:
        data[sym] = df
bench = load_kline('sh000300', 750)
bdates = bench['日期'].dt.strftime('%Y-%m-%d').values
strat = make_momentum(0.998, 20, 20)

win = 60
windows = [(bdates[i], bdates[i+win-1]) for i in range(0, len(bdates)-win, win)]

print("="*88)
print("个股模式 + 5元佣金起收 + 印花税0.1% — 本金门槛测算")
print("="*88)
print(f"{'本金':>9}{'持仓数':>7}{'单票仓位':>10}{'单笔金额':>10}{'5元占单边':>11}{'往返总成本':>11}{'平均收益':>11}{'为正':>9}{'平均回撤':>10}{'最差窗口':>10}")
print("-"*88)

for cap in [2000.0, 5000.0, 10000.0, 20000.0, 50000.0]:
    for npos, pct in [(1, 0.95), (2, 0.45), (3, 0.30)]:
        T.CAPITAL = cap
        rets, dds = [], []
        for s, e in windows:
            try:
                r = T.run_window(data, bench, s, e, strat, max_pos=npos, max_pct=pct)
                rets.append(r['ret'])
                dds.append(r['dd'])
            except Exception:
                rets.append(0.0)
                dds.append(0.0)
        if not rets: continue
        single = cap * pct
        comm_pct = 5.0 / single if single > 0 else 1.0
        round_cost = comm_pct*2 + T.SLIPPAGE*2 + STAMP
        pos = sum(1 for x in rets if x > 0)
        print(f"{cap:>9.0f}{npos:>7}{pct*100:>9.0f}%{single:>10.0f}{comm_pct*100:>10.2f}%"
              f"{round_cost*100:>10.2f}%{np.mean(rets)*100:>10.2f}%{pos:>5}/{len(windows)}{np.mean(dds)*100:>9.1f}%{min(rets)*100:>9.2f}%")
