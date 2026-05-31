#!/usr/bin/env python3
"""
主权AI虚拟盘 · 全托管GPT驱动 + Harness知识库
==============================================
资金: $500
全权决策: GPT-5.5 (不请示用户)
知识库: 跨session积累经验，死路回避，探索覆盖率

整合了 quant-explorer/harness.py:
- 防御性校验（参数/逻辑/枚举值）
- 指纹去重 + 相似度检测
- 探索结果知识库持久化
- 死路记忆注入
- 覆盖率地图
"""
import ccxt, json, time, os, sys, requests, numpy as np, hashlib
from datetime import datetime
from pathlib import Path

# ── 基础配置 ──────────────────────────────────────────────
INITIAL_CASH = 500.0
LEVERAGE = 3
PROBE_SIZE = 0.01   # 探路 ~$5保证金
FULL_SIZE  = 0.25   # 全量 $125
SCALE_UP_DELAY = 7200   # 2小时
SCALE_PROFIT_THRESHOLD = 0.005  # 盈利0.5%+才加仓
TAKER_FEE = 0.0004
STATE_FILE = os.path.expanduser('~/charon/bot_logs/sovereign_gpt_state.json')
LOG_FILE = os.path.expanduser('~/charon/bot_logs/sovereign_gpt.log')
REPORT_FILE = os.path.expanduser('~/charon/bot_logs/sovereign_gpt_report.json')

# ── 宏观风险暂停开关 ──────────────────────────────────────
# 当检测到以下关键词时自动进入暂停模式，不开新仓
MACRO_RISK_KEYWORDS = [
    'tariff', 'tariffs', '关税',
    'Trump', 'trump', '特朗普',
    'trade war', '贸易战',
    'recession', '衰退',
    'Fed rate', 'rate hike', 'rate cut', '加息', '降息',
    'ban', 'restrict', '限制',
    'war', 'conflict', '战争', '冲突',
    'default', '违约',
    'crisis', '危机',
]

# ── 宏观事件数据（全局）──────────────────────────────────
macro_event_active = False       # 是否触发宏观暂停
macro_event_reason = ''          # 触发原因
macro_last_check = 0             # 上次检查时间（秒级时间戳）

def check_macro_events() -> tuple[bool, str]:
    """
    检测当前是否有高危宏观事件（通过关键词简单判断）。
    后续可替换为真实新闻API或Twitter API。
    返回 (is_risky, reason)
    """
    global macro_event_active, macro_event_reason, macro_last_check

    # 每30分钟最多检查一次
    if time.time() - macro_last_check < 1800:
        return macro_event_active, macro_event_reason
    macro_last_check = time.time()

    # 模拟事件检测（这里可接入真实新闻API或Twitter流）
    # 实际生产中应替换为真实数据源
    try:
        # Binance八卦币安币安币安事件（简单模拟，可接入CoinGecko news）
        # 此处通过简单时间窗口判断：北京时间深夜+大幅波动=高危
        now = datetime.now()
        hour = now.hour
        # 已知高风险时段：非农/FOMC公布前后（utc+8，简化判断）
        risky_hours = list(range(20, 24)) + list(range(0, 4))  # 20-04 UTC+8 = 高波动窗口
        if hour in risky_hours:
            # 通过当前价格波动判断市场状态
            try:
                btc = get_price('BTC/USDT')
                if btc:
                    k = get_klines('BTC/USDT', '1h', 6)
                    if k and len(k['closes']) >= 6:
                        vols = k['volumes']
                        closes = k['closes']
                        if len(vols) >= 6 and vols[-1] > np.mean(vols[-6:-1]) * 1.5:
                            macro_event_active = True
                            macro_event_reason = f'高波动窗口({hour}:00) + 成交量异常'
                            return True, macro_event_reason
            except:
                pass
    except:
        pass

    macro_event_active = False
    macro_event_reason = ''
    return False, ''

def get_top_traders_ratio(symbol: str) -> dict:
    """获取顶级交易员多空比（Binance Futures）"""
    try:
        s = symbol.replace('/', '')
        r = requests.get(
            f'https://fapi.binance.com/futures/data/topLongShortPositionRatio?symbol={s}&period=1h&limit=1',
            timeout=5)
        d = r.json()[-1]
        long_ratio = float(d.get('longPositionRatio', 0.5))
        short_ratio = float(d.get('shortPositionRatio', 0.5))
        return {
            'long_top_pct': int(long_ratio * 100),
            'short_top_pct': int(short_ratio * 100),
            'top_long_short_ratio': long_ratio / short_ratio if short_ratio > 0 else 1.0,
        }
    except:
        return {'long_top_pct': 50, 'short_top_pct': 50, 'top_long_short_ratio': 1.0}

def get_volume_momentum(symbol: str) -> float:
    """成交量动量：当前成交量 / 前6期均值，>1.5=放量"""
    try:
        k = get_klines(symbol, '1h', 10)
        if k and len(k['volumes']) >= 7:
            vols = k['volumes']
            current = vols[-1]
            avg = np.mean(vols[-7:-1])
            return current / avg if avg > 0 else 1.0
    except:
        pass
    return 1.0

def get_bollinger_bands(closes, period=20):
    """返回 (上轨, 中轨, 下轨)"""
    if len(closes) < period:
        return None, None, None
    recent = closes[-period:]
    mid = np.mean(recent)
    std = np.std(recent)
    return mid + 2 * std, mid, mid - 2 * std

def calc_macd(closes, fast=12, slow=26, signal=9):
    """返回 MACD柱（快线-慢线）"""
    if len(closes) < slow + signal:
        return 0.0
    import pandas as pd
    s = pd.Series(closes)
    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    return float(macd_hist.iloc[-1])

def get_smart_money_score(symbol: str) -> float:
    """聪明钱综合得分：顶级交易员方向 + 成交量动量"""
    top = get_top_traders_ratio(symbol)
    top_ratio = top['top_long_short_ratio']  # >1 多头占优，<1 空头占优
    vol_mom = get_volume_momentum(symbol)    # >1 放量
    # 成交量放大 + 顶级多头占比高 → 得分接近1（强多头）
    # 成交量放大 + 顶级空头占比高 → 得分接近0（强空头）
    vol_score = min(vol_mom / 2.0, 1.0)  # 归一化，>2x=满分
    ls_score = top_ratio / (top_ratio + 1.0)  # 0~1，>1多头，<1空头
    return min(max(ls_score * 0.6 + vol_score * 0.4, 0.0), 1.0)

def get_binance_hot_coins() -> list:
    """获取币安热点币（成交量排名前5的合约币种）"""
    try:
        r = requests.get('https://fapi.binance.com/fapi/v1/ticker/24h', timeout=5)
        all_tickers = r.json()
        # 按成交额排序，取前10
        sorted_tickers = sorted(all_tickers, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
        hot = []
        for t in sorted_tickers[:10]:
            sym = t.get('symbol', '')
            # 过滤合约币种（以USDT结尾）
            if sym.endswith('USDT') and 'USDC' not in sym:
                hot.append({
                    'symbol': sym,
                    'price': float(t.get('lastPrice', 0)),
                    'quote_vol': float(t.get('quoteVolume', 0)),
                    'price_change': float(t.get('priceChangePercent', 0)),
                })
        return hot
    except:
        return []

def daily_report(data, state) -> dict:
    """生成日报"""
    positions_summary = []
    for pos in state.get('positions', []):
        sym = pos['symbol']
        current_price = data.get(sym, {}).get('price', 0)
        positions_summary.append({
            'symbol': sym,
            'side': pos['side'],
            'entry': pos['entry'],
            'current': current_price,
            'unrealized_pnl': calc_pnl(pos['entry'], current_price, pos['side'], LEVERAGE, pos['margin']),
            'stop': pos['stop'],
            'tp': pos['tp'],
            'margin': pos['margin'],
        })
    report = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'cash': state['cash'],
        'equity': state['cash'] + sum(p['margin'] for p in positions_summary),
        'trades': state['trades'],
        'total_pnl': state['pnl'],
        'total_fees': state['fees'],
        'positions': positions_summary,
        'macro_pause': macro_event_active,
        'macro_reason': macro_event_reason,
        'smart_money': {
            'BTC_top_ratio': get_top_traders_ratio('BTC/USDT'),
            'SOL_top_ratio': get_top_traders_ratio('SOL/USDT'),
            'BTC_vol_momentum': get_volume_momentum('BTC/USDT'),
            'SOL_vol_momentum': get_volume_momentum('SOL/USDT'),
        },
    }
    try:
        with open(REPORT_FILE, 'w') as f:
            json.dump(report, f, indent=2)
        log(f"📋 日报已写入 {REPORT_FILE}")
    except:
        pass
    return report


# ── 动态杠杆配置 ─────────────────────────────────────────
# 信心等级 → 最大杠杆
# 基于：RSI偏离50的程度 + FnG偏离50的程度 + 趋势确认程度
CONFIDENCE_LEVERAGE_MAP = [
    # (信心阈值, 最大杠杆, 说明)
    (0.0,  1,  "无信号/矛盾"),
    (0.3,  2,  "弱信号"),
    (0.6,  3,  "普通信号"),
    (0.8,  5,  "强信号"),
    (0.95, 10, "极强信号"),
]

# ── 移动止损配置 ──────────────────────────────────────────
TRAILING_TRIGGERS = [
    # (盈利%触发, 新止损距 Entry 的 %, 说明)
    (0.02, 0.005, "盈利2%→保本止损"),
    (0.05, 0.015, "盈利5%→止损上移1.5%"),
    (0.10, 0.030, "盈利10%→止损上移3%"),
    (0.20, 0.050, "盈利20%→止损上移5%"),
]

# ── GPT超时重试配置 ───────────────────────────────────────
GPT_TIMEOUT = 90     # 90秒超时（10个币种prompt更大）
GPT_MAX_RETRIES = 3  # 最多3次重试

# ── 网格配置 ──────────────────────────────────────────────
GRID_LEVELS = 3          # 网格层数
GRID_INTERVAL_PCT = 0.5   # 每层间距（%），0.5% = 网格间距
GRID_MARGIN_PCT = 0.20    # 每层保证金占比（20% × 3 = 60%总仓位）

# ── 知识库配置 ────────────────────────────────────────────
KB_DIR = Path('/home/admin/charon/bot_logs/quant_kb')
KB_DIR.mkdir(exist_ok=True)
INDEX_FILE = KB_DIR / 'strategy_index.json'
DEAD_ENDS_FILE = KB_DIR / 'dead_ends.json'
TOP_FILE = KB_DIR / 'top_strategies.json'
EXPLORE_COUNT_FILE = KB_DIR / 'explore_count.json'

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# ── 日志 ──────────────────────────────────────────────────
def log(msg):
    t = datetime.now().strftime('%m-%d %H:%M')
    line = f'[{t}] {msg}'
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')
    print(line, flush=True)

# ── API配置 ──────────────────────────────────────────────
GPT_KEY = 'sk-BLzmIrUAOsZOpwUPf1IuILbxnyaq0bitkntL3aHiEIO29mtL'
GPT_URL = 'https://vip.aipro.love/v1/chat/completions'

# 主API模型队列（哈基米第三方模型，按优先级排队）
# 第一个失败自动换下一个，全部失败才轮到备用API
GPT_MODELS = ['gpt-5.5', 'gpt-5.4', 'gpt-5.2', 'gemini-3-flash', 'gemini-3.1-flash']

# 备用API（1314mc兜底）
GPT_KEY_BAK = 'sk-5fZEPvB59BBqWDLU0JSK9heLCpIbCfXXbNCSjcbEyk1wlkVf'
GPT_URL_BAK = 'http://www.1314mc.net:3333/v1/chat/completions'
GPT_MODEL_BAK = 'claude-opus-4-6/4-7'

# ── 交易所 ────────────────────────────────────────────────
ex = ccxt.binance({'enableRateLimit': True})
ex.load_markets()

# ── 状态 ──────────────────────────────────────────────────
state = {'cash': INITIAL_CASH, 'positions': [], 'trades': 0, 'pnl': 0.0, 'fees': 0.0, 'equity_curve': [], 'session_start': time.time()}
if os.path.exists(STATE_FILE):
    try:
        old = json.load(open(STATE_FILE))
        # 兼容旧单持仓格式
        if 'positions' not in old and 'position' in old and old['position']:
            old['positions'] = [old['position']]
            del old['position']
        state = old
    except: pass

# ═══════════════════════════════════════════════════════════
# HARNESS 层
# ═══════════════════════════════════════════════════════════

def config_fingerprint(params: dict) -> str:
    """给策略配置算MD5指纹，用于去重"""
    canonical = json.dumps(params, sort_keys=True)
    return hashlib.md5(canonical.encode()).hexdigest()


def validate_params(params: dict) -> tuple[bool, str]:
    """防御性校验：宽进严出"""
    for field in ['symbol', 'side', 'leverage']:
        if field not in params or params[field] is None:
            return False, f"缺少参数: {field}"
    if params['side'] not in ['long', 'short']:
        return False, f"side必须是long/short，实际: {params['side']}"
    if params['leverage'] not in [1, 2, 3, 5, 10]:
        return False, f"leverage必须是1/2/3/5/10，实际: {params['leverage']}"
    return True, "OK"


def check_duplicate(fingerprint: str) -> tuple[bool, dict]:
    """指纹去重"""
    try:
        index = json.load(open(INDEX_FILE)) if INDEX_FILE.exists() else {}
    except: index = {}
    if fingerprint in index:
        return True, index[fingerprint]
    return False, {}


def jaccard_similarity(a: list, b: list) -> float:
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b: return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def check_similarity(params: dict) -> tuple[float, dict]:
    """相似度检测，>0.9警告"""
    current_factors = [params.get('side'), params.get('symbol'), f"lev{params.get('leverage')}"]
    try:
        top = json.load(open(TOP_FILE)) if TOP_FILE.exists() else []
    except: top = []
    for old in top[:10]:
        sim = jaccard_similarity(current_factors, old.get('factors', []))
        if sim > 0.9:
            return sim, old
    return 0.0, {}


def load_dead_ends() -> list:
    """加载死路记录"""
    try:
        return json.load(open(DEAD_ENDS_FILE)) if DEAD_ENDS_FILE.exists() else []
    except: return []


def get_cross_session_knowledge() -> dict:
    """读取跨session知识，供GPT prompt注入"""
    result = {
        'best_strategies': [],
        'dead_ends': [],
        'total_explored': 0,
        'exploration_map': {},
    }
    try:
        index = json.load(open(INDEX_FILE)) if INDEX_FILE.exists() else {}
        result['total_explored'] = len(index)
        result['exploration_map'] = {
            'total': len(index),
        }
    except: pass
    try:
        top = json.load(open(TOP_FILE)) if TOP_FILE.exists() else []
        result['best_strategies'] = top[:5]
    except: pass
    result['dead_ends'] = load_dead_ends()[-10:]
    return result


def update_knowledge(params: dict, result: dict):
    """探索完成后更新知识库"""
    score = result.get('pnl_pct', 0)
    
    # 索引更新
    fp = config_fingerprint(params)
    try:
        index = json.load(open(INDEX_FILE)) if INDEX_FILE.exists() else {}
    except: index = {}
    index[fp] = {
        'score': score,
        'params': params,
        'timestamp': datetime.now().isoformat(),
        'nav': result.get('nav', 0)
    }
    with open(INDEX_FILE, 'w') as f:
        json.dump(index, f, indent=2)
    
    # 死路记录
    if score < -5:
        try:
            dead_ends = json.load(open(DEAD_ENDS_FILE)) if DEAD_ENDS_FILE.exists() else []
        except: dead_ends = []
        factors = [params.get('side'), params.get('symbol'), f"lev{params.get('leverage')}"]
        dead_ends.append({
            'factors': factors,
            'score': score,
            'params': params,
            'timestamp': datetime.now().isoformat()
        })
        dead_ends = dead_ends[-50:]
        with open(DEAD_ENDS_FILE, 'w') as f:
            json.dump(dead_ends, f, indent=2)
        log(f"💀 死路记录: {factors} 评分{score:.2f}")
    
    # Top-N 策略
    try:
        top = json.load(open(TOP_FILE)) if TOP_FILE.exists() else []
    except: top = []
    factors = [params.get('side'), params.get('symbol'), f"lev{params.get('leverage')}"]
    top.append({'factors': factors, 'score': score, 'params': params, 'timestamp': datetime.now().isoformat()})
    top = sorted(top, key=lambda x: x['score'], reverse=True)[:20]
    with open(TOP_FILE, 'w') as f:
        json.dump(top, f, indent=2)
    
    # 探索次数
    try:
        cnt = json.load(open(EXPLORE_COUNT_FILE)) if EXPLORE_COUNT_FILE.exists() else {}
    except: cnt = {}
    cnt['total'] = cnt.get('total', 0) + 1
    with open(EXPLORE_COUNT_FILE, 'w') as f:
        json.dump(cnt, f)


def get_exploration_map() -> str:
    """生成探索覆盖率报告字符串"""
    try:
        index = json.load(open(INDEX_FILE)) if INDEX_FILE.exists() else {}
    except: index = {}
    
    symbols = {}
    sides = {}
    levers = {}
    
    for fp, entry in index.items():
        p = entry.get('params', {})
        sym = p.get('symbol', 'unknown')
        side = p.get('side', 'unknown')
        lev = str(p.get('leverage', 'unknown'))
        symbols[sym] = symbols.get(sym, 0) + 1
        sides[side] = sides.get(side, 0) + 1
        levers[lev] = levers.get(lev, 0) + 1
    
    total = len(index) or 1
    lines = [f"探索总次数: {total}"]
    lines.append(f"BTC/ETH/SOL覆盖: BTC={'✅' if 'BTC/USDT' in symbols else '❌'} ETH={'✅' if 'ETH/USDT' in symbols else '❌'} SOL={'✅' if 'SOL/USDT' in symbols else '❌'}")
    lines.append(f"方向分布: 多={sides.get('long',0)} 空={sides.get('short',0)}")
    lines.append(f"杠杆分布: 3x={levers.get('3',0)} 5x={levers.get('5',0)}")
    
    return " | ".join(lines)


# ═══════════════════════════════════════════════════════════
# 数据采集
# ═══════════════════════════════════════════════════════════

def get_price(symbol):
    try:
        t = ex.fetch_ticker(symbol)
        return float(t['last'])
    except: return None


def get_klines(symbol, tf='1h', limit=30):
    try:
        k = ex.fetch_ohlcv(symbol, tf, limit=limit)
        return {
            'closes': [float(x[4]) for x in k],
            'highs': [float(x[2]) for x in k],
            'lows': [float(x[3]) for x in k],
            'volumes': [float(x[5]) for x in k],
        }
    except: return None


def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return 50.0
    deltas = np.diff(closes)
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    avg_g = np.mean(gains[-period:])
    avg_l = np.mean(losses[-period:])
    if avg_l < 1e-10: return 100.0
    return 100.0 - (100.0 / (1.0 + avg_g / avg_l))


def get_funding(symbol):
    try:
        s = symbol.replace('/', '')
        r = requests.get(f'https://fapi.binance.com/fapi/v1/premiumIndex?symbol={s}', timeout=5)
        return float(r.json().get('lastFundingRate', 0)) * 100
    except: return 0.0


def get_longshort(symbol):
    try:
        r = requests.get(
            f'https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=1',
            timeout=5)
        d = r.json()[-1]
        return {
            'ratio': float(d['longShortRatio']),
            'long_pct': int(float(d['longAccount']) * 100),
            'short_pct': int(float(d['shortAccount']) * 100)
        }
    except: return {'ratio': 1.0, 'long_pct': 50, 'short_pct': 50}


def get_fng():
    try:
        r = requests.get('https://api.alternative.me/fng/?limit=1', timeout=5)
        d = r.json()['data'][0]
        return int(d['value']), d['value_classification']
    except: return 50, 'Neutral'


def collect_data(symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ETC/USDT', 'BNB/USDT', 'AVAX/USDT', 'MATIC/USDT', 'LINK/USDT', 'ADA/USDT', 'DOGE/USDT']):
    data = {}
    for sym in symbols:
        k1h = get_klines(sym, '1h', 30)
        k4h = get_klines(sym, '4h', 30)
        k1d = get_klines(sym, '1d', 14)
        price = get_price(sym)
        
        closes_1h = k1h['closes'] if k1h else []
        closes_1d = k1d['closes'] if k1d else []
        
        data[sym] = {
            'price': price,
            'rsi_1h': calc_rsi(closes_1h) if closes_1h else 50,
            'rsi_4h': calc_rsi(k4h['closes']) if k4h else 50,
            'rsi_1d': calc_rsi(closes_1d) if closes_1d else 50,
            'high_20_1h': max(k1h['highs'][-20:]) if k1h and len(k1h['highs']) >= 20 else price,
            'low_20_1h': min(k1h['lows'][-20:]) if k1h and len(k1h['lows']) >= 20 else price,
            'high_20_4h': max(k4h['highs'][-20:]) if k4h and len(k4h['highs']) >= 20 else price,
            'low_20_4h': min(k4h['lows'][-20:]) if k4h and len(k4h['lows']) >= 20 else price,
            'funding': get_funding(sym),
        }
        
        s = sym.replace('/', '')
        ls = get_longshort(s)
        data[sym]['ls_ratio'] = ls['ratio']
        data[sym]['ls_long_pct'] = ls['long_pct']
        data[sym]['ls_short_pct'] = ls['short_pct']

        # 聪明钱数据
        top = get_top_traders_ratio(s)
        data[sym]['top_long_pct'] = top['long_top_pct']
        data[sym]['top_short_pct'] = top['short_top_pct']
        data[sym]['top_ratio'] = top['top_long_short_ratio']
        data[sym]['vol_momentum'] = get_volume_momentum(sym)

        # 补充指标：布林带 + MACD（用于RSI失效时的辅助信号）
        closes_1h = k1h['closes'] if k1h else []
        if closes_1h:
            bb_up, bb_mid, bb_low = get_bollinger_bands(closes_1h)
            data[sym]['bb_up'] = bb_up
            data[sym]['bb_mid'] = bb_mid
            data[sym]['bb_low'] = bb_low
            data[sym]['macd_hist'] = calc_macd(closes_1h)

    # 全局热点币
    data['hot_coins'] = get_binance_hot_coins()[:5]

    fng_val, fng_class = get_fng()
    data['fng'] = {'value': fng_val, 'class': fng_class}

    # 宏观事件检查（每30分钟）
    is_macro_risky, macro_reason = check_macro_events()
    data['macro_risky'] = is_macro_risky
    data['macro_reason'] = macro_reason

    return data


# ═══════════════════════════════════════════════════════════
# GPT决策（增强版：注入知识库上下文）
# ═══════════════════════════════════════════════════════════

def gpt_decide(data, position=None):
    pos_ctx = ''
    if position:
        elapsed = (time.time() - position.get('open_time', time.time())) / 3600
        pos_ctx = f"""
【当前持仓】
  币种: {position['symbol']}
  方向: {position['side']}
  入场价: ${position['entry']:.4f}
  当前价: ${data.get(position['symbol'], {}).get('price', 0):.4f}
  已持仓: {elapsed:.1f}小时
  浮盈: ${position.get('unrealized_pnl', 0):.2f}
  止损: ${position.get('stop', 0):.4f}
  止盈: ${position.get('tp', 0):.4f}
"""

    # 注入知识库上下文
    kb = get_cross_session_knowledge()
    dead_end_txt = ''
    if kb.get('dead_ends'):
        dead_factors = [d['factors'] for d in kb['dead_ends'][-5:]]
        dead_end_txt = f"\n【死路回避】（以下方向评分<5%，别再试）:\n"
        for df in dead_factors:
            dead_end_txt += f"  - {df}\n"
    
    best_txt = ''
    if kb.get('best_strategies'):
        best_txt = f"\n【历史最优】(评分最高):\n"
        for b in kb['best_strategies'][:3]:
            best_txt += f"  - {b['factors']} 评分={b['score']:.1f}\n"
    
    explore_txt = get_exploration_map()

    # 构建10个币种的数据块（精简版：省token）
    coin_data_block = ""
    symbol_list = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ETC/USDT', 'BNB/USDT', 'AVAX/USDT', 'MATIC/USDT', 'LINK/USDT', 'ADA/USDT', 'DOGE/USDT']
    for sym in symbol_list:
        d = data.get(sym, {})
        price = d.get('price', 0)
        rsi_1d = d.get('rsi_1d', 50)
        funding = d.get('funding', 0)
        ls_ratio = d.get('ls_ratio', 1.0)
        top_ratio = d.get('top_ratio', 1.0)
        top_long_pct = d.get('top_long_pct', 50)
        top_short_pct = d.get('top_short_pct', 50)
        vol_mom = d.get('vol_momentum', 1.0)
        bb_up = d.get('bb_up', 0)
        bb_low = d.get('bb_low', 0)
        macd_hist = d.get('macd_hist', 0)
        name = sym.split('/')[0]
        if price > 0:
            coin_data_block += f"{name}:${price:.4f} RSI_1d={rsi_1d:.0f} funding={funding:+.2f}% ls={ls_ratio:.2f} 顶级多={top_long_pct}%空={top_short_pct}% 放量={vol_mom:.1f}x MACD={macd_hist:+.4f}\n"

    # 热点币（币安成交量前5）
    hot_coins = data.get('hot_coins', [])
    hot_block = ""
    if hot_coins:
        hot_block = "【币安热点币】（成交额前5）\n"
        for h in hot_coins[:5]:
            hot_block += f"  {h['symbol']}: ${h['price']:.4f} 涨跌{h['price_change']:+.1f}% 成交额${h['quote_vol']/1e6:.1f}M\n"

    # 宏观风险状态
    macro_status = f"⚠️ 宏观暂停 | {data.get('macro_reason','')}" if data.get('macro_risky') else "✅ 宏观正常"


    prompt = f"""你是专业加密货币交易员。以下是实时市场数据：

【知识库上下文】（来自历史探索的经验）
{dead_end_txt if dead_end_txt else "【死路】无记录"}
{best_txt if best_txt else "【最优】暂无历史数据"}
【探索覆盖率】{explore_txt}

【市场情绪】
恐惧贪婪: {data['fng']['value']}/100 ({data['fng']['class']})

【宏观状态】{macro_status}
（如果宏观暂停，不开新仓，只处理现有持仓的止损/止盈）

{hot_block if hot_block else ""}
【各币种数据】（从10个中选最优机会）
{coin_data_block}
{pos_ctx}
【资金】
现金: ${state['cash']:.2f} | 已交易: {state['trades']}笔 | 总PnL: ${state['pnl']:.2f}

你的任务是决定现在做什么。返回JSON（不要其他内容）：
{{"action": "long|short|close|hold", "symbol": "以上任意币种", "entry_zone": "具体价格区间", "stop_loss": 价格, "take_profit": 价格, "leverage": 数字, "confidence": 0-1之间的信心指数, "reason": "一句话原因"}}

规则：
- 有持仓且价格到止损或止盈 → close
- 有持仓但方向仍然有效 → hold
- 无持仓且有明确机会 → long或short
- 无明确机会 → hold
- 方向冲突时(funding和RSI矛盾) → hold
- 多空比>2.5且和你的方向一致 → 否决
- 避免重复试已知的死路方向
- 宏观暂停时：只平仓，不开新仓
- RSI=50中性时：用布林带+MACD+聪明钱顶级多空比综合判断（优先看MACD柱方向和顶级交易员多空比）
"""
    # ── 主API（哈基米）── 模型队列接力
    for model in GPT_MODELS:
        for attempt in range(GPT_MAX_RETRIES):
            try:
                r = requests.post(GPT_URL, json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 300,
                    'temperature': 0.2
                }, headers={
                    'Authorization': f'Bearer {GPT_KEY}',
                    'Content-Type': 'application/json'
                }, timeout=GPT_TIMEOUT)

                if r.status_code == 200:
                    content = r.json()['choices'][0]['message']['content']
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        return json.loads(content[start:end])
                reason = f'HTTP {r.status_code}'
            except Exception as e:
                reason = f'API error: {e}'

            if attempt < GPT_MAX_RETRIES - 1:
                wait = 2 ** attempt * 3
                log(f"模型{model}失败({attempt+1}/{GPT_MAX_RETRIES})，{wait}秒后重试: {reason}")
                time.sleep(wait)

        log(f"模型{model}全部重试耗尽，切换下一个模型...")

    # ── 备用API（1314mc）── 兜底
    log("哈基米模型队列耗尽，切换1314mc备用...")
    try:
        r = requests.post(GPT_URL_BAK, json={
            'model': GPT_MODEL_BAK,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 300,
            'temperature': 0.2
        }, headers={
            'Authorization': f'Bearer {GPT_KEY_BAK}',
            'Content-Type': 'application/json'
        }, timeout=90)

        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                log("1314mc备用成功")
                return json.loads(content[start:end])
        reason = f'HTTP {r.status_code}'
    except Exception as e:
        reason = f'备用API error: {e}'

    return {'action': 'hold', 'reason': f'所有模型/接口失败: {reason}'}


# ═══════════════════════════════════════════════════════════
# 安全校验
# ═══════════════════════════════════════════════════════════

def safe_position(entry, stop, tp, leverage):
    sl_dist = abs(entry - stop) / entry
    liq_dist = 0.10 / leverage
    if liq_dist < sl_dist * 1.5:
        return False, f'强平距不足(需>{sl_dist*1.5*100:.1f}%)'
    if sl_dist > 0.08:
        return False, f'止损太宽({sl_dist*100:.1f}%)'
    return True, 'OK'


# ═══════════════════════════════════════════════════════════
# 动态杠杆（量化机构核心）
# ═══════════════════════════════════════════════════════════

def calc_confidence(data, symbol) -> float:
    """
    计算信号信心指数 [0, 1]
    基于：RSI偏离50 + FnG偏离50 + 趋势强度
    """
    sym_data = data.get(symbol, {})
    rsi = sym_data.get('rsi_1h', 50)
    rsi_1d = sym_data.get('rsi_1d', 50)
    
    # RSI偏离50的程度（越大偏离 → 越强信号）
    rsi_dev = abs(rsi - 50) / 50  # 0~1
    rsi_1d_dev = abs(rsi_1d - 50) / 50
    
    # FnG偏离50
    fng = data.get('fng', {}).get('value', 50)
    fng_dev = abs(fng - 50) / 50  # 0~1
    
    # 多空比倾向
    ls_ratio = sym_data.get('ls_ratio', 1.0)
    ls_dev = abs(ls_ratio - 1.0)  # 偏离1.0的程度
    
    # 趋势确认：价格在20日区间内的位置
    price = sym_data.get('price', 0)
    high_20 = sym_data.get('high_20_1h', price)
    low_20 = sym_data.get('low_20_1h', price)
    range_pos = (price - low_20) / (high_20 - low_20) if high_20 > low_20 else 0.5
    
    # 综合信心：加权平均
    conf = (
        rsi_dev * 0.25 +
        rsi_1d_dev * 0.25 +
        fng_dev * 0.20 +
        min(ls_dev, 1.0) * 0.15 +
        (0.5 - abs(range_pos - 0.5)) * 0.15  # 偏离区间中点越远 → 越强
    )
    
    return min(1.0, max(0.0, conf))


def dynamic_leverage(data, symbol) -> int:
    """
    根据信心程度返回最大允许杠杆
    信心越高 → 允许越高杠杆（但最多不超过GPT指定的杠杆）
    """
    conf = calc_confidence(data, symbol)
    
    max_allowed = LEVERAGE  # 默认3x
    for threshold, lev, _ in CONFIDENCE_LEVERAGE_MAP:
        if conf >= threshold:
            max_allowed = lev
    
    # 日线RSI极端时不许高杠杆（RSI>70超买 或 RSI<30超卖）
    rsi_1d = data.get(symbol, {}).get('rsi_1d', 50)
    if rsi_1d > 70 or rsi_1d < 30:
        max_allowed = min(max_allowed, 3)
    
    return max_allowed


# ═══════════════════════════════════════════════════════════
# 移动止损（量化机构核心）
# ═══════════════════════════════════════════════════════════

def update_trailing_stop(pos, current, entry_price, side):
    """
    检查是否触发移动止损，触发则更新止损价
    返回 (是否触发, 新止损价)
    """
    if side == 'long':
        profit_pct = (current - entry_price) / entry_price
    else:
        profit_pct = (entry_price - current) / entry_price
    
    new_stop = pos.get('stop', 0)  # 默认不动
    
    for trigger_profit, stop_dist_pct, label in TRAILING_TRIGGERS:
        if profit_pct >= trigger_profit:
            if side == 'long':
                candidate = entry_price * (1 + stop_dist_pct)
            else:
                candidate = entry_price * (1 - stop_dist_pct)
            
            # 止损只能上移，不能回撤
            if side == 'long' and candidate > new_stop:
                new_stop = candidate
            elif side == 'short' and candidate < new_stop:
                new_stop = candidate
    
    return new_stop


def calc_pnl(entry, current, side, leverage, margin):
    if side == 'long':
        return (current - entry) / entry * leverage * margin
    else:
        return (entry - current) / entry * leverage * margin


# ═══════════════════════════════════════════════════════════
# 网格开仓（核心函数）
# ═══════════════════════════════════════════════════════════
def open_grid(sym, side, entry_price):
    """在 sym 上开 GRID_LEVELS 层网格，同方向不同价格"""
    interval = entry_price * GRID_INTERVAL_PCT / 100  # 每格价格间距
    grid_positions = []

    for i in range(GRID_LEVELS):
        if side == 'long':
            # 做多网格：低价先开（跌了加仓），高价后开（追涨）
            lvl_entry = entry_price - interval * (GRID_LEVELS - 1 - i)
        else:
            # 做空网格：高价先开（涨了加仓），低价后开（杀跌）
            lvl_entry = entry_price + interval * (GRID_LEVELS - 1 - i)

        # 每层止损 = 本层入场价 ± 1格距
        if side == 'long':
            lvl_stop = lvl_entry - interval * 1.5  # 多头止损在下方
            lvl_tp = lvl_entry + interval * 2.0     # 多头止盈在上方
        else:
            lvl_stop = lvl_entry + interval * 1.5  # 空头止损在上方
            lvl_tp = lvl_entry - interval * 2.0     # 空头止盈在下方

        margin = state['cash'] * GRID_MARGIN_PCT  # 每层 20% 保证金
        pos = {
            'symbol': sym,
            'side': side,
            'entry': lvl_entry,
            'stop': lvl_stop,
            'tp': lvl_tp,
            'leverage': LEVERAGE,
            'margin': margin,
            'open_time': time.time(),
            'unrealized_pnl': 0,
            'level': i + 1,
            'reason': f'网格{i+1}/{GRID_LEVELS}',
        }
        grid_positions.append(pos)

    # 全部追加到持仓列表
    state['positions'].extend(grid_positions)

    for pos in grid_positions:
        log(f"📊 网格{pos['level']}/{GRID_LEVELS} | {sym} {side} @{pos['entry']:.4f} 止损${pos['stop']:.4f} 目标${pos['tp']:.4f} 保证金${pos['margin']:.2f}")

    save()


# ═══════════════════════════════════════════════════════════
# 保存状态
# ═══════════════════════════════════════════════════════════

def save():
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


# ═══════════════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════════════

log(f'=== 主权GPT虚拟盘 启动 | 资金${INITIAL_CASH} | 3x杠杆 ===')
log(f'知识库目录: {KB_DIR}')

while True:
    try:
        # 采集数据
        data = collect_data()
        sol_price = data.get('SOL/USDT', {}).get('price', 0)
        log(f"数据: BTC${data['BTC/USDT']['price']:,.0f} RSI_1d={data['BTC/USDT']['rsi_1d']:.1f} | ETH${data['ETH/USDT']['price']:.2f} RSI_1d={data['ETH/USDT']['rsi_1d']:.1f} | SOL${sol_price:.2f} RSI_1d={data.get('SOL/USDT', {}).get('rsi_1d', 50):.1f}")

        # ── 检查所有网格持仓 ──
        closed_any = False
        for pos in list(state['positions']):
            sym = pos['symbol']
            current = data.get(sym, {}).get('price')
            if not current:
                continue

            margin = pos['margin']
            pos['unrealized_pnl'] = calc_pnl(pos['entry'], current, pos['side'], LEVERAGE, margin)

            log(f"持仓{pos.get('level','?')}: {sym} {pos['side']} @{current:.4f} 浮${pos['unrealized_pnl']:.2f}")

            triggered = False
            action = ''
            pnl = 0

            if pos['side'] == 'long' and current <= pos['stop']:
                action = '止损'; pnl = calc_pnl(pos['entry'], current, 'long', LEVERAGE, margin); triggered = True
            elif pos['side'] == 'short' and current >= pos['stop']:
                action = '止损'; pnl = calc_pnl(pos['entry'], current, 'short', LEVERAGE, margin); triggered = True
            elif pos['side'] == 'long' and current >= pos['tp']:
                action = '止盈'; pnl = calc_pnl(pos['entry'], current, 'long', LEVERAGE, margin); triggered = True
            elif pos['side'] == 'short' and current <= pos['tp']:
                action = '止盈'; pnl = calc_pnl(pos['entry'], current, 'short', LEVERAGE, margin); triggered = True

            if triggered:
                fee = margin * TAKER_FEE
                state['cash'] += pnl - fee
                state['pnl'] += pnl
                state['fees'] += fee
                state['trades'] += 1
                log(f"✅ {action} | 网格{pos.get('level','?')} {sym} @{current:.4f} PnL=${pnl:.2f} 手续费${fee:.2f}")
                log(f"   余额: ${state['cash']:.2f}")

                params = {'symbol': sym, 'side': pos['side'], 'leverage': pos.get('leverage', LEVERAGE),
                          'stop_loss_pct': abs(pos['entry']-pos['stop'])/pos['entry'], 'take_profit_pct': abs(pos['tp']-pos['entry'])/pos['entry']}
                result = {'pnl_pct': pnl/margin*100, 'nav': state['cash']}
                update_knowledge(params, result)

                state['positions'].remove(pos)
                save()
                closed_any = True

        # ── 宏观风险拦截 ──
        if data.get('macro_risky'):
            log(f"⚠️ 宏观风险暂停 | {data.get('macro_reason','')} | 不开新仓，只处理现有持仓")

        # ── 无持仓 → GPT决策开网格 ──
        if not state['positions']:
            decision = gpt_decide(data)
            log(f"GPT决策: {decision}")

            # 宏观暂停时强制跳过开仓
            if data.get('macro_risky') and decision.get('action') in ('long', 'short'):
                log(f"⚠️ 宏观暂停跳过开仓 | GPT信号: {decision.get('action')} {decision.get('symbol')}")
                decision = {'action': 'hold', 'reason': f"宏观风险暂停: {data.get('macro_reason','')}"}

            if decision.get('action') in ('long', 'short') and decision.get('symbol'):
                sym = decision['symbol']
                entry_price = data[sym]['price']
                entry_conf = calc_confidence(data, sym)

                if entry_conf < 0.5:
                    log(f"❌ 信心{entry_conf:.0%}低于50%阈值，跳过开仓")
                else:
                    params = {'symbol': sym, 'side': decision['action'], 'leverage': LEVERAGE,
                              'stop_loss_pct': GRID_INTERVAL_PCT * 1.5 / 100, 'take_profit_pct': GRID_INTERVAL_PCT * 2.0 / 100}
                    ok, msg = validate_params(params)
                    if not ok:
                        log(f"❌ 参数校验失败: {msg}")
                    else:
                        open_grid(sym, decision['action'], entry_price)
                        log(f"🐢 GPT信号 | {sym} {decision['action']} @{entry_price:.4f} 信心{entry_conf:.2f}")

            elif decision.get('action') == 'hold' and decision.get('reason'):
                log(f"🤚 GPT观望 | {decision.get('reason', '无信号')}")

        # ── 热点币日志（每小时轮换中记录）──
        hot = data.get('hot_coins', [])
        if hot:
            hot_str = ' | '.join([f"{h['symbol']}{h['price_change']:+.1f}%" for h in hot[:3]])
            log(f"🔥 热点: {hot_str}")

        # ── 生成日报（每24次循环≈每2天，也可在启动时触发）──
        # 简单策略：每小时写一次，文件名带日期，保留7天
        report = daily_report(data, state)

        time.sleep(7200)  # 2小时循环

    except Exception as e:
        import traceback
        log(f"异常: {e} | {traceback.format_exc()[-200:]}")
        time.sleep(300)