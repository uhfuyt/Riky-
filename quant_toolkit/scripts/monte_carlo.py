#!/usr/bin/env python3
"""
monte_carlo.py — 蒙特卡洛验证（Bootstrap）
核心问题: 回测赚钱是策略能力还是运气？
方法: 把交易顺序随机打乱N次，如果打乱后依然赚钱 → 策略有真本事。
      如果只有原顺序赚钱 → 纯运气（幸存者偏差）。
用法:
    python monte_carlo.py                      # 演示数据
    python monte_carlo.py --csv btc.csv        # 真实K线
"""
import argparse
import csv

import numpy as np

import backtest_demo as bt
import indicators as ind

N_SIMULATIONS = 1000  # 打乱次数


def load_csv(path):
    closes, highs, lows = [], [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            closes.append(float(row["close"]))
            highs.append(float(row["high"]))
            lows.append(float(row["low"]))
    return np.array(closes), np.array(highs), np.array(lows)


def get_trade_pnls(close, high, low):
    """用backtest_demo的引擎跑一遍, 提取每笔交易pnl序列"""
    # 复用 backtest_demo 的核心逻辑: 这里简化——直接跑引擎并返回交易列表
    n = len(close)
    signal = ind.ema(close, 12) > ind.ema(close, 26)
    signal = np.where(signal, 1.0, -1.0)

    cash = bt.INITIAL_CAPITAL
    qty = 0.0
    entry_price = 0.0
    entry_bar = 0
    last_trade = -bt.COOLDOWN
    trade_pnls = []  # 每笔的pnl_pct

    for i in range(1, n):
        price = close[i]
        h, l = high[i], low[i]
        if qty > 0:
            high_pnl = (h - entry_price) / entry_price
            low_pnl = (l - entry_price) / entry_price
            hit_sl = low_pnl <= -bt.STOP_LOSS
            hit_tp = high_pnl >= bt.TAKE_PROFIT
            timeout = (i - entry_bar) >= bt.MAX_HOLD
            if hit_sl or hit_tp or timeout:
                exit_px = price * (1 - bt.FEE_RATE) * (1 - bt.SLIPPAGE)
                cash += qty * exit_px
                pnl_pct = (exit_px - entry_price) / entry_price
                trade_pnls.append(pnl_pct)
                qty = 0.0
        if qty == 0 and (i - last_trade) >= bt.COOLDOWN and not np.isnan(signal[i]):
            if signal[i] > 0:
                invest = cash * bt.POSITION_PCT
                if invest >= 5:
                    buy_px = price * (1 + bt.FEE_RATE) * (1 + bt.SLIPPAGE)
                    qty = invest / buy_px
                    entry_price = buy_px
                    entry_bar = i
                    last_trade = i
    return trade_pnls


def bootstrap(pnls, n_sim=N_SIMULATIONS):
    """打乱交易顺序, 模拟最终收益分布"""
    if len(pnls) < 5:
        return {"error": "交易笔数不足(<5)，无法验证"}
    final_pnls = []
    for _ in range(n_sim):
        shuffled = pnls.copy()
        np.random.shuffle(shuffled)
        equity = bt.INITIAL_CAPITAL
        for p in shuffled:
            equity *= (1 + p)
        final_pnls.append(equity - bt.INITIAL_CAPITAL)
    final_pnls = np.array(final_pnls)
    return {
        "模拟次数": n_sim,
        "交易笔数": len(pnls),
        "中位数收益$": round(float(np.median(final_pnls)), 2),
        "P10收益$": round(float(np.percentile(final_pnls, 10)), 2),
        "P90收益$": round(float(np.percentile(final_pnls, 90)), 2),
        "正收益概率%": round(float(np.mean(final_pnls > 0) * 100), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="蒙特卡洛Bootstrap验证")
    parser.add_argument("--csv", default=None, help="K线CSV路径")
    parser.add_argument("--sims", type=int, default=N_SIMULATIONS)
    args = parser.parse_args()

    if args.csv:
        close, high, low = load_csv(args.csv)
    else:
        close, high, low = bt.fake_data()

    # 1. 原始回测
    print("════ 原始回测 ════")
    bt.backtest(close, high, low, verbose=True)

    # 2. 提取交易
    pnls = get_trade_pnls(close, high, low)
    print(f"\n提取到 {len(pnls)} 笔交易")

    # 3. Bootstrap
    print(f"\n════ Bootstrap验证 (打乱{args.sims}次) ════")
    result = bootstrap(pnls, args.sims)
    if "error" in result:
        print(f"  ⚠️ {result['error']}")
        return
    for k, v in result.items():
        print(f"  {k}: {v}")

    # 4. 判定
    prob = result["正收益概率%"]
    print("\n════ 判定 ════")
    if prob >= 95:
        print(f"  ✅ 正收益概率 {prob}% ≥ 95% → 策略有真本事，可进入虚拟盘验证")
    elif prob >= 50:
        print(f"  ⚠️ 正收益概率 {prob}% → 策略勉强，但运气成分大，建议改参数重试")
    else:
        print(f"  🔴 正收益概率 {prob}% < 50% → 纯运气/负期望！这个策略不能实盘")


if __name__ == "__main__":
    main()
