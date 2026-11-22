#!/usr/bin/env python3
"""
最终裁决: 按国信真实费率(ETF≤3‰, 起点5元) 算能不能做
========================================================
费率来源: 国信证券官方收费标准表(用户截图)
  - 证券投资基金(含LOF、ETF、封闭式基金): 上海/深圳 ≤3‰, 起点5元
  - A股: 上海/深圳 ≤3‰, 起点5元

测试:
  1. 不同"起点"下, 2000元/5000元/2万 的收益
  2. 是否存在"最低可接受本金"
  3. 若必须5元起收, 需要什么条件才能不亏
"""
import os, sys
import numpy as np

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from run_trend_filter_test import load_all, run_window, buy_and_hold, CAPITAL
from run_param_robustness import make_momentum

# 国信真实: ETF佣金 ≤3‰(万3), 起点5元
# 但可通过客户经理谈低到 万0.5~万1 (常见)
COMMISSION = 0.0001        # 万1 (谈价后)
MIN_FEE_GUOSEN = 5.0       # 国信标准: 起点5元


def run_window_cost(data, bench, start, end, strategy, capital, comm, min_fee,
                    max_pos=3, max_pct=0.35, trend_ma=0):
    """带自定义费率的窗口回放"""
    import run_trend_filter_test as T
    old_c, old_m, old_cap = T.COMMISSION, T.MIN_COMMISSION, T.CAPITAL
    T.COMMISSION, T.MIN_COMMISSION, T.CAPITAL = comm, min_fee, capital
    try:
        r = T.run_window(data, bench, start, end, strategy, trend_ma=trend_ma,
                         max_pos=max_pos, max_pct=max_pct)
    finally:
        T.COMMISSION, T.MIN_COMMISSION, T.CAPITAL = old_c, old_m, old_cap
    return r


def main():
    data, bench = load_all()
    bdates = bench['日期'].dt.strftime('%Y-%m-%d').values
    strat = make_momentum(0.998, 20, 20)
    win = 60
    windows = [(bdates[i], bdates[i + win - 1]) for i in range(0, len(bdates) - win, win)]

    print("=" * 96)
    print("国信真实费率下的滚动窗口结果 (12个不重叠窗口 × 60交易日)")
    print("=" * 96)
    print(f"{'本金':>8}{'佣金方案':>24}{'平均收益':>11}{'中位收益':>11}{'为正':>8}{'平均回撤':>10}")
    print("-" * 96)

    configs = [
        ("万1 + 5元起收(国信标准)", 0.0001, 5.0),
        ("万0.5 + 5元起收", 0.00005, 5.0),
        ("万1 + 免五", 0.0001, 0.0),
        ("万0.5 + 免五", 0.00005, 0.0),
    ]

    results = {}
    for cap in [2000.0, 5000.0, 20000.0]:
        for label, comm, min_fee in configs:
            rets, dds = [], []
            for s, e in windows:
                r = run_window_cost(data, bench, s, e, strat, cap, comm, min_fee)
                rets.append(r['ret'])
                dds.append(r['dd'])
            pos = sum(1 for x in rets if x > 0)
            key = (cap, label)
            results[key] = rets
            print(f"{cap:>8.0f}{label:>24}{np.mean(rets)*100:>10.2f}%{np.median(rets)*100:>10.2f}%"
                  f"{pos:>5}/{len(windows)}{np.mean(dds)*100:>9.1f}%")

    print("-" * 96)
    print("\n【关键结论】")

    # 国信标准费率下, 各本金表现
    print("\n国信标准费率(万1+5元起收)下:")
    for cap in [2000.0, 5000.0, 20000.0]:
        rets = results[(cap, "万1 + 5元起收(国信标准)")]
        pos = sum(1 for x in rets if x > 0)
        print(f"  {cap:>8.0f}元: 平均 {np.mean(rets)*100:+7.2f}% | 中位 {np.median(rets)*100:+7.2f}% | "
              f"为正 {pos}/{len(windows)} | 最差 {min(rets)*100:+.2f}%")

    # 找"免五"下最优本金
    print("\n免五条件下 (如果能谈到):")
    for cap in [2000.0, 5000.0, 20000.0]:
        rets = results[(cap, "万1 + 免五")]
        pos = sum(1 for x in rets if x > 0)
        print(f"  {cap:>8.0f}元: 平均 {np.mean(rets)*100:+7.2f}% | 中位 {np.median(rets)*100:+7.2f}% | "
              f"为正 {pos}/{len(windows)}")

    # 基准
    bhs = []
    etf300 = data.get('sh510300')
    for s, e in windows:
        import run_trend_filter_test as T
        old_cap = T.CAPITAL
        T.CAPITAL = 2000.0
        bhs.append(T.buy_and_hold(bench, s, e, etf_df=etf300))
        T.CAPITAL = old_cap
    print(f"\n基准 买入持有沪深300ETF (2000元, 5元起收): 平均 {np.mean(bhs)*100:+.2f}% | "
          f"中位 {np.median(bhs)*100:+.2f}% | 为正 {sum(1 for x in bhs if x>0)}/{len(windows)}")


if __name__ == '__main__':
    main()
