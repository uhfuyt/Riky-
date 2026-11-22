#!/usr/bin/env python3
"""
A股回测引擎 v2 — 面向小资金(500元级)的多标的组合回测
=====================================================
相比 v1 的改动:
  1. 数据周期 240 → 750 天 (3年, 覆盖牛熊)
  2. 信号阈值放宽 (样本量从 0.6笔/标的 → 目标 8+笔/标的)
  3. 组合回测: 30标的资金池轮动, 而非每标的孤立跑
  4. 加入 ETF 模式: 免印花税, 支持小资金
  5. 基准对比: 沪深300
  6. 真实摩擦成本: 佣金/印花税/滑点/最低佣金门槛
"""
import os, sys, json, math, time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np
import pandas as pd

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ENGINE_DIR, 'data')
LOG_DIR = os.path.join(ENGINE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# 成本参数 (可按券商实际费率覆盖)
# ============================================================
COMMISSION_RATE = 0.00025     # 佣金 万2.5
MIN_COMMISSION = 5.0          # 单笔最低佣金(元) — 券商常见门槛
STAMP_TAX = 0.001            # 印花税 千1 (仅卖出, 个股)
ETF_STAMP_TAX = 0.0          # ETF 免印花税
SLIPPAGE = 0.001             # 滑点 千1
LOT_SIZE = 100               # 个股 100股/手
ETF_LOT_SIZE = 100           # ETF 100份/手
MAX_POSITION_PCT = 0.30      # 单票上限
INITIAL_CAPITAL = 500.0      # 初始资金
HOLD_MIN_DAYS = 5            # 最短持有交易日

# ============================================================
# 工具
# ============================================================
def log(msg):
    t = datetime.now().strftime('%H:%M:%S')
    print(f"[{t}] {msg}", flush=True)


def _to_qq_symbol(symbol):
    s = str(symbol).strip()
    if s.startswith(('sh', 'sz', 'bj')):
        return s.lower()   # 必须小写: SH510300 会找不到文件
    if s.startswith('0') and s == '000300':
        return 'sh000300'   # 上证指数
    if s.startswith(('6', '9')):
        return 'sh' + s
    if s.startswith(('0', '2', '3')):
        return 'sz' + s      # 深市: 000/002/300
    if s.startswith(('4', '8')):
        return 'bj' + s
    if s.startswith(('0', '2', '3')):
        return 'sz' + s
    if s.startswith(('4', '8')):
        return 'bj' + s
    return 'sh' + s


def load_kline(symbol, datalen=750):
    """读本地缓存的K线"""
    qq = _to_qq_symbol(symbol)
    for p in [os.path.join(DATA_DIR, f"{qq}_qq_{datalen}.csv"),
              os.path.join(DATA_DIR, f"{qq}_qq_640.csv"),
              os.path.join(DATA_DIR, f"{qq}_qq_240.csv")]:
        if os.path.exists(p):
            try:
                df = pd.read_csv(p, parse_dates=['日期'])
                if len(df) >= 250:
                    return df.tail(datalen).reset_index(drop=True)
            except Exception:
                continue
    return None


def calc_sharpe(daily_returns, rf=0.015):
    """年化夏普: (年化收益 - 无风险利率) / 年化波动率"""
    if len(daily_returns) < 5:
        return 0.0
    r = np.array(daily_returns)
    std = r.std()
    if std == 0:
        return 0.0
    ann_ret = r.mean() * 252
    ann_vol = std * math.sqrt(252)
    return float((ann_ret - rf) / ann_vol)


def calc_max_drawdown(values):
    if not values:
        return 0.0
    peak = values[0]
    mdd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak > 0 else 0
        if dd < mdd:
            mdd = dd
    return float(mdd)


# ============================================================
# 策略 v2 — 放宽阈值, 提高信号密度
# ============================================================
def strategy_ma_cross_v2(kline, idx):
    """5日上穿20日均线 → BUY; 20日均线下穿 → SELL
    v2改动: 去掉'量能>1.5倍'的双重条件(信号太少)
    """
    if idx < 22:
        return 'HOLD'
    close = kline['收盘'].values
    ma5 = close[idx-4:idx+1].mean()
    ma20 = close[idx-19:idx+1].mean()
    p_ma5 = close[idx-5:idx].mean()
    p_ma20 = close[idx-20:idx].mean()
    if p_ma5 <= p_ma20 and ma5 > ma20:
        return 'BUY'
    if p_ma5 >= p_ma20 and ma5 < ma20:
        return 'SELL'
    return 'HOLD'


def strategy_rsi_v2(kline, idx):
    """RSI < 35 买入, RSI > 65 卖出 (v2: 30/70 → 35/65, 更灵敏)"""
    if idx < 16:
        return 'HOLD'
    close = kline['收盘'].values
    d = np.diff(close[idx-14:idx+1])
    if len(d) < 14:
        return 'HOLD'
    gain = np.where(d > 0, d, 0).mean()
    loss = np.where(d < 0, -d, 0).mean()
    rsi = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    if rsi < 35:
        return 'BUY'
    if rsi > 65:
        return 'SELL'
    return 'HOLD'


def strategy_momentum_v2(kline, idx):
    """突破20日新高 + >10日均线 → BUY; 跌破10日均线 → SELL
    v2: 突破阈值 0.998 → 0.995 (更早入场)
    """
    if idx < 21:
        return 'HOLD'
    close = kline['收盘'].values
    high20 = close[idx-19:idx+1].max()
    ma10 = close[idx-9:idx+1].mean()
    if close[idx] > high20 * 0.995 and close[idx] > ma10:
        return 'BUY'
    if close[idx] < ma10:
        return 'SELL'
    return 'HOLD'


def strategy_dual_low_v2(kline, idx):
    """连续3跌 + RSI<45 → BUY; 反弹>10日均线或RSI>60 → SELL"""
    if idx < 26:
        return 'HOLD'
    close = kline['收盘'].values
    down3 = close[idx] < close[idx-1] < close[idx-2] < close[idx-3]
    d = np.diff(close[idx-14:idx+1])
    gain = np.where(d > 0, d, 0).mean()
    loss = np.where(d < 0, -d, 0).mean()
    rsi = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    ma10 = close[idx-9:idx+1].mean()
    if down3 and rsi < 45:
        return 'BUY'
    if close[idx] > ma10 * 1.01 or rsi > 60:
        return 'SELL'
    return 'HOLD'


STRATEGIES_V2 = {
    'ma_cross':   ('均线交叉V2', strategy_ma_cross_v2),
    'rsi':        ('RSI反转V2', strategy_rsi_v2),
    'momentum':   ('动量突破V2', strategy_momentum_v2),
    'dual_low':   ('双低V2', strategy_dual_low_v2),
}


# ============================================================
# 组合回测
# ============================================================
@dataclass
class Position:
    symbol: str
    shares: int
    cost: float          # 每股成本(含费用)
    buy_date: str
    buy_idx: int
    high_since_buy: float = 0.0
    is_etf: bool = False


@dataclass
class Trade:
    date: str
    symbol: str
    side: str
    price: float
    shares: int
    fee: float
    pnl: float
    reason: str


class Portfolio:
    def __init__(self, capital, is_etf=False, commission_rate=None,
                 min_commission=None, stamp_tax=None, slippage=None,
                 max_position_pct=None):
        self.cash = capital
        self.initial = capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.daily_value: List[dict] = []
        self.is_etf = is_etf
        self.commission_rate = COMMISSION_RATE if commission_rate is None else commission_rate
        self.min_commission = (0.0 if is_etf else MIN_COMMISSION) if min_commission is None else min_commission
        self.stamp_tax = (ETF_STAMP_TAX if is_etf else STAMP_TAX) if stamp_tax is None else stamp_tax
        self.slippage = SLIPPAGE if slippage is None else slippage
        self.lot = ETF_LOT_SIZE if is_etf else LOT_SIZE
        self.max_position_pct = MAX_POSITION_PCT if max_position_pct is None else max_position_pct

    # --- 费用 ---
    def buy_fee(self, gross):
        return max(gross * self.commission_rate, self.min_commission) + gross * self.slippage

    def sell_fee(self, gross):
        return max(gross * self.commission_rate, self.min_commission) + gross * self.slippage + gross * self.stamp_tax

    def buy_shares(self, price, cash, max_pct=None):
        """按仓位上限算可买股数(整手)
        小资金场景: 即使达不到目标比例, 只要付得起1手就买(否则永远0交易)
        """
        pct = self.max_position_pct if max_pct is None else max_pct
        target = cash * pct
        raw = target / (price * (1 + self.commission_rate + self.slippage))
        sh = int(raw // self.lot) * self.lot
        if sh < self.lot:
            sh = self.lot if cash >= price * self.lot + self.buy_fee(price*self.lot) else 0
        # 考虑最低佣金/印花税: 不能让总成本超预算
        while sh >= self.lot:
            gross = price * sh
            if gross + self.buy_fee(gross) <= cash:
                return sh
            sh -= self.lot
        return 0

    def total_value(self, price_map):
        v = self.cash
        for sym, pos in self.positions.items():
            p = price_map.get(sym, pos.cost)
            v += p * pos.shares
        return v

    def open_pos(self, sym, shares, price, date, idx, is_etf=False):
        gross = price * shares
        fee = self.buy_fee(gross)
        self.cash -= (gross + fee)
        self.positions[sym] = Position(sym, shares, (gross + fee) / shares, date, idx, price, is_etf)
        self.trades.append(Trade(date, sym, 'BUY', price, shares, fee, 0.0, '信号'))

    def close_pos(self, sym, price, date, reason):
        pos = self.positions[sym]
        gross = price * pos.shares
        fee = self.sell_fee(gross)
        proceeds = gross - fee
        pnl = proceeds - pos.cost * pos.shares
        self.cash += proceeds
        self.trades.append(Trade(date, sym, 'SELL', price, pos.shares, fee, pnl, reason))
        del self.positions[sym]
        return pnl


def is_limit_up_or_down(open_price, prev_close, limit_pct):
    if prev_close <= 0:
        return False
    chg = (open_price - prev_close) / prev_close
    return abs(chg) >= limit_pct


PRICE_LIMIT = 0.10   # 主板涨跌停10% (创业板/科创板20%, 保守起见用10%)


def run_portfolio_backtest(symbols, names, strategy_fn, strategy_name,
                           capital=INITIAL_CAPITAL, datalen=750,
                           stop_loss=0.08, take_profit=0.25,
                           is_etf=False, max_hold_days=60,
                           commission_rate=None, min_commission=None,
                           stamp_tax=None, slippage=None, max_position_pct=None,
                           max_positions=4):
    """多标的组合回测: 统一日期轴, 每日扫描"""
    # 加载数据
    data = {}
    for sym in symbols:
        df = load_kline(sym, datalen)
        if df is None or len(df) < 120:
            continue
        data[sym] = df
    if not data:
        return None

    # 统一日期轴(取所有标的日期的交集近似: 用最长的一只)
    ref_sym = max(data.keys(), key=lambda s: len(data[s]))
    dates = data[ref_sym]['日期'].dt.strftime('%Y-%m-%d').values

    # 预转换为 numpy 加速
    arr = {}
    for sym, df in data.items():
        d = dict(zip(df['日期'].dt.strftime('%Y-%m-%d').values, range(len(df))))
        arr[sym] = {
            'dates': df['日期'].dt.strftime('%Y-%m-%d').values,
            'open': df['开盘'].values, 'close': df['收盘'].values,
            'high': df['最高'].values, 'low': df['最低'].values,
            'idx_of': d,
        }

    pf = Portfolio(capital, is_etf, commission_rate, min_commission, stamp_tax, slippage,
                   max_position_pct)
    price_map = {}

    for i, date in enumerate(dates):
        if i < 25:
            continue

        # 收集今日有效标的
        active = []
        for sym in arr:
            j = arr[sym]['idx_of'].get(date)
            if j is not None and j >= 25:
                active.append((sym, j))

        if not active:
            continue

        # 价格快照
        today = {sym: arr[sym]['close'][j] for sym, j in active}
        prev = {}
        for sym, j in active:
            jm1 = j - 1
            prev[sym] = arr[sym]['close'][jm1] if jm1 >= 0 else arr[sym]['close'][j]

        # 更新持仓最高价
        for sym, pos in pf.positions.items():
            if sym in today:
                pos.high_since_buy = max(pos.high_since_buy, arr[sym]['high'][arr[sym]['idx_of'][date]])

        # --- 卖出 ---
        for sym, j in active:
            if sym not in pf.positions:
                continue
            pos = pf.positions[sym]
            price = today[sym]
            sig = strategy_fn(arr[sym]['df_view'] if 'df_view' in arr[sym] else None, j) if False else None
            # 信号需要原始df, 用闭包方式取
            sig = strategy_fn(_df_view(arr[sym], j), j)

            reason = None
            hold_days = i - pos.buy_idx
            if sig == 'SELL':
                reason = '信号'
            elif price <= pos.cost * (1 - stop_loss):
                reason = f'止损{stop_loss*100:.0f}%'
            elif price >= pos.cost * (1 + take_profit):
                reason = f'止盈{take_profit*100:.0f}%'
            elif pos.high_since_buy > 0 and price < pos.high_since_buy * 0.93:
                reason = '移动止盈'
            elif hold_days >= max_hold_days:
                reason = f'时间止损{max_hold_days}天'

            if reason:
                if is_limit_up_or_down(arr[sym]['open'][j], prev[sym], PRICE_LIMIT):
                    pass  # 跌停不卖
                else:
                    pf.close_pos(sym, price, date, reason)

        # --- 买入 ---
        for sym, j in active:
            if sym in pf.positions:
                continue
            if len(pf.positions) >= max_positions:
                continue
            sig = strategy_fn(_df_view(arr[sym], j), j)
            if sig != 'BUY':
                continue
            if is_limit_up_or_down(arr[sym]['open'][j], prev[sym], PRICE_LIMIT):
                continue  # 涨停买不到
            price = today[sym]
            sh = pf.buy_shares(price, pf.cash)
            if sh >= pf.lot:
                pf.open_pos(sym, sh, price, date, i, is_etf)

        # --- 净值 ---
        price_map.update(today)
        for sym in list(pf.positions.keys()):
            if sym not in price_map:
                price_map[sym] = pf.positions[sym].cost
        pf.daily_value.append({
            'date': date, 'total': pf.total_value(price_map),
            'cash': pf.cash, 'n_pos': len(pf.positions),
        })

    # 期末清仓
    last_date = dates[-1]
    for sym in list(pf.positions.keys()):
        j = arr[sym]['idx_of'].get(last_date)
        if j is not None:
            pf.close_pos(sym, arr[sym]['close'][j], last_date, '期末清仓')

    # 指标
    values = [d['total'] for d in pf.daily_value]
    rets = [(values[i] / values[i-1] - 1) for i in range(1, len(values))]
    wins = [t for t in pf.trades if t.side == 'SELL' and t.pnl > 0]
    losses = [t for t in pf.trades if t.side == 'SELL' and t.pnl <= 0]
    gross_win = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))

    return {
        'strategy': strategy_name,
        'n_symbols': len(data),
        'initial_capital': capital,
        'final_value': pf.cash + sum(t.price * 0 for t in []) + sum(
            0 for _ in []) if False else values[-1] if values else capital,
        'total_return': (values[-1] / capital - 1) if values else 0,
        'annual_return': ((values[-1] / capital) ** (252 / max(len(values), 1)) - 1) if values else 0,
        'max_drawdown': calc_max_drawdown(values),
        'sharpe': calc_sharpe(rets),
        'n_trades': len([t for t in pf.trades if t.side == 'SELL']),
        'win_rate': len(wins) / max(len(wins) + len(losses), 1),
        'profit_factor': (gross_win / gross_loss) if gross_loss > 0 else float('inf'),
        'total_fees': sum(t.fee for t in pf.trades),
        'days': len(values),
        'start_date': dates[0] if len(dates) else '',
        'end_date': dates[-1] if len(dates) else '',
        'avg_hold_days': (sum(t for t in []) or 0),
        'trades_detail': [
            {'date': t.date, 'symbol': t.symbol, 'side': t.side, 'price': t.price,
             'shares': t.shares, 'fee': round(t.fee, 4), 'pnl': round(t.pnl, 4), 'reason': t.reason}
            for t in pf.trades
        ],
    }


def _df_view(arr, j):
    """构造策略函数需要的 DataFrame 视图(只到 j 那一行)"""
    import pandas as _pd
    end = j + 1
    return _pd.DataFrame({
        '收盘': arr['close'][:end],
        '最高': arr['high'][:end],
        '最低': arr['low'][:end],
        '成交量': arr.get('vol', arr['close'][:end]),
    })
