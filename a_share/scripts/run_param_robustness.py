#!/usr/bin/env python3
"""
动量突破V2 参数稳健性扫描
=========================
在多个参数组合 + 不同市场阶段下, 检查动量策略是否稳定
稳健 = 大部分参数组合都赚钱, 不是只在某个点赚钱
"""
import os, sys, json
import numpy as np
import pandas as pd
from datetime import datetime

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from a_share_backtest_v2 import load_kline
from run_oos_test import load_etf_set, simple_portfolio_backtest
from a_share_backtest_v2 import STRATEGIES_V2


def make_momentum(break_thr, ma_n, exit_ma_n):
    """参数化的动量策略"""
    def fn(kline, idx):
        if idx < max(ma_n, exit_ma_n) + 2:
            return 'HOLD'
        close = kline['收盘'].values
        high = close[idx-19:idx+1].max()
        ma = close[idx-ma_n+1:idx+1].mean()
        ex_ma = close[idx-exit_ma_n+1:idx+1].mean()
        if close[idx] > high * break_thr and close[idx] > ma:
            return 'BUY'
        if close[idx] < ex_ma:
            return 'SELL'
        return 'HOLD'
    return fn


def main():
    data = load_etf_set()
    is_df = {s: df.iloc[:500].reset_index(drop=True) for s, df in data.items()}
    oos_df = {s: df.iloc[500:].reset_index(drop=True) for s, df in data.items()}

    print("="*94)
    print("动量突破 参数稳健性扫描 (本金2000元 ETF)")
    print("="*94)
    print(f"{'突破阈值':>10}{'入场MA':>9}{'出场MA':>9}{'IS收益':>11}{'OOS收益':>11}{'OOS交易':>9}{'OOS费':>9}{'判定':>16}")
    print("-"*94)

    results = []
    for thr in [0.990, 0.995, 0.998]:
        for ma_n, ex_n in [(10, 10), (20, 10), (20, 20), (30, 10)]:
            fn = make_momentum(thr, ma_n, ex_n)
            try:
                is_r = simple_portfolio_backtest(is_df, fn)
                oos_r = simple_portfolio_backtest(oos_df, fn)
            except Exception as e:
                print(f"{thr:>10}{ma_n:>9}{ex_n:>9}  失败: {e}")
                continue
            if not is_r or not oos_r:
                continue
            ok = oos_r['total_return'] > 0
            results.append({
                'thr': thr, 'ma': ma_n, 'exit_ma': ex_n,
                'IS': is_r['total_return'], 'OOS': oos_r['total_return'],
                'OOS_n': oos_r['n_trades'], 'OOS_fees': oos_r['total_fees'],
                'OOS_dd': oos_r['max_drawdown'], 'OOS_sharpe': oos_r['sharpe'],
            })
            print(f"{thr:>10.3f}{ma_n:>9}{ex_n:>9}{is_r['total_return']*100:>10.2f}%"
                  f"{oos_r['total_return']*100:>10.2f}%{oos_r['n_trades']:>9}"
                  f"{oos_r['total_fees']:>8.0f}元{'✅正' if ok else '❌负':>16}")

    if results:
        pos = sum(1 for r in results if r['OOS'] > 0)
        avg_oos = np.mean([r['OOS'] for r in results])
        med_oos = np.median([r['OOS'] for r in results])
        print("-"*94)
        print(f"参数组数: {len(results)} | OOS为正: {pos}/{len(results)} ({pos/len(results)*100:.0f}%)")
        print(f"OOS平均收益: {avg_oos*100:+.2f}% | 中位数: {med_oos*100:+.2f}%")

        # 找最稳的参数组合: OOS正 + 交易数适中 + 回撤小
        good = [r for r in results if r['OOS'] > 0 and r['OOS_n'] >= 30]
        if good:
            best = max(good, key=lambda r: r['OOS'])
            print(f"\n★ 最优稳健组合: 突破阈值={best['thr']} 入场MA={best['ma']} 出场MA={best['exit_ma']}")
            print(f"  IS {best['IS']*100:+.2f}% → OOS {best['OOS']*100:+.2f}% | "
                  f"回撤 {best['OOS_dd']*100:.1f}% | Sharpe {best['OOS_sharpe']:.2f} | {best['OOS_n']}笔")

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(ENGINE_DIR, 'logs', f'param_robustness_{stamp}.json')
    with open(out, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n已保存: {out}")


if __name__ == '__main__':
    main()
