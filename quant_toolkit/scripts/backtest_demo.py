#!/usr/bin/env python3
"""
backtest_demo.py — 最小可用回测引擎（含手续费/滑点/止损/冷却期）
用法:
    python backtest_demo.py                 # 用内置BTC假数据演示
    python backtest_demo.py --csv btc.csv   # 用自己拉的真实数据
"""
import argparse
import csv

import numpy as np

import indicators as ind


# ─── 参数区（新手从这里调） ──────────────────────────────
INITIAL_CAPITAL = 1000.0   # 初始资金
POSITION_PCT = 0.10        # 单笔仓位比例 (10%)
FEE_RATE = 0.001           # 手续费 (现货0.1%)
SLIPPAGE = 0.0003          # 滑点 (3bp)
COOLDOWN = 20              # 冷却期: 多少根K线后才能再开仓
STOP_LOSS = 0.05           # 止损 5%
TAKE_PROFIT = 0.15         # 止盈 15%
MAX_HOLD = 72              # 持仓超时 72根K线强制平仓


def load_csv(path):
    """读取CSV: ts,open,high,low,close,volume"""
    closes, highs, lows = [], [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            closes.append(float(row["close"]))
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
    return np.array(closes), np.array(highs), np.array(lows)


def fake_data(n=720):
    """无数据时生成一段演示K线（随机游走+趋势）"""
    rng = np.random.default_rng(42)
    trend = np.linspace(0, 0.3, n)
    noise = rng.normal(0, 0.02, n).cumsum()
    close = 100 * np.exp(trend + noise)
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    return close, high, low


def backtest(close, high, low, verbose=True):
    """核心回测循环。返回结果dict。"""
    n = len(close)
    signal = ind.ema(close, 12) > ind.ema(close, 26)  # 双均线信号
    signal = np.where(signal, 1.0, -1.0)

    cash = INITIAL_CAPITAL
    qty = 0.0
    entry_price = 0.0
    entry_bar = 0
    last_trade = -COOLDOWN
    trades = []
    equity = np.zeros(n)
    equity[0] = INITIAL_CAPITAL

    for i in range(1, n):
        price = close[i]
        h, l = high[i], low[i]

        # 1. 持仓管理
        if qty > 0:
            pnl_pct = (price - entry_price) / entry_price
            hold = i - entry_bar
            # 用最高/最低价检查止损止盈是否被触及
            high_pnl = (h - entry_price) / entry_price
            low_pnl = (l - entry_price) / entry_price
            hit_sl = low_pnl <= -STOP_LOSS
            hit_tp = high_pnl >= TAKE_PROFIT
            timeout = hold >= MAX_HOLD

            if hit_sl or hit_tp or timeout:
                exit_px = price * (1 - FEE_RATE) * (1 - SLIPPAGE)
                cash += qty * exit_px
                reason = "SL" if hit_sl else ("TP" if hit_tp else "TIMEOUT")
                trades.append({"type": reason, "pnl_pct": pnl_pct * 100, "hold": hold})
                qty = 0.0

        # 2. 开仓
        if qty == 0 and (i - last_trade) >= COOLDOWN and not np.isnan(signal[i]):
            if signal[i] > 0:  # 只做多
                invest = cash * POSITION_PCT
                if invest >= 5:
                    buy_px = price * (1 + FEE_RATE) * (1 + SLIPPAGE)
                    qty = invest / buy_px
                    entry_price = buy_px
                    entry_bar = i
                    last_trade = i

        equity[i] = cash + qty * price if qty > 0 else cash

    # 收盘强制平仓
    if qty > 0:
        cash += qty * close[-1] * (1 - FEE_RATE) * (1 - SLIPPAGE)
        equity[-1] = cash

    # 3. 指标计算
    ret_pct = (equity[-1] / INITIAL_CAPITAL - 1) * 100
    log_ret = np.diff(np.log(equity + 1e-10))
    sharpe = (log_ret.mean() / log_ret.std() * np.sqrt(365 * 24)) if log_ret.std() > 1e-8 else 0.0

    peak = np.maximum.accumulate(equity)
    max_dd = float(((peak - equity) / (peak + 1e-10)).max() * 100)

    wins = [t for t in trades if t["pnl_pct"] > 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0.0

    result = {
        "初始资金": INITIAL_CAPITAL,
        "最终权益": round(equity[-1], 2),
        "收益率%": round(ret_pct, 2),
        "Sharpe": round(sharpe, 2),
        "最大回撤%": round(max_dd, 2),
        "交易次数": len(trades),
        "胜率%": round(win_rate, 1),
        "盈亏笔数": f"{len(wins)}W/{len(trades)-len(wins)}L",
    }
    if verbose:
        print("════ 回测结果 ════")
        for k, v in result.items():
            print(f"  {k}: {v}")
        if trades:
            recent = [f"{t['type']} {t['pnl_pct']:.1f}%" for t in trades[-3:]]
            print(f"  最近3笔: {recent}")
    return result


def main():
    parser = argparse.ArgumentParser(description="最小回测引擎")
    parser.add_argument("--csv", default=None, help="K线CSV路径（ts,open,high,low,close,volume）")
    parser.add_argument("--capital", type=float, default=INITIAL_CAPITAL)
    args = parser.parse_args()

    if args.csv:
        close, high, low = load_csv(args.csv)
        print(f"✅ 加载 {len(close)} 根K线: {args.csv}")
    else:
        close, high, low = fake_data()
        print("⚠️ 使用内置演示数据（随机游走）。用 --csv 指定真实数据。")

    backtest(close, high, low)


if __name__ == "__main__":
    main()
