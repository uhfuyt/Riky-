#!/usr/bin/env python3
"""
A股 ETF 模拟盘引擎 — 30天纸上交易
====================================
策略: 动量突破 V2 (0.998突破 + 入场MA20 + 出场MA20)
标的: 16只宽基ETF
资金: 2000元
频率: 每日收盘后运行 (cron 15:10)

产出:
  state.json          — 当前持仓/现金/净值
  trades.csv          — 交易流水
  daily.csv           — 每日净值
  report_<date>.json  — 每日快照
  signal_<date>.md    — 今日信号 (推送给用户手动下单)
"""
import _pathsetup  # noqa: F401  (路径引导: 让 engine/ 与 scripts/ 互相可见)
import os, sys, json, csv
from datetime import datetime, date

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

from a_share_backtest_v2 import load_kline
from run_param_robustness import make_momentum


STATE_DIR = os.path.join(ENGINE_DIR, 'paper')
os.makedirs(STATE_DIR, exist_ok=True)

# ============ 参数 ============
CAPITAL = 2000.0
COMMISSION = 0.0005      # ETF 万0.5 (保守估计, 实盘按券商实际)
MIN_COMMISSION = 0.0    # 免五 (若券商有5元门槛, 改这里为5.0)
SLIPPAGE = 0.001
STAMP_TAX = 0.0         # ETF 免印花税
LOT = 100
MAX_PCT = 0.35          # 单只上限 35%
MAX_POS = 3             # 最多持3只
STOP_LOSS = 0.08
TAKE_PROFIT = 0.25
TRAIL = 0.93            # 移动止盈: 跌破最高价7%
MAX_HOLD = 60           # 时间止损(交易日)

ETF_POOL = [
    ('sh510300', '沪深300ETF'), ('sh510500', '中证500ETF'), ('sh512100', '中证1000ETF'),
    ('sh588000', '科创50ETF'), ('sz159915', '创业板ETF'), ('sh510880', '红利ETF'),
    ('sz159919', '沪深300ETF深'), ('sh513100', '纳指ETF'), ('sh513500', '标普500ETF'),
    ('sh512880', '证券ETF'), ('sh515180', '红利低波ETF'), ('sh516160', '新能源ETF'),
    ('sh515790', '光伏ETF'), ('sh512170', '医疗ETF'), ('sh512690', '酒ETF'),
    ('sz159941', '纳指ETF深'),
]

STRATEGY = make_momentum(0.998, 20, 20)

# ============ 路径 ============
P_STATE = os.path.join(STATE_DIR, 'state.json')
P_TRADES = os.path.join(STATE_DIR, 'trades.csv')
P_DAILY = os.path.join(STATE_DIR, 'daily.csv')
P_SIG = os.path.join(STATE_DIR, 'signal_latest.md')


def log(m):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {m}", flush=True)


def load_state():
    if os.path.exists(P_STATE):
        with open(P_STATE) as f:
            return json.load(f)
    return {
        'start_date': date.today().isoformat(),
        'initial_capital': CAPITAL,
        'cash': CAPITAL,
        'positions': {},     # code -> {shares, cost, buy_date, high, buy_idx}
        'day_index': 0,
        'last_date': None,
        'equity_curve': [],
        'total_fees': 0.0,
    }


def save_state(s):
    tmp = P_STATE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, P_STATE)   # 原子写


def append_csv(path, row, header):
    exists = os.path.exists(path)
    with open(path, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        w.writerow(row)


def buy_fee(gross):
    return max(gross * COMMISSION, MIN_COMMISSION) + gross * SLIPPAGE


def sell_fee(gross):
    return max(gross * COMMISSION, MIN_COMMISSION) + gross * SLIPPAGE + gross * STAMP_TAX


def calc_shares(price, cash):
    target = cash * MAX_PCT
    raw = target / (price * (1 + COMMISSION + SLIPPAGE))
    sh = int(raw // LOT) * LOT
    if sh < LOT:
        sh = LOT if cash >= price * LOT + buy_fee(price * LOT) else 0
    while sh >= LOT:
        gross = price * sh
        if gross + buy_fee(gross) <= cash:
            return sh
        sh -= LOT
    return 0


def fetch_latest():
    """取所有ETF最新K线 (含今日)"""
    out = {}
    for code, name in ETF_POOL:
        df = load_kline(code, 750)
        if df is None or len(df) < 60:
            log(f"  [跳过] {code} 无数据")
            continue
        out[code] = {'name': name, 'df': df}
    return out


def run():
    log("=== ETF 模拟盘运行 ===")
    st = load_state()
    data = fetch_latest()
    if not data:
        log("无数据, 退出")
        return

    # 基准日期轴
    ref = max(data.values(), key=lambda v: len(v['df']))['df']
    dates = ref['日期'].dt.strftime('%Y-%m-%d').values
    today = dates[-1]

    if st['last_date'] == today:
        log(f"今日({today})已运行过, 跳过")
        return

    # 找今天在哪些ETF有数据
    today_map = {}
    for code, v in data.items():
        df = v['df']
        idx = df.index[df['日期'].dt.strftime('%Y-%m-%d') == today]
        if len(idx):
            i = idx[0]
            today_map[code] = {
                'i': int(i),
                'close': float(df['收盘'].iloc[i]),
                'high': float(df['最高'].iloc[i]),
                'open': float(df['开盘'].iloc[i]),
                'prev': float(df['收盘'].iloc[i-1]) if i > 0 else float(df['收盘'].iloc[i]),
                'df': df,
            }

    if not today_map:
        log(f"今日({today})ETF无新数据(可能是非交易日), 退出")
        return

    log(f"交易日: {today} | 有数据ETF: {len(today_map)}只")

    # ============ 卖出 ============
    sell_actions = []
    for code, pos in list(st['positions'].items()):
        if code not in today_map:
            continue
        tm = today_map[code]
        price = tm['close']
        pos['high'] = max(pos['high'], tm['high'])
        hold = st['day_index'] - pos['buy_idx']

        reason = None
        sig = STRATEGY(tm['df'].iloc[:tm['i']+1], tm['i'])
        if sig == 'SELL':
            reason = '信号(跌破MA20)'
        elif price <= pos['cost'] * (1 - STOP_LOSS):
            reason = f'止损{STOP_LOSS*100:.0f}%'
        elif price >= pos['cost'] * (1 + TAKE_PROFIT):
            reason = f'止盈{TAKE_PROFIT*100:.0f}%'
        elif pos['high'] > 0 and price < pos['high'] * TRAIL:
            reason = '移动止盈'
        elif hold >= MAX_HOLD:
            reason = f'时间止损{MAX_HOLD}日'

        if reason:
            gross = price * pos['shares']
            fee = sell_fee(gross)
            proceeds = gross - fee
            pnl = proceeds - pos['cost'] * pos['shares']
            st['cash'] += proceeds
            st['total_fees'] += fee
            name = data[code]['name']
            sell_actions.append({
                'date': today, 'code': code, 'name': name, 'side': 'SELL',
                'price': round(price, 4), 'shares': pos['shares'],
                'amount': round(gross, 2), 'fee': round(fee, 4),
                'pnl': round(pnl, 2), 'reason': reason,
                'hold_days': hold,
            })
            append_csv(P_TRADES, sell_actions[-1],
                       ['date','code','name','side','price','shares','amount','fee','pnl','reason','hold_days'])
            del st['positions'][code]

    # ============ 买入 ============
    buy_actions = []
    candidates = []
    for code, tm in today_map.items():
        if code in st['positions']:
            continue
        sig = STRATEGY(tm['df'].iloc[:tm['i']+1], tm['i'])
        if sig == 'BUY':
            candidates.append((code, tm))
    candidates.sort(key=lambda x: -x[1]['close'])  # 同信号时按价格高者优先(流动性好)

    for code, tm in candidates:
        if len(st['positions']) >= MAX_POS:
            break
        price = tm['close']
        sh = calc_shares(price, st['cash'])
        if sh < LOT:
            continue
        gross = price * sh
        fee = buy_fee(gross)
        if gross + fee > st['cash']:
            continue
        st['cash'] -= (gross + fee)
        st['total_fees'] += fee
        st['positions'][code] = {
            'shares': sh, 'cost': price, 'buy_date': today,
            'high': tm['high'], 'buy_idx': st['day_index'],
            'name': data[code]['name'],
        }
        buy_actions.append({
            'date': today, 'code': code, 'name': data[code]['name'], 'side': 'BUY',
            'price': round(price, 4), 'shares': sh, 'amount': round(gross, 2),
            'fee': round(fee, 4), 'pnl': 0, 'reason': '突破信号',
            'hold_days': 0,
        })
        append_csv(P_TRADES, buy_actions[-1],
                   ['date','code','name','side','price','shares','amount','fee','pnl','reason','hold_days'])

    # ============ 净值 ============
    pos_value = sum(p['shares'] * today_map[c]['close']
                    for c, p in st['positions'].items() if c in today_map)
    equity = st['cash'] + pos_value
    st['day_index'] += 1
    st['last_date'] = today
    st['equity_curve'].append({
        'date': today, 'equity': round(equity, 2),
        'cash': round(st['cash'], 2), 'position_value': round(pos_value, 2),
        'n_positions': len(st['positions']), 'fees_cum': round(st['total_fees'], 2),
    })
    append_csv(P_DAILY, st['equity_curve'][-1],
               ['date','equity','cash','position_value','n_positions','fees_cum'])
    save_state(st)

    # ============ 输出 ============
    total_ret = equity / CAPITAL - 1
    log(f"净值: {equity:.2f} 元 ({total_ret*100:+.2f}%) | 持仓 {len(st['positions'])} | 累计费用 {st['total_fees']:.2f}元")

    # 基准(沪深300)
    bench = load_kline('sh000300', 750)
    bench_ret = None
    if bench is not None:
        bdates = bench['日期'].dt.strftime('%Y-%m-%d').values
        if st['start_date'] in bdates:
            i0 = list(bdates).index(st['start_date'])
            b0 = float(bench['收盘'].iloc[i0])
            b1 = float(bench['收盘'].iloc[-1])
            bench_ret = b1 / b0 - 1
            log(f"基准 沪深300: {bench_ret*100:+.2f}%")

    # 信号文件
    bench_str = f" | 沪深300 {bench_ret*100:+.2f}%" if bench_ret is not None else ""
    lines = [f"# ETF模拟盘信号 · {today}", "",
             f"净值 **{equity:.2f} 元** ({total_ret*100:+.2f}%) | 持仓 {len(st['positions'])} | "
             f"费用 {st['total_fees']:.2f}元{bench_str}", ""]
    if sell_actions:
        lines.append("## 🔻 今日卖出")
        for a in sell_actions:
            lines.append(f"- **{a['name']}({a['code']})** {a['shares']}份 @{a['price']} → "
                         f"卖 {a['amount']}元, 盈亏 {a['pnl']:+}元 · {a['reason']}")
        lines.append("")
    if buy_actions:
        lines.append("## 🔺 今日买入")
        for a in buy_actions:
            lines.append(f"- **{a['name']}({a['code']})** {a['shares']}份 @{a['price']} → "
                         f"买 {a['amount']}元 · {a['reason']}")
        lines.append("")
    if not sell_actions and not buy_actions:
        lines.append("今日无操作 (持有不动)")
        lines.append("")
    if st['positions']:
        lines.append("## 📦 当前持仓")
        for c, p in st['positions'].items():
            cur = today_map.get(c, {}).get('close', p['cost'])
            pnl = (cur - p['cost']) / p['cost'] * 100
            lines.append(f"- {p['name']}({c}) {p['shares']}份 成本{p['cost']:.3f} → 现价{cur:.3f} "
                         f"({pnl:+.1f}%) 市值{cur*p['shares']:.0f}元 买入{p['buy_date']}")
        lines.append("")
    lines.append(f"_累计交易 {len(st['equity_curve'])} 个交易日 | 初始 {CAPITAL}元_")

    with open(P_SIG, 'w') as f:
        f.write('\n'.join(lines))

    print("\n" + "\n".join(lines))


if __name__ == '__main__':
    run()
