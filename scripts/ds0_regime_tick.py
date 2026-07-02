#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[DS-0] 暗黑星火 · 全托管决策脚本
===================================
cron每15分钟跑一次:
  1. 拉 BTC/ETH 1h/4h/1d K线
  2. 三周期评分 (牛/震/熊)
  3. 匹配最优策略 (趋势/网格/做空)
  4. 输出简短报告 → 沉默 unless 异常
  5. 完全不调三方LLM API (memory铁律: cron禁烧钱)

零打扰原则: 正常时stdout为空 (cron no_agent模式 = 空stdout不汇报)
异常时才输出
"""
import os, sys, json, time
import urllib.request
import urllib.error
import numpy as np
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
LOG_DIR = "/home/admin/charon/bot_logs"
STATE_FILE = f"{LOG_DIR}/ds0_regime_state.json"
REGIME_LOG = f"{LOG_DIR}/ds0_regime.log"

os.makedirs(LOG_DIR, exist_ok=True)


def log(msg):
    ts = datetime.now(CST).strftime("%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(REGIME_LOG, 'a') as f:
        f.write(line + "\n")


def fetch_klines(symbol='BTCUSDT', interval='1h', limit=200):
    """拉币安K线（无需API key）"""
    try:
        url = f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}'
        r = urllib.request.urlopen(url, timeout=10)
        data = json.loads(r.read())
        closes = np.array([float(k[4]) for k in data])
        return closes
    except Exception as e:
        return None


def ema(s, p):
    a = np.array(s, dtype=float)
    if len(a) < p:
        return None
    k = 2.0 / (p + 1)
    o = np.empty_like(a)
    o[0] = a[0]
    for i in range(1, len(a)):
        o[i] = a[i] * k + o[i - 1] * (1 - k)
    return o


def rsi(closes, p=14):
    a = np.array(closes, dtype=float)
    if len(a) < p + 1:
        return 50.0
    d = np.diff(a)
    g = np.maximum(d, 0)
    l = np.maximum(-d, 0)
    ag = np.mean(g[-p:])
    al = np.mean(l[-p:])
    if al < 1e-10:
        return 100.0
    return 100.0 - 100.0 / (1 + ag / al)


def score_regime(closes_1h, closes_4h, closes_1d):
    """三周期评分: 牛/震/熊 (-100 ~ +100)
    正数=看多, 负数=看空, 0±20=震荡
    """
    score = 0

    # 1h权重10%
    if closes_1h is not None and len(closes_1h) >= 50:
        e20_1h = ema(closes_1h, 20)[-1]
        e50_1h = ema(closes_1h, 50)[-1]
        if e20_1h > e50_1h:
            score += 10
        else:
            score -= 10

    # 4h权重30%
    if closes_4h is not None and len(closes_4h) >= 50:
        e20_4h = ema(closes_4h, 20)[-1]
        e50_4h = ema(closes_4h, 50)[-1]
        r_4h = rsi(closes_4h)
        if e20_4h > e50_4h:
            score += 25 if r_4h < 70 else 15  # 趋势但RSI不高=健康涨
        else:
            score -= 25 if r_4h > 30 else 15

    # 1d权重60%
    if closes_1d is not None and len(closes_1d) >= 50:
        e20_1d = ema(closes_1d, 20)[-1]
        e50_1d = ema(closes_1d, 50)[-1]
        r_1d = rsi(closes_1d)
        change_30d = (closes_1d[-1] / closes_1d[-30] - 1) * 100 if len(closes_1d) >= 30 else 0
        if e20_1d > e50_1d:
            score += 50 if r_1d < 65 else 35  # 强势但别追顶
        else:
            score -= 50 if r_1d > 35 else 35
        # 30天涨跌幅微调
        if change_30d > 20:
            score -= 15  # 涨多了容易回调
        elif change_30d < -20:
            score += 15  # 跌多了容易反弹

    return max(-100, min(100, score))


def regime_label(score):
    """分数 → 周期标签"""
    if score >= 30:
        return "🟢 牛"
    elif score <= -30:
        return "🔴 熊"
    else:
        return "🟡 震"


def strategy_match(score):
    """周期 → 策略匹配"""
    if score >= 30:
        return "趋势跟踪(combo31/趋势/突破)"
    elif score <= -30:
        return "做空+均值回归(bear_paper/均值回归)"
    else:
        return "网格+震荡(现货网格/RSI均值回归)"


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"last_regime": None, "last_score": 0, "regime_changed_at": None, "tick_count": 0}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def check_paper_alive():
    """检查虚拟盘进程（与心跳同步）"""
    import subprocess
    expected_pids = {
        1498859: "combo31_paper",
        341826: "paper_engine_v1",
        390019: "sol_turtle_paper",
    }
    dead = []
    for pid, name in expected_pids.items():
        try:
            os.kill(pid, 0)
        except OSError:
            dead.append(name)
    return dead


def main():
    state = load_state()
    state["tick_count"] = state.get("tick_count", 0) + 1

    # 1. 拉K线 (BTC + ETH)
    btc_1h = fetch_klines('BTCUSDT', '1h', 100)
    btc_4h = fetch_klines('BTCUSDT', '4h', 100)
    btc_1d = fetch_klines('BTCUSDT', '1d', 100)

    if btc_1d is None:
        log("⚠️ K线获取失败, 跳过本次")
        save_state(state)
        return  # 静默

    # 2. 三周期评分
    score = score_regime(btc_1h, btc_4h, btc_1d)
    label = regime_label(score)
    strategy = strategy_match(score)

    # BTC当前价
    btc_price = btc_1d[-1]
    eth_1d = fetch_klines('ETHUSDT', '1d', 100)
    eth_price = eth_1d[-1] if eth_1d is not None else 0

    # 3. 周期切换检测
    regime_changed = state.get("last_regime") != label
    if regime_changed:
        state["regime_changed_at"] = datetime.now(CST).isoformat()
    state["last_regime"] = label
    state["last_score"] = score

    # 4. 进程存活检查
    dead_pids = check_paper_alive()

    # 5. 状态写盘
    state["btc_price"] = btc_price
    state["eth_price"] = eth_price
    state["updated_at"] = datetime.now(CST).isoformat()
    save_state(state)

    # 6. 决策输出 (静默原则: 正常不汇报, 异常/周期切换才汇报)
    output_lines = []

    if dead_pids:
        output_lines.append(f"🔴 虚拟盘进程死亡: {dead_pids}")

    if regime_changed and state["regime_changed_at"]:
        output_lines.append(
            f"⚡ 周期切换: {state.get('prev_regime', '?')} → {label} "
            f"(score={score:+d}) | 策略={strategy} | "
            f"BTC=${btc_price:,.0f} ETH=${eth_price:,.0f}"
        )

    # 异常score（极端值）
    if abs(score) >= 70:
        output_lines.append(
            f"⚠️ 极端周期 score={score:+d} {label} | "
            f"BTC=${btc_price:,.0f} | 策略={strategy}"
        )

    # 输出（cron no_agent模式: 空stdout静默, 有内容才推送）
    if output_lines:
        for line in output_lines:
            log(line)
        print("\n".join(output_lines))
    # 否则静默


if __name__ == "__main__":
    main()