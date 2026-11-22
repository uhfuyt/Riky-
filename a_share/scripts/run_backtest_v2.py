#!/usr/bin/env python3
"""A股策略回测 v2 — 主执行器"""
import os, sys, json
from datetime import datetime

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from a_share_backtest_v2 import (
    run_portfolio_backtest, STRATEGIES_V2, load_kline, log,
    INITIAL_CAPITAL, calc_max_drawdown, calc_sharpe,
)

OUT_DIR = os.path.join(ENGINE_DIR, 'logs')

# 股票池(中证100前30) — 硬编码避免akshare依赖
# 真实股票池 = akshare 中证100前30 实际返回的标的 (2026-11-22 拉取, 30只全有数据)
UNIVERSE = [
    ('000002','万科A'),('000063','中兴通讯'),('000100','TCL科技'),('000333','美的集团'),
    ('000338','潍柴动力'),('000425','徐工机械'),('000538','云南白药'),('000651','格力电器'),
    ('000725','京东方A'),('000792','盐湖股份'),('000807','云铝股份'),('000963','华东医药'),
    ('001979','招商蛇口'),('002001','新和成'),('002028','思源电气'),('002179','中航光电'),
    ('002230','科大讯飞'),('002352','顺丰控股'),('002371','北方华创'),('002415','海康威视'),
    ('002422','科伦药业'),('002460','赣锋锂业'),('002463','沪电股份'),('002466','天齐锂业'),
    ('002475','立讯精密'),('002594','比亚迪'),('002625','光启技术'),('002714','牧原股份'),
    ('300014','亿纬锂能'),('300015','爱尔眼科'),
]

# ETF池
ETF_POOL = [
    ('sh510300','沪深300ETF'),('sh510500','中证500ETF'),('sh512100','中证1000ETF'),
    ('sh588000','科创50ETF'),('sz159915','创业板ETF'),('sh510880','红利ETF'),
    ('sz159919','沪深300ETF深'),('sh513100','纳指ETF'),('sh513500','标普500ETF'),
    ('sh512880','证券ETF'),('sh515180','红利低波ETF'),('sh516160','新能源ETF'),
    ('sh515790','光伏ETF'),('sh512170','医疗ETF'),('sh512690','酒ETF'),
    ('sz159941','纳指ETF深'),
]


def benchmark(capital=INITIAL_CAPITAL, datalen=750):
    """沪深300基准 (买入持有, 含一次性买入费用)"""
    df = load_kline('sh000300', datalen)
    if df is None or len(df) < 100:
        return None
    closes = df['收盘'].values
    # 起点收盘买入
    entry = closes[25]
    # ETF/指数免印花税, 按个股口径保守算佣金+滑点
    fee = capital * (0.00025 + 0.001)
    shares = capital / (entry * (1 + 0.00025 + 0.001))
    values = []
    for c in closes[25:]:
        v = cash = capital - (entry * shares + entry * shares * (0.00025 + 0.001))
        v = shares * c + cash
        values.append(v)
    rets = [(values[i]/values[i-1]-1) for i in range(1, len(values))]
    return {
        'name': '沪深300基准(买入持有)',
        'initial_capital': capital,
        'final_value': values[-1],
        'total_return': values[-1]/capital - 1,
        'annual_return': (values[-1]/capital)**(252/len(values)) - 1,
        'max_drawdown': calc_max_drawdown(values),
        'sharpe': calc_sharpe(rets),
        'days': len(values),
    }


def run_all(capital=INITIAL_CAPITAL, is_etf=False, tag=''):
    results = []
    symbols = [s for s, n in UNIVERSE]
    names = {s: n for s, n in UNIVERSE}
    if is_etf:
        symbols = [s for s, n in ETF_POOL]
        names = {s: n for s, n in ETF_POOL}

    for key, (sname, fn) in STRATEGIES_V2.items():
        log(f"=== 回测 {sname} ({key}) {'[ETF]' if is_etf else '[个股]'} ===")
        try:
            r = run_portfolio_backtest(
                symbols, names, fn, sname,
                capital=capital, datalen=750,
                is_etf=is_etf,
                # ETF 佣金按万1无最低门槛, 个股按万2.5+5元门槛
                commission_rate=0.0001 if is_etf else 0.00025,
                min_commission=0.0 if is_etf else 5.0,
                stamp_tax=0.0 if is_etf else 0.001,
                stop_loss=0.08, take_profit=0.25,
                max_position_pct=(0.95 if not is_etf else 0.35),
                max_positions=(2 if not is_etf else 3),
            )
            if r:
                results.append(r)
                log(f"  收益 {r['total_return']*100:+.2f}% | 年化 {r['annual_return']*100:+.2f}% | "
                    f"Sharpe {r['sharpe']:.2f} | 回撤 {r['max_drawdown']*100:.1f}% | "
                    f"交易 {r['n_trades']}笔 | 胜率 {r['win_rate']*100:.0f}% | 费 {r['total_fees']:.2f}元")
        except Exception as e:
            import traceback
            log(f"  失败: {e}")
            traceback.print_exc()
    return results


def main():
    capital = float(sys.argv[1]) if len(sys.argv) > 1 else INITIAL_CAPITAL
    mode = sys.argv[2] if len(sys.argv) > 2 else 'stock'

    log(f"本金={capital}元 模式={mode}")
    bench = benchmark(capital)
    if bench:
        log(f"基准 沪深300: {bench['total_return']*100:+.2f}% | 年化 {bench['annual_return']*100:+.2f}% | "
            f"Sharpe {bench['sharpe']:.2f} | 回撤 {bench['max_drawdown']*100:.1f}%")

    results = run_all(capital, is_etf=(mode == 'etf'), tag=mode)

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUT_DIR, f'backtest_v2_{mode}_{stamp}.json')
    with open(out, 'w') as f:
        json.dump({'mode': mode, 'capital': capital, 'benchmark': bench,
                   'results': results}, f, ensure_ascii=False, indent=1)
    log(f"已保存: {out}")

    # 汇总表
    print("\n" + "="*94)
    print(f"A股回测 v2 汇总  本金={capital}元  模式={mode}")
    print("="*94)
    print(f"{'策略':<14}{'总收益':>10}{'年化':>10}{'Sharpe':>9}{'最大回撤':>10}{'交易数':>8}{'胜率':>8}{'费用':>9}")
    print("-"*94)
    if bench:
        print(f"{'【基准】':<14}{bench['total_return']*100:>9.2f}%{bench['annual_return']*100:>9.2f}%"
              f"{bench['sharpe']:>9.2f}{bench['max_drawdown']*100:>9.1f}%{'—':>8}{'—':>8}{'—':>9}")
    for r in results:
        print(f"{r['strategy']:<14}{r['total_return']*100:>9.2f}%{r['annual_return']*100:>9.2f}%"
              f"{r['sharpe']:>9.2f}{r['max_drawdown']*100:>9.1f}%{r['n_trades']:>8}"
              f"{r['win_rate']*100:>7.0f}%{r['total_fees']:>8.2f}元")
    print("="*94)


if __name__ == '__main__':
    main()
