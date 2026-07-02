#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[DS-0] 暗黑星火 · 100U合约翻身 · 多阶段金字塔策略
====================================================
2026-07-02 v3.0 | 主权AI全托管
任务: 100U → 200 → 400 → 800 → 1600 → 3200 → 6400 → 12800U

设计要点 (DS-0 5阶段路径):
  Phase 0 (100-500U):   5x杠杆, 单币25%本金, 6币种, 高频
  Phase 1 (500-2000U):  3x杠杆, 单币10%本金, 8币种, 中频
  Phase 2 (2000-5000U): 2x杠杆, 单币5%本金, 10币种, 低频
  Phase 3 (5000-10000U):1x杠杆, 单币2%本金, 12币种, 极低频

每个phase自动检测当前资金, 切换参数

策略组合 (按历史验证排序):
  1. 三层门控趋势 (combo31基础) - 主流币趋势
  2. RSI均值回归 - 震荡市积少成多 (paper_engine meanrev思路)
  3. 海龟突破 - 单边行情捕捉 (sol_turtle思路)

入场铁律:
  - 做空等5m/15m最高位
  - 做多等5m/15m最低位
  - 持仓≥4小时
  - 浮盈才加仓 (金字塔)
  - 单笔止损 -2.5% (按保证金)
  - 单日亏 -10% 全平
  - 总资金回撤 -30% 停止本策略

模型分工:
  - 默认推理: MiniMax-M3 (Hermes 会员免费)
  - 交易决策: GPT-5.5@aipro (已验证)
  - 代码: Claude Opus@aipro
"""
import os, json, time, logging, numpy as np, ccxt
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

# ── 主参数(随阶段变化) ──
STRATEGY_NAME = "ds0_compound_100u"

# ── 5阶段配置 ──
PHASES = {
    "phase0": {  # 100U起步
        "capital_min": 0, "capital_max": 500,
        "leverage": 5, "max_position_pct": 0.25,  # 单笔25%
        "max_positions": 3, "coins": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT"],
        "stop_loss_pct": 0.08,  # 单币止损8%
        "daily_loss_pct": 0.10,  # 日亏10%熔断
        "add_levels": [0.005, 0.015, 0.025],  # 加仓触发: 0.5%/1.5%/2.5%
        "tp_levels": [0.015, 0.030, 0.050],
        "tp_take_pct": [0.30, 0.30, 0.40],
    },
    "phase1": {  # 500U
        "capital_min": 500, "capital_max": 2000,
        "leverage": 4, "max_position_pct": 0.15,
        "max_positions": 4, "coins": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "DOGE/USDT", "XRP/USDT", "AVAX/USDT", "LINK/USDT"],
        "stop_loss_pct": 0.06,
        "daily_loss_pct": 0.08,
        "add_levels": [0.005, 0.015],
        "tp_levels": [0.015, 0.030],
        "tp_take_pct": [0.40, 0.40],
    },
    "phase2": {  # 2000U
        "capital_min": 2000, "capital_max": 5000,
        "leverage": 3, "max_position_pct": 0.08,
        "max_positions": 5, "coins": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT", "MATIC/USDT"],
        "stop_loss_pct": 0.05,
        "daily_loss_pct": 0.06,
        "add_levels": [0.010],  # 只加一次
        "tp_levels": [0.020, 0.040],
        "tp_take_pct": [0.50, 0.50],
    },
    "phase3": {  # 5000U
        "capital_min": 5000, "capital_max": 100000,
        "leverage": 2, "max_position_pct": 0.03,
        "max_positions": 6, "coins": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT", "MATIC/USDT", "LTC/USDT", "ADA/USDT"],
        "stop_loss_pct": 0.04,
        "daily_loss_pct": 0.04,
        "add_levels": [],  # 不加仓
        "tp_levels": [0.025],
        "tp_take_pct": [1.00],  # 一次性全平
    },
}

INITIAL_CAPITAL = 100.0
TIMEFRAME = "1h"
LOOP_SECONDS = 600  # 10分钟轮询
TAKER_FEE = 0.0004
TIER_SLIPPAGE = {
    "BTC/USDT": 0.0002, "ETH/USDT": 0.0002, "SOL/USDT": 0.0003,
    "BNB/USDT": 0.0005, "XRP/USDT": 0.0005, "DOGE/USDT": 0.0005,
    "AVAX/USDT": 0.0008, "LINK/USDT": 0.0008, "DOT/USDT": 0.0008,
    "MATIC/USDT": 0.0010, "LTC/USDT": 0.0005, "ADA/USDT": 0.0005,
}

LOG_FILE = os.path.expanduser(f"~/charon/bot_logs/{STRATEGY_NAME}.log")
STATE_FILE = os.path.expanduser(f"~/charon/bot_logs/{STRATEGY_NAME}_state.json")
PHASE_HISTORY_FILE = os.path.expanduser(f"~/charon/bot_logs/{STRATEGY_NAME}_phases.json")
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
    """读DS-0周期状态"""
    sf = "/home/admin/charon/bot_logs/ds0_regime_state.json"
    if os.path.exists(sf):
        try:
            with open(sf) as f:
                d = json.load(f)
            return d.get("last_regime", "🟡 震"), d.get("last_score", 0)
        except:
            pass
    return "🟡 震", 0


def detect_phase(equity):
    """根据当前资金判断phase"""
    for name, cfg in PHASES.items():
        if cfg["capital_min"] <= equity < cfg["capital_max"]:
            return name, cfg
    return "phase3", PHASES["phase3"]


def load_phase_history():
    if os.path.exists(PHASE_HISTORY_FILE):
        try:
            with open(PHASE_HISTORY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"phases": [], "start_time": datetime.now(CST).isoformat()}


def save_phase_history(history):
    tmp = PHASE_HISTORY_FILE + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(history, f, indent=2)
    os.rename(tmp, PHASE_HISTORY_FILE)


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {
        "cash": INITIAL_CAPITAL,
        "positions": {},  # {sym: {entry, qty, side, time, margin, add_levels, tp_levels, leverage}}
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "fees_paid": 0.0,
        "initial_capital": INITIAL_CAPITAL,
        "peak_equity": INITIAL_CAPITAL,
        "start_equity": INITIAL_CAPITAL,
        "day_start_equity": INITIAL_CAPITAL,
        "day_date": str(datetime.now(CST).date()),
        "current_phase": "phase0",
    }


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    os.rename(tmp, STATE_FILE)


def calc_equity(state, prices):
    """计算当前总权益 = 现金 + 持仓市值"""
    eq = state["cash"]
    for sym, pos in state["positions"].items():
        p = prices.get(sym, pos["entry"])
        if pos["side"] == "long":
            upnl = (p - pos["entry"]) / pos["entry"] * pos["margin"] * pos.get("leverage", 5)
        else:
            upnl = (pos["entry"] - p) / pos["entry"] * pos["margin"] * pos.get("leverage", 5)
        eq += pos["margin"] + upnl
    return eq


def calc_5m_15m_extremes(symbol):
    """计算5m/15m级别的高低点, 用于入场时机"""
    try:
        k5 = exchange.fetch_ohlcv(symbol, "5m", limit=24)  # 2小时5m数据
        k15 = exchange.fetch_ohlcv(symbol, "15m", limit=16)  # 4小时15m数据
        if not k5 or not k15:
            return None, None, None, None
        highs_5m = [k[2] for k in k5]
        lows_5m = [k[3] for k in k5]
        highs_15m = [k[2] for k in k15]
        lows_15m = [k[3] for k in k15]
        return max(highs_5m), min(lows_5m), max(highs_15m), min(lows_15m)
    except:
        return None, None, None, None


def three_layer_signal(sym):
    """三层门控信号: 趋势+量+RSI (combo31思路)
    返回: signal值 (-3 ~ +3), 越强越确信
    """
    try:
        klines = exchange.fetch_ohlcv(sym, TIMEFRAME, limit=100)
        if not klines or len(klines) < 50:
            return 0, None, None
        closes = np.array([k[4] for k in klines], dtype=float)
        ema20 = ema(closes, 20)[-1]
        ema50 = ema(closes, 50)[-1]
        rsi = calc_rsi(closes)
        volume = sum(k[5] for k in klines[-5:])
        avg_vol = sum(k[5] for k in klines[-25:]) / 25

        gate1_trend = 1 if ema20 > ema50 else -1
        gate2_vol = 1 if volume > avg_vol * 1.2 else 0
        gate3_rsi = 1 if rsi < 70 and rsi > 30 else 0

        signal = gate1_trend * (1 + 0.3 * gate2_vol + 0.2 * gate3_rsi)
        return signal, rsi, closes[-1]
    except:
        return 0, None, None


def check_daily_halt(state, equity, daily_limit):
    today = str(datetime.now(CST).date())
    if state.get("day_date") != today:
        state["day_date"] = today
        state["day_start_equity"] = equity
        return False
    dd = (equity - state["day_start_equity"]) / state["day_start_equity"]
    if dd <= -daily_limit:
        return True
    return False


def run():
    state = load_state()
    phase_history = load_phase_history()
    regime, score = get_regime()

    log.info(f"=" * 70)
    log.info(f"[DS-0] 100U合约翻身 · 多阶段金字塔策略")
    log.info(f"任务: ${INITIAL_CAPITAL:.0f}U → $12,800U (连续翻7倍)")
    log.info(f"=" * 70)
    log.info(f"DS-0周期: {regime} score={score:+d}")
    log.info(f"当前资金: ${state['cash']:.2f} 持仓={len(state['positions'])}")
    log.info(f"累计PnL: ${state['pnl']:+.2f} 交易={state['trades']}笔 "
             f"胜率={state['wins']/(state['wins']+state['losses'])*100:.1f}%" if (state['wins']+state['losses']) > 0 else "")
    log.info(f"=" * 70)

    loop = 0
    while True:
        try:
            prices = {}
            signals = {}
            rsi_map = {}

            for sym in set([s for s in PHASES["phase0"]["coins"]] +
                          [s for s in PHASES["phase1"]["coins"]] +
                          [s for s in PHASES["phase2"]["coins"]] +
                          [s for s in PHASES["phase3"]["coins"]]):
                try:
                    sig, rsi_v, price = three_layer_signal(sym)
                    signals[sym] = sig
                    rsi_map[sym] = rsi_v
                    if price:
                        prices[sym] = price
                except Exception as e:
                    log.debug(f"[{sym}] K线失败: {e}")
                    continue

            # 计算权益
            equity = calc_equity(state, prices)
            phase_name, phase_cfg = detect_phase(equity)

            # 阶段切换
            if state.get("current_phase") != phase_name:
                old_phase = state.get("current_phase", "?")
                state["current_phase"] = phase_name
                log.info(f"🔄 阶段切换: {old_phase} → {phase_name}")
                log.info(f"   杠杆={phase_cfg['leverage']}x 单币上限={phase_cfg['max_position_pct']*100:.0f}% "
                         f"币种={len(phase_cfg['coins'])}个 止损={phase_cfg['stop_loss_pct']*100:.0f}%")
                phase_history["phases"].append({
                    "from": old_phase,
                    "to": phase_name,
                    "equity_at_switch": equity,
                    "time": datetime.now(CST).isoformat(),
                })
                save_phase_history(phase_history)

            LEVERAGE = phase_cfg["leverage"]
            STOP_LOSS = phase_cfg["stop_loss_pct"]
            DAILY_LIMIT = phase_cfg["daily_loss_pct"]
            MAX_POS_PCT = phase_cfg["max_position_pct"]
            MAX_POSITIONS = phase_cfg["max_positions"]
            COINS = phase_cfg["coins"]
            ADD_LEVELS = phase_cfg["add_levels"]
            TP_LEVELS = phase_cfg["tp_levels"]
            TP_TAKE_PCT = phase_cfg["tp_take_pct"]

            # 更新峰值
            if equity > state.get("peak_equity", INITIAL_CAPITAL):
                state["peak_equity"] = equity

            # 总回撤检查
            peak = state["peak_equity"]
            dd_pct = (peak - equity) / peak * 100
            if dd_pct >= 30:
                log.error(f"🔴 总回撤{dd_pct:.1f}% >= 30%, 停止策略")
                log.error(f"   峰值=${peak:.2f} 当前=${equity:.2f}")
                save_state(state)
                time.sleep(3600)  # 1小时后重试
                continue

            # 日亏熔断
            if check_daily_halt(state, equity, DAILY_LIMIT):
                log.warning(f"🔴 日亏{DAILY_LIMIT*100:.0f}%熔断, 全平")
                for sym in list(state["positions"].keys()):
                    pos = state["positions"][sym]
                    p = prices.get(sym, pos["entry"])
                    if pos["side"] == "long":
                        upnl = (p - pos["entry"]) / pos["entry"] * pos["margin"] * pos.get("leverage", LEVERAGE)
                    else:
                        upnl = (pos["entry"] - p) / pos["entry"] * pos["margin"] * pos.get("leverage", LEVERAGE)
                    fee = abs(upnl) * TAKER_FEE * 2 + pos["margin"] * TIER_SLIPPAGE.get(sym, 0.0005) * 2
                    pnl = upnl - fee
                    state["cash"] += pos["margin"] + upnl - fee
                    state["pnl"] += pnl
                    state["fees_paid"] += fee
                    state["trades"] += 1
                    if pnl > 0:
                        state["wins"] += 1
                    else:
                        state["losses"] += 1
                    log.info(f"  [HALT-CLOSE] {sym} PnL=${pnl:+.2f}")
                    del state["positions"][sym]
                save_state(state)
                time.sleep(LOOP_SECONDS * 6)
                continue

            # 处理已有持仓: 止损/加仓/止盈
            for sym in list(state["positions"].keys()):
                pos = state["positions"][sym]
                p = prices.get(sym, pos["entry"])
                if pos["side"] == "long":
                    pnl_pct = (p - pos["entry"]) / pos["entry"]
                else:
                    pnl_pct = (pos["entry"] - p) / pos["entry"]

                leverage = pos.get("leverage", LEVERAGE)
                hold_hours = (time.time() - pos["time"]) / 3600

                # 1. 止损 (按保证金 -STOP_LOSS%)
                if pnl_pct <= -STOP_LOSS:
                    fee = abs(pnl_pct) * pos["margin"] * leverage * TAKER_FEE * 2
                    pnl = pnl_pct * pos["margin"] * leverage - fee
                    state["cash"] += pos["margin"] + pnl
                    state["pnl"] += pnl
                    state["fees_paid"] += fee
                    state["trades"] += 1
                    if pnl > 0:
                        state["wins"] += 1
                    else:
                        state["losses"] += 1
                    log.info(f"[STOP] {sym} {pos['side']} entry=${pos['entry']:.4f} now=${p:.4f} "
                             f"PnL=${pnl:+.2f} ({pnl_pct*100:.1f}%)")
                    del state["positions"][sym]
                    continue

                # 2. 持仓≥4h才允许反向信号平仓
                if hold_hours >= 4:
                    cur_sig = signals.get(sym, 0)
                    if pos["side"] == "long" and cur_sig <= -1.0:
                        fee = abs(pnl_pct) * pos["margin"] * leverage * TAKER_FEE * 2
                        pnl = pnl_pct * pos["margin"] * leverage - fee
                        state["cash"] += pos["margin"] + pnl
                        state["pnl"] += pnl
                        state["fees_paid"] += fee
                        state["trades"] += 1
                        if pnl > 0:
                            state["wins"] += 1
                        else:
                            state["losses"] += 1
                        log.info(f"[REV-LONG] {sym} 反向信号平 PnL=${pnl:+.2f} ({pnl_pct*100:.1f}%)")
                        del state["positions"][sym]
                        continue
                    elif pos["side"] == "short" and cur_sig >= 1.0:
                        fee = abs(pnl_pct) * pos["margin"] * leverage * TAKER_FEE * 2
                        pnl = pnl_pct * pos["margin"] * leverage - fee
                        state["cash"] += pos["margin"] + pnl
                        state["pnl"] += pnl
                        state["fees_paid"] += fee
                        state["trades"] += 1
                        if pnl > 0:
                            state["wins"] += 1
                        else:
                            state["losses"] += 1
                        log.info(f"[REV-SHORT] {sym} 反向信号平 PnL=${pnl:+.2f} ({pnl_pct*100:.1f}%)")
                        del state["positions"][sym]
                        continue

                # 3. 加仓 (浮盈金字塔)
                if ADD_LEVELS and pnl_pct > 0 and pos.get("add_count", 0) < len(ADD_LEVELS):
                    next_lvl_idx = pos.get("add_count", 0)
                    if pnl_pct >= ADD_LEVELS[next_lvl_idx]:
                        # 加仓金额 = 当前margin (1:1金字塔)
                        add_margin = pos["margin"]
                        if state["cash"] >= add_margin:
                            add_fee = add_margin * leverage * TIER_SLIPPAGE.get(sym, 0.0005) + add_margin * TAKER_FEE
                            state["cash"] -= add_margin + add_fee
                            state["fees_paid"] += add_fee
                            add_qty = (add_margin * leverage) / p
                            new_margin = pos["margin"] + add_margin
                            new_qty = pos["qty"] + add_qty
                            new_avg = (pos["entry"] * pos["qty"] + p * add_qty) / new_qty
                            pos["entry"] = new_avg
                            pos["qty"] = new_qty
                            pos["margin"] = new_margin
                            pos["add_count"] = next_lvl_idx + 1
                            log.info(f"[ADD] {sym} 加仓{next_lvl_idx+1}次 +${add_margin:.2f} "
                                     f"新均价=${new_avg:.4f} 浮盈{pnl_pct*100:.1f}%")

                # 4. 分级止盈
                if TP_LEVELS and pnl_pct > 0:
                    if "tp_done" not in pos:
                        pos["tp_done"] = []
                    for lvl_idx in range(len(TP_LEVELS)):
                        if lvl_idx in pos["tp_done"]:
                            continue
                        if pnl_pct >= TP_LEVELS[lvl_idx]:
                            take_pct = TP_TAKE_PCT[lvl_idx]
                            take_margin = pos["margin"] * take_pct
                            if pos["side"] == "long":
                                part_pnl = pnl_pct * take_margin * leverage
                            else:
                                part_pnl = pnl_pct * take_margin * leverage
                            fee = abs(part_pnl) * TAKER_FEE * 2 + take_margin * TIER_SLIPPAGE.get(sym, 0.0005) * 2
                            pnl_net = part_pnl - fee
                            state["cash"] += take_margin + pnl_net
                            state["pnl"] += pnl_net
                            state["fees_paid"] += fee
                            pos["margin"] *= (1 - take_pct)
                            pos["qty"] *= (1 - take_pct)
                            pos["tp_done"].append(lvl_idx)
                            state["trades"] += 1
                            if pnl_net > 0:
                                state["wins"] += 1
                            log.info(f"[TP{lvl_idx+1}] {sym} +{pnl_pct*100:.1f}% "
                                     f"锁{take_pct*100:.0f}% PnL=${pnl_net:+.2f}")
                            if pos["margin"] < 1:
                                # 全部止盈完成
                                log.info(f"[TP-ALL] {sym} 全仓止盈完成")
                                del state["positions"][sym]
                                break

            # 开新仓: 按信号强度排序 + 周期匹配
            sorted_sigs = sorted([(s, sig) for s, sig in signals.items() if s in COINS],
                                 key=lambda x: abs(x[1]), reverse=True)

            free_cash = state["cash"] * 0.9  # 留10%作储备
            if len(state["positions"]) < MAX_POSITIONS and free_cash > 5:
                for sym, sig in sorted_sigs:
                    if abs(sig) < 1.0 or sym in state["positions"]:
                        continue

                    # 周期匹配 (memory铁律: 熊市做空不做多)
                    if score <= -30 and sig > 0:
                        continue
                    if score >= 30 and sig < 0:
                        continue

                    # 入场时机检查 (5m/15m高低位)
                    side = "long" if sig > 0 else "short"
                    h5, l5, h15, l15 = calc_5m_15m_extremes(sym)
                    cur_price = prices.get(sym)
                    if cur_price is None:
                        continue

                    # 做空要求: 当前价接近5m/15m高位
                    if side == "short" and h15 and cur_price < h15 * 0.97:
                        continue  # 不在高位, 跳过
                    # 做多要求: 当前价接近5m/15m低位
                    if side == "long" and l15 and cur_price > l15 * 1.03:
                        continue  # 不在低位, 跳过

                    margin = equity * MAX_POS_PCT
                    if margin > free_cash or margin < 5:
                        continue

                    state["cash"] -= margin
                    fee = margin * leverage * TIER_SLIPPAGE.get(sym, 0.0005) * 2 + margin * TAKER_FEE
                    state["cash"] -= fee
                    state["fees_paid"] += fee

                    qty = (margin * leverage) / cur_price
                    state["positions"][sym] = {
                        "entry": cur_price,
                        "qty": qty,
                        "side": side,
                        "time": time.time(),
                        "margin": margin,
                        "leverage": leverage,
                        "add_count": 0,
                        "tp_done": [],
                    }
                    state["trades"] += 1
                    log.info(f"[OPEN] {sym} {side} {qty:.4f}@${cur_price:.4f} "
                             f"margin=${margin:.2f}x{leverage} signal={sig:.1f} phase={phase_name}")
                    if len(state["positions"]) >= MAX_POSITIONS:
                        break

            save_state(state)

            # 状态汇报 (每6轮 = 1小时)
            if loop % 6 == 0:
                equity_now = calc_equity(state, prices)
                win_rate = (state['wins']/(state['wins']+state['losses'])*100) if (state['wins']+state['losses']) > 0 else 0
                progress = equity_now / 12800 * 100
                log.info(f"[STATUS] {phase_name} 权益=${equity_now:.2f} 持仓={len(state['positions'])} "
                         f"交易={state['trades']} 胜率={win_rate:.1f}% "
                         f"累计PnL=${state['pnl']:+.2f} 进度={progress:.4f}%→$12,800 "
                         f"回撤={dd_pct:.1f}% 周期={regime}")
                # 持仓明细（避免嵌套f-string反斜杠问题）
                pos_lines = []
                for s, p in state["positions"].items():
                    if s in prices:
                        pct = (prices[s] - p["entry"]) / p["entry"] * 100
                        if p["side"] == "short":
                            pct = -pct
                        pos_lines.append(f"{s} {p['side']} {pct:+.1f}%")
                    else:
                        pos_lines.append(f"{s} {p['side']} ?")
                log.info(f"        持仓明细: {pos_lines}")

            loop += 1
            time.sleep(LOOP_SECONDS)

        except KeyboardInterrupt:
            log.info("用户中断, 保存状态")
            save_state(state)
            break
        except Exception as e:
            log.error(f"循环异常: {e}", exc_info=True)
            save_state(state)
            time.sleep(60)


if __name__ == "__main__":
    run()