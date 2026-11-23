#!/usr/bin/env python3
"""
策略 vs 买入持有 — 逐窗口超额 (决定"值不值得做"的最后一问)
============================================================
如果策略不能稳定跑赢"啥也不做买沪深300ETF持有"，
那所有交易、所有代码都是白费，直接持有ETF更好。
"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_trend_filter_test as T
from run_trend_filter_test import load_all
from run_param_robustness import make_momentum


data, bench = load_all()
etf300 = data.get('sh510300')
bdates = bench['日期'].dt.strftime('%Y-%m-%d').values
strat = make_momentum(0.998, 20, 20)
win = 60
windows = [(bdates[i], bdates[i + win - 1]) for i in range(0, len(bdates) - win, win)]


def run_case(label, capital, comm, min_fee):
    print("\n" + "=" * 96)
    print(f"【{label}】本金{capital:.0f}元 | 佣金{comm*10000:.1f}bp 最低{min_fee:.0f}元")
    print("=" * 96)
    print(f"{'窗口':<26}{'策略':>10}{'买入持有':>11}{'超额':>10}{'交易':>6}")
    print("-" * 96)

    old = (T.CAPITAL, T.COMMISSION, T.MIN_COMMISSION)
    T.CAPITAL, T.COMMISSION, T.MIN_COMMISSION = capital, comm, min_fee
    try:
        rets, bhs, ns = [], [], []
        for s, e in windows:
            r = T.run_window(data, bench, s, e, strat, max_pos=3, max_pct=0.35)
            b = T.buy_and_hold(bench, s, e, etf_df=etf300)
            rets.append(r['ret'])
            bhs.append(b)
            ns.append(r['n'])
            ex = r['ret'] - b
            print(f"{s}~{e:<12}{r['ret']*100:>9.2f}%{b*100:>10.2f}%{ex*100:>9.2f}%{r['n']:>6}")
    finally:
        T.CAPITAL, T.COMMISSION, T.MIN_COMMISSION = old

    ex = [rets[i] - bhs[i] for i in range(len(rets))]
    pos = sum(1 for x in rets if x > 0)
    posex = sum(1 for x in ex if x > 0)
    print("-" * 96)
    print(f"策略平均 {np.mean(rets)*100:+.2f}% | 买入持有平均 {np.mean(bhs)*100:+.2f}% | "
          f"平均超额 {np.mean(ex)*100:+.2f}%")
    print(f"策略为正 {pos}/{len(windows)} | 超额为正 {posex}/{len(windows)}")
    print(f"超额中位 {np.median(ex)*100:+.2f}% | 超额标准差 {np.std(ex)*100:.2f}%")
    return {'ret': float(np.mean(rets)), 'bh': float(np.mean(bhs)),
            'excess': float(np.mean(ex)), 'pos': pos, 'posex': posex,
            'ex_median': float(np.median(ex)), 'ex_std': float(np.std(ex)),
            'n_windows': len(windows)}


if __name__ == '__main__':
    cases = [
        ('2000元 国信标准(5元起收)', 2000.0, 0.0001, 5.0),
        ('2000元 免五', 2000.0, 0.0001, 0.0),
        ('2000元 最低1元', 2000.0, 0.0001, 1.0),
        ('5000元 国信标准(5元起收)', 5000.0, 0.0001, 5.0),
        ('5000元 最低1元', 5000.0, 0.0001, 1.0),
        ('20000元 国信标准(5元起收)', 20000.0, 0.0001, 5.0),
    ]
    out = {}
    for label, cap, comm, mf in cases:
        out[label] = run_case(label, cap, comm, mf)

    print("\n\n" + "=" * 96)
    print("总表: 策略 vs 买入持有沪深300ETF")
    print("=" * 96)
    print(f"{'方案':<26}{'策略均值':>10}{'基准均值':>10}{'平均超额':>10}{'超额为正':>10}{'超额中位':>10}")
    print("-" * 96)
    for label, r in out.items():
        print(f"{label:<26}{r['ret']*100:>9.2f}%{r['bh']*100:>9.2f}%{r['excess']*100:>9.2f}%"
              f"{r['posex']:>5}/{r['n_windows']}{r['ex_median']*100:>9.2f}%")

    import json
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'logs', 'vs_buyhold.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
