#!/usr/bin/env python3
"""
DS-0 · SOL海龟趋势虚拟盘 (100U本金, 7x杠杆)
策略: 突破20日高点入场多, 跌破10日低点出场
风控: 6%硬止损, 2×ATR动态止损
"""
import os, json, time, requests, numpy as np
from datetime import datetime

STATE_FILE = "/home/admin/charon/bot_logs/sol_turtle_paper_state.json"
LOG_FILE = "/home/admin/charon/bot_logs/sol_turtle_paper.log"
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

INITIAL_CAPITAL = 100.0
LEVERAGE = 7
SYMBOL = "SOL/USDT:USDT"
ENTRY_PERIOD = 480  # 20天×24h
EXIT_PERIOD = 240   # 10天×24h
ATR_PERIOD = 14
STOP_LOSS_PCT = 0.06
LOOP_SECONDS = 300  # 5分钟

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        'initial_capital': INITIAL_CAPITAL,
        'capital': INITIAL_CAPITAL,  # 当前可用资金
        'position': None,  # {'side','entry_price','entry_ts','size','stop_price'}
        'total_pnl': 0.0,
        'trade_count': 0,
        'wins': 0,
        'round': 0,
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch_klines(symbol='SOLUSDT', limit=500, interval='1h'):
    r = requests.get('https://fapi.binance.com/fapi/v1/klines',
                    params={'symbol': symbol, 'interval': interval, 'limit': limit},
                    timeout=10)
    return [{'ts': k[0], 'open': float(k[1]), 'high': float(k[2]),
             'low': float(k[3]), 'close': float(k[4])} for k in r.json()]

def calc_atr(klines, period=14):
    atr = [0] * len(klines)
    for i in range(period, len(klines)):
        tr = max(klines[i]['high'] - klines[i]['low'],
                 abs(klines[i]['high'] - klines[i-1]['close']),
                 abs(klines[i]['low'] - klines[i-1]['close']))
        if i == period:
            atr[i] = tr
        else:
            atr[i] = (atr[i-1] * (period-1) + tr) / period
    return atr

def main():
    state = load_state()
    log(f"=== SOL海龟虚拟盘 启动 ===")
    log(f"本金: ${state['capital']:.2f} | 杠杆: {LEVERAGE}x | 止损: {STOP_LOSS_PCT*100}%")

    while True:
        try:
            state['round'] += 1
            klines = fetch_klines('SOLUSDT', 500, '1h')
            if len(klines) < ENTRY_PERIOD + 10:
                time.sleep(LOOP_SECONDS)
                continue

            price = klines[-1]['close']
            closes = [k['close'] for k in klines]
            highs = [k['high'] for k in klines]
            lows = [k['low'] for k in klines]
            atr_arr = calc_atr(klines, ATR_PERIOD)
            atr = atr_arr[-1]

            # 20日高/低
            hh = max(highs[-ENTRY_PERIOD:])
            ll = min(lows[-ENTRY_PERIOD:])
            # 10日高/低 (出场)
            hh10 = max(highs[-EXIT_PERIOD:])
            ll10 = min(lows[-EXIT_PERIOD:])

            pos = state['position']

            if pos:
                # 持仓中: 检查止损+出场
                if pos['side'] == 'long':
                    change = (price - pos['entry_price']) / pos['entry_price']
                    # 硬止损
                    if price <= pos['entry_price'] * (1 - STOP_LOSS_PCT):
                        pnl = state['capital'] * LEVERAGE * change
                        state['capital'] += pnl
                        state['total_pnl'] += pnl
                        state['trade_count'] += 1
                        if pnl > 0: state['wins'] += 1
                        log(f"[止损LONG] {price:.4f} | entry={pos['entry_price']:.4f} | pnl=${pnl:+.2f} | 余额=${state['capital']:.2f}")
                        state['position'] = None
                    # 跌破10日低出场
                    elif price < ll10:
                        pnl = state['capital'] * LEVERAGE * change
                        state['capital'] += pnl
                        state['total_pnl'] += pnl
                        state['trade_count'] += 1
                        if pnl > 0: state['wins'] += 1
                        log(f"[出场LONG] {price:.4f} (10日低) | pnl=${pnl:+.2f} | 余额=${state['capital']:.2f}")
                        state['position'] = None
                    # ATR移动止损
                    elif price < pos['entry_price'] - 2*atr:
                        pnl = state['capital'] * LEVERAGE * change
                        state['capital'] += pnl
                        state['total_pnl'] += pnl
                        state['trade_count'] += 1
                        if pnl > 0: state['wins'] += 1
                        log(f"[ATR止损LONG] {price:.4f} (ATR={atr:.2f}) | pnl=${pnl:+.2f}")
                        state['position'] = None
                else:  # short
                    change = (pos['entry_price'] - price) / pos['entry_price']
                    if price >= pos['entry_price'] * (1 + STOP_LOSS_PCT):
                        pnl = state['capital'] * LEVERAGE * change
                        state['capital'] += pnl
                        state['total_pnl'] += pnl
                        state['trade_count'] += 1
                        if pnl > 0: state['wins'] += 1
                        log(f"[止损SHORT] {price:.4f} | pnl=${pnl:+.2f}")
                        state['position'] = None
                    elif price > hh10:
                        pnl = state['capital'] * LEVERAGE * change
                        state['capital'] += pnl
                        state['total_pnl'] += pnl
                        state['trade_count'] += 1
                        if pnl > 0: state['wins'] += 1
                        log(f"[出场SHORT] {price:.4f} (10日高) | pnl=${pnl:+.2f}")
                        state['position'] = None

            if state['position'] is None:
                # 入场信号
                if price > hh and atr > 0:
                    state['position'] = {
                        'side':'long',
                        'entry_price': price,
                        'entry_ts': int(time.time()),
                        'size': (state['capital'] * LEVERAGE) / price,
                        'stop_price': price * (1 - STOP_LOSS_PCT),
                    }
                    log(f"[开多] {price:.4f} | 20日高突破 {hh:.4f} | ATR={atr:.2f}")
                elif price < ll and atr > 0:
                    state['position'] = {
                        'side':'short',
                        'entry_price': price,
                        'entry_ts': int(time.time()),
                        'size': (state['capital'] * LEVERAGE) / price,
                        'stop_price': price * (1 + STOP_LOSS_PCT),
                    }
                    log(f"[开空] {price:.4f} | 20日低跌破 {ll:.4f} | ATR={atr:.2f}")

            # 每6轮状态
            if state['round'] % 6 == 0:
                pos = state['position']
                pos_str = f"{pos['side']}@{pos['entry_price']:.2f}" if pos else "空仓"
                wr = (state['wins']/state['trade_count']*100) if state['trade_count']>0 else 0
                log(f"[状态] #{state['round']} price={price:.2f} | {pos_str} | "
                    f"本金${state['capital']:.2f} | PnL=${state['total_pnl']:+.2f} | "
                    f"交易{state['trade_count']}笔 胜率{wr:.0f}%")

            save_state(state)

        except Exception as e:
            log(f"[错误] {e}")
            import traceback
            traceback.print_exc()

        time.sleep(LOOP_SECONDS)

if __name__ == '__main__':
    main()