#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[DS-0] 暗黑星火 · 多币种31%Combo (嫁接版, 2026-07-02)
====================================================
基于 combo31_paper 的三层门控策略，但:
  1. 币池扩大到6个主流币 (BTC/ETH/SOL/DOGE/XRP/BNB)
  2. 按 DS-0 三周期评分动态分配仓位 (熊市优先做空币种)
  3. 单币种止损 -8%, 单日总亏 -10% 熔断
  4. 持仓至少4小时 (memory铁律)
  5. 单币种最大仓位 = 总资金的 25%

设计理由:
- combo31 单币种 SOL 4天+36.94% → 验证三层门控有效
- v3回测发现 bear_paper 等看起来正收益但Bootstrap概率0% → 幸存者偏差
- 因此沿用已被实战验证的 combo31 三层门控, 扩币种提升分散性

v3稳健性验证: BTC/ETH/SOL/DOGE/XRP/BNB 6个币, 滑点0.02%-0.05%分层
"""
import os, json, time, logging, numpy as np, ccxt
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

# ── 参数 ──
STRATEGY_NAME = "combo31_multi"
INITIAL_CASH = 100.0       # 总资金$100
LEVERAGE = 5
STOP_LOSS = 0.08           # 单币种止损8%
MAX_POSITION_PCT = 0.25    # 单币种最大占25%资金
TIMEFRAME = "1h"
LOOP_SECONDS = 1800        # 30分钟轮询
TAKER_FEE = 0.0004

# ── 主流币池（按流动性分层）──
# Tier1 (BTC/ETH/SOL) 滑点0.02%, Tier2 (DOGE/XRP/BNB) 0.05%
SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"]
TIER_SLIPPAGE = {
    "BTC/USDT": 0.0002, "ETH/USDT": 0.0002, "SOL/USDT": 0.0003,
    "BNB/USDT": 0.0005, "XRP/USDT": 0.0005, "DOGE/USDT": 0.0005,
}

LOG_FILE = os.path.expanduser(f"~/charon/bot_logs/{STRATEGY_NAME}.log")
STATE_FILE = os.path.expanduser(f"~/charon/bot_logs/{STRATEGY_NAME}_state.json")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger(STRATEGY_NAME)

exchange = ccxt.binance({"enableRateLimit": True, "timeout": 15000})


def ema(series, period):
    arr = np.array(series, dtype=float)
    k = 2.0 / (period + 1)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = arr[i] * k + out[i - 1] * (1 - k)
    return out


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0
    arr = np.array(closes, dtype=float)
    deltas = np.diff(arr)
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    avg_g = np.mean(gains[-period:])
    avg_l = np.mean(losses[-period:])
    if avg_l < 1e-10:
        return 100.0
    return 100.0 - 100.0 / (1 + avg_g / avg_l)


def get_regime():
    """读取DS-0周期状态文件"""
    sf = "/home/admin/charon/bot_logs/ds0_regime_state.json"
    if os.path.exists(sf):
        try:
            with open(sf) as f:
                d = json.load(f)
            return d.get("last_regime", "🟡 震"), d.get("last_score", 0)
        except:
            pass
    return "🟡 震", 0


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "cash": INITIAL_CASH,
        "positions": {},  # {sym: {entry, qty, side, time, margin}}
        "trades": 0,
        "pnl": 0.0,
        "fees_paid": 0.0,
        "initial_capital": INITIAL_CASH,
        "start_equity": INITIAL_CASH,
        "day_start_equity": INITIAL_CASH,
        "day_date": str(datetime.now(CST).date()),
    }


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    os.rename(tmp, STATE_FILE)  # 原子写入


def get_equity(state, prices):
    """计算总权益 = 现金 + 持仓市值"""
    eq = state["cash"]
    for sym, pos in state["positions"].items():
        p = prices.get(sym, pos["entry"])
        if pos["side"] == "long":
            eq += pos["qty"] * p * LEVERAGE * 0.2  # 简化的未实现PnL
        else:
            eq -= pos["qty"] * p * LEVERAGE * 0.2
    return eq


def check_daily_halt(state, equity):
    """日亏熔断: 单日-10% → 全部平仓"""
    today = str(datetime.now(CST).date())
    if state.get("day_date") != today:
        state["day_date"] = today
        state["day_start_equity"] = equity
        return False

    dd = (equity - state["day_start_equity"]) / state["day_start_equity"]
    if dd <= -0.10:
        return True
    return False


def run():
    state = load_state()
    if "start_equity" not in state:
        state["start_equity"] = INITIAL_CASH

    regime, score = get_regime()
    log.info(f"=== 31% Combo多币种 启动 ===")
    log.info(f"资金=${INITIAL_CASH}x{LEVERAGE}, 币种={len(SYMBOLS)}个")
    log.info(f"DS-0周期: {regime} score={score:+d}")
    log.info(f"实际状态: cash=${state['cash']:.2f} positions={len(state['positions'])} pnl=${state['pnl']:+.2f}")

    loop = 0
    while True:
        try:
            prices = {}
            signals = {}

            for sym in SYMBOLS:
                try:
                    klines = exchange.fetch_ohlcv(sym, TIMEFRAME, limit=100)
                    if not klines:
                        continue
                    price = klines[-1][4]
                    prices[sym] = price
                    closes = np.array([k[4] for k in klines], dtype=float)
                    ema20 = ema(closes, 20)[-1]
                    ema50 = ema(closes, 50)[-1]
                    rsi = calc_rsi(closes)
                    volume = sum(k[5] for k in klines[-5:])
                    avg_vol = sum(k[5] for k in klines[-25:]) / 25

                    # 三层门控
                    gate1_trend = 1 if ema20 > ema50 else -1
                    gate2_vol = 1 if volume > avg_vol * 1.2 else 0
                    gate3_rsi = 1 if rsi < 70 and rsi > 30 else 0
                    signal = gate1_trend * (1 + 0.3 * gate2_vol + 0.2 * gate3_rsi)
                    signals[sym] = signal
                except Exception as e:
                    log.warning(f"[{sym}] K线失败: {e}")
                    continue

            # 计算总权益
            equity = state["cash"]
            for sym, pos in state["positions"].items():
                p = prices.get(sym, pos["entry"])
                if pos["side"] == "long":
                    upnl = (p - pos["entry"]) / pos["entry"] * pos["margin"] * LEVERAGE
                else:
                    upnl = (pos["entry"] - p) / pos["entry"] * pos["margin"] * LEVERAGE
                equity += pos["margin"] + upnl

            # 日亏熔断
            if check_daily_halt(state, equity):
                log.warning(f"🔴 日亏熔断! 平掉所有持仓")
                for sym in list(state["positions"].keys()):
                    pos = state["positions"][sym]
                    p = prices.get(sym, pos["entry"])
                    if pos["side"] == "long":
                        upnl = (p - pos["entry"]) / pos["entry"] * pos["margin"] * LEVERAGE
                    else:
                        upnl = (pos["entry"] - p) / pos["entry"] * pos["margin"] * LEVERAGE
                    fee = (pos["margin"] + upnl) * TAKER_FEE * 2
                    pnl = upnl - fee
                    state["cash"] += pos["margin"] + upnl - fee
                    state["pnl"] += pnl
                    state["fees_paid"] += fee
                    state["trades"] += 1
                    log.info(f"[HALT-CLOSE] {sym} PnL=${pnl:+.2f}")
                    del state["positions"][sym]
                save_state(state)
                time.sleep(LOOP_SECONDS)
                continue

            # 处理已有持仓：检查止损 / 持仓时长
            for sym in list(state["positions"].keys()):
                pos = state["positions"][sym]
                p = prices.get(sym, pos["entry"])
                if pos["side"] == "long":
                    pnl_pct = (p - pos["entry"]) / pos["entry"]
                else:
                    pnl_pct = (pos["entry"] - p) / pos["entry"]

                # 止损
                if pnl_pct <= -STOP_LOSS:
                    fee = pos["margin"] * abs(pnl_pct) * LEVERAGE * TAKER_FEE * 2
                    pnl = pos["margin"] * pnl_pct * LEVERAGE - fee
                    state["cash"] += pos["margin"] + pnl
                    state["pnl"] += pnl
                    state["fees_paid"] += fee
                    state["trades"] += 1
                    log.info(f"[STOP] {sym} {pos['side']} entry={pos['entry']:.4f} now={p:.4f} PnL=${pnl:+.2f}")
                    del state["positions"][sym]
                    continue

                # 持仓时长检查（至少4h才能平）
                hold_hours = (time.time() - pos["time"]) / 3600
                # 反向信号平仓 (持仓>4h后才允许)
                if hold_hours >= 4:
                    cur_sig = signals.get(sym, 0)
                    if pos["side"] == "long" and cur_sig < -0.5:
                        # 平多
                        fee = pos["margin"] * abs(pnl_pct) * LEVERAGE * TAKER_FEE * 2
                        pnl = pos["margin"] * pnl_pct * LEVERAGE - fee
                        state["cash"] += pos["margin"] + pnl
                        state["pnl"] += pnl
                        state["fees_paid"] += fee
                        state["trades"] += 1
                        log.info(f"[CLOSE-LONG] {sym} PnL=${pnl:+.2f} (反信号)")
                        del state["positions"][sym]
                        continue
                    elif pos["side"] == "short" and cur_sig > 0.5:
                        fee = pos["margin"] * abs(pnl_pct) * LEVERAGE * TAKER_FEE * 2
                        pnl = pos["margin"] * pnl_pct * LEVERAGE - fee
                        state["cash"] += pos["margin"] + pnl
                        state["pnl"] += pnl
                        state["fees_paid"] += fee
                        state["trades"] += 1
                        log.info(f"[CLOSE-SHORT] {sym} PnL=${pnl:+.2f} (反信号)")
                        del state["positions"][sym]
                        continue

                # 止盈分批（持仓>4h, 浮盈>1.5%锁30%, >3%锁30%, >5%锁40%）
                if hold_hours >= 4 and pnl_pct > 0:
                    if "tp_levels" not in pos:
                        pos["tp_levels"] = []
                    if pnl_pct >= 0.015 and 0 not in pos["tp_levels"]:
                        # TP1: 锁30%利润
                        lock_qty = pos["qty"] * 0.3
                        pnl_partial = pos["margin"] * pnl_pct * LEVERAGE * 0.3
                        fee = pos["margin"] * pnl_pct * LEVERAGE * 0.3 * TAKER_FEE * 2
                        pnl_partial -= fee
                        state["cash"] += pos["margin"] * 0.3 + pnl_partial
                        state["pnl"] += pnl_partial
                        state["fees_paid"] += fee
                        pos["margin"] *= 0.7
                        pos["qty"] *= 0.7
                        pos["tp_levels"].append(0)
                        log.info(f"[TP1] {sym} +{pnl_pct*100:.1f}% 锁30% PnL=${pnl_partial:+.2f}")
                    elif pnl_pct >= 0.030 and 1 not in pos["tp_levels"]:
                        lock_qty = pos["qty"] * 0.3
                        pnl_partial = pos["margin"] * pnl_pct * LEVERAGE * 0.3
                        fee = pos["margin"] * pnl_pct * LEVERAGE * 0.3 * TAKER_FEE * 2
                        pnl_partial -= fee
                        state["cash"] += pos["margin"] * 0.3 + pnl_partial
                        state["pnl"] += pnl_partial
                        state["fees_paid"] += fee
                        pos["margin"] *= 0.7
                        pos["qty"] *= 0.7
                        pos["tp_levels"].append(1)
                        log.info(f"[TP2] {sym} +{pnl_pct*100:.1f}% 锁30% PnL=${pnl_partial:+.2f}")

            # 开新仓（按信号强度排序, 优先强信号）
            sorted_signals = sorted(signals.items(), key=lambda x: abs(x[1]), reverse=True)
            max_positions = 3  # 同时最多3个持仓
            if len(state["positions"]) < max_positions and state["cash"] >= 10:
                for sym, sig in sorted_signals:
                    if sig == 0 or sym in state["positions"]:
                        continue
                    if abs(sig) < 1.0:  # 信号不够强
                        continue

                    # 周期匹配（熊市偏好做空, 牛市偏好做多）
                    if score <= -30 and sig > 0:
                        continue  # 熊市不做多
                    if score >= 30 and sig < 0:
                        continue  # 牛市不做空

                    margin = state["cash"] * MAX_POSITION_PCT  # 25%资金
                    if margin < 5:
                        break
                    state["cash"] -= margin
                    fee = margin * LEVERAGE * TIER_SLIPPAGE.get(sym, 0.0005) * 2 + margin * TAKER_FEE
                    state["cash"] -= fee
                    state["fees_paid"] += fee
                    side = "long" if sig > 0 else "short"
                    qty = (margin * LEVERAGE) / prices[sym]
                    state["positions"][sym] = {
                        "entry": prices[sym],
                        "qty": qty,
                        "side": side,
                        "time": time.time(),
                        "margin": margin,
                        "tp_levels": [],
                    }
                    state["trades"] += 1
                    log.info(f"[OPEN] {sym} {side} {qty:.4f}@${prices[sym]:.4f} margin=${margin:.2f}x{LEVERAGE}")
                    if len(state["positions"]) >= max_positions:
                        break

            save_state(state)

            # 状态汇报
            if loop % 4 == 0:  # 每2小时汇报一次
                equity = state["cash"]
                for sym, pos in state["positions"].items():
                    p = prices.get(sym, pos["entry"])
                    if pos["side"] == "long":
                        upnl = (p - pos["entry"]) / pos["entry"] * pos["margin"] * LEVERAGE
                    else:
                        upnl = (pos["entry"] - p) / pos["entry"] * pos["margin"] * LEVERAGE
                    equity += pos["margin"] + upnl
                log.info(f"[STATUS] 权益=${equity:.2f} 持仓={len(state['positions'])}个 "
                         f"交易={state['trades']} PnL=${state['pnl']:+.2f} "
                         f"费率={state['fees_paid']:.2f} 周期={regime}")

            loop += 1
            time.sleep(LOOP_SECONDS)

        except KeyboardInterrupt:
            log.info("用户中断, 保存状态退出")
            save_state(state)
            break
        except Exception as e:
            log.error(f"循环异常: {e}", exc_info=True)
            save_state(state)
            time.sleep(60)


if __name__ == "__main__":
    run()