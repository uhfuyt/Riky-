#!/usr/bin/env python3
"""
滚动窗口稳健性检验 — 策略到底能不能用
=======================================
把 750 天切成多个不重叠窗口, 每个窗口独立跑一次策略。
如果只有个别窗口赚钱 → 运气; 如果大多数窗口赚钱 → 真策略。
这是判断"要不要真金白银上"的最后一道关。
"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a_share_backtest_v2 import load_kline
from validate_paper_engine import replay



def main():
    bench = load_kline('sh000300', 750)
    dates = bench['日期'].dt.strftime('%Y-%m-%d').values

    print("=" * 92)
    print("滚动窗口检验 (不重叠, 每窗口约60交易日, ETF动量突破 0.998/MA20/MA20, 2000元)")
    print("=" * 92)
    print(f"{'窗口':<28}{'策略收益':>11}{'沪深300':>11}{'超额':>10}{'回撤':>9}{'交易':>7}{'胜率':>8}")
    print("-" * 92)

    win = 60
    results = []
    for i in range(0, len(dates) - win, win):
        s, e = dates[i], dates[i + win - 1]
        r = replay(start_date=s, end_date=e, sort_mode='code')
        # 基准
        b0 = float(bench['收盘'].iloc[i])
        b1 = float(bench['收盘'].iloc[i + win - 1])
        bret = b1 / b0 - 1
        excess = r['total_return'] - bret
        results.append({'s': s, 'e': e, 'ret': r['total_return'], 'bench': bret,
                        'excess': excess, 'dd': r['max_drawdown'],
                        'n': r['n_trades'], 'wr': r['win_rate']})
        print(f"{s}~{e:<12}{r['total_return']*100:>10.2f}%{bret*100:>10.2f}%"
              f"{excess*100:>9.2f}%{r['max_drawdown']*100:>8.1f}%{r['n_trades']:>7}"
              f"{r['win_rate']*100:>7.0f}%")

    print("-" * 92)
    if results:
        import numpy as np
        rets = [x['ret'] for x in results]
        exc = [x['excess'] for x in results]
        pos = sum(1 for x in rets if x > 0)
        pos_exc = sum(1 for x in exc if x > 0)
        print(f"窗口数: {len(results)}")
        print(f"策略为正: {pos}/{len(results)} ({pos/len(results)*100:.0f}%) | "
              f"超额为正: {pos_exc}/{len(results)} ({pos_exc/len(results)*100:.0f}%)")
        print(f"平均收益: {np.mean(rets)*100:+.2f}% | 中位数: {np.median(rets)*100:+.2f}%")
        print(f"平均超额: {np.mean(exc)*100:+.2f}% | 中位数: {np.median(exc)*100:+.2f}%")
        print(f"最好 {max(rets)*100:+.2f}% | 最差 {min(rets)*100:+.2f}% | 标准差 {np.std(rets)*100:.2f}%")
        print()
        verdict = "✅ 稳健, 可上模拟盘" if pos_exc / len(results) >= 0.6 else "❌ 不稳健, 需重新选策略"
        print(f"判定: {verdict}")


if __name__ == '__main__':
    main()
