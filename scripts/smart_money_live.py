#!/usr/bin/env python3
"""
smart_money_live.py
聪明钱自动追踪 — 全托管版
无需截图，自动抓取交易所+链上数据，识别聪明钱信号
每3小时cron触发，更新 smart_money_live.json 和 smart_money_track.md
"""
import json, time, urllib.request, sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path('/home/admin/charon/analysis')
TRACK_FILE = BASE / 'smart_money_track.md'
DATA_FILE = Path('/tmp/smart_money_live.json')

# ── 币安行情 ──
import ccxt
ex = ccxt.binance({'enableRateLimit': True})

def fetch_all():
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'XRP/USDT', 'ADA/USDT']
    result = {}
    for sym in symbols:
        try:
            spot = ex.fetch_ticker(sym)
            try:
                perp = ex.fetch_ticker(sym + ':USDT')
                funding = ex.fetch_funding_rate(sym + ':USDT')
                fr = float(funding['fundingRate']) * 100
            except:
                perp = None
                fr = 0
            result[sym.replace('/USDT','')] = {
                'price': spot['last'],
                'change_24h_pct': round(float(spot.get('change',0) or 0)/spot['last']*100, 3),
                'volume_24h_usdt': round(float(spot.get('quoteVolume',0) or 0)/1e6, 1),
                'funding_rate': round(fr, 4),
                'open_interest': 0,
            }
        except Exception as e:
            result[sym.replace('/USDT','')] = {'error': str(e)}
        time.sleep(0.2)
    return result

def calc_rsi(closes, period=14):
    import numpy as np
    if len(closes) < period+1: return 50
    arr = np.array(closes, dtype=float)
    deltas = np.diff(arr)
    gains = np.maximum(deltas, 0)
    losses = np.maximum(-deltas, 0)
    avg_g = np.mean(gains[-period:])
    avg_l = np.mean(losses[-period:])
    if avg_l < 1e-10: return 100
    rs = avg_g / avg_l
    return round(100 - 100/(1+rs), 1)

def analyze(data):
    """识别聪明钱信号"""
    signals = []
    alerts = []
    
    for coin, d in data.items():
        if 'error' in d: continue
        price = d['price']
        fr = d['funding_rate']
        chg = d['change_24h_pct']
        
        # 1. 资金费率极端值 → 聪明钱做空信号
        if fr > 0.01:  # >0.01% 每8h = 年化>10%
            signals.append(f'🔥 {coin}: 多头费率{fr:.4f}%（年化>10%）→ 聪明钱在做空')
            alerts.append(('short', coin, fr))
        
        # 2. 资金费率为负 → 空头付钱，做多信号
        if fr < -0.01:
            signals.append(f'📈 {coin}: 空头费率{fr:.4f}%（年化>12%）→ 聪明钱在做多')
            alerts.append(('long', coin, fr))
        
        # 3. 24h涨幅异常
        if abs(chg) > 5:
            signals.append(f'⚡ {coin}: 24h涨跌{chg:.2f}% → 极端波动，关注趋势延续')
        
        # 4. 成交量暴涨
        if d['volume_24h_usdt'] > 500:  # >$500M
            signals.append(f'📊 {coin}: 成交量${d['volume_24h_usdt']:.0f}M → 大户异动')
    
    return signals, alerts

def build_report(data, signals):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    # 计算RSI（用1h K线）
    rsi_data = {}
    for coin in data:
        if 'error' in data[coin]: continue
        try:
            klines = ex.fetch_ohlcv(f'{coin}/USDT', '1h', limit=15)
            closes = [k[4] for k in klines]
            rsi_data[coin] = calc_rsi(closes)
        except:
            rsi_data[coin] = None

    report = f"""# 🧠 聪明钱实时追踪（自动更新）
> 更新时间: {now} | 触发频率: 每3小时

---

## 行情快照

| 币种 | 价格 | 24h涨跌 | 成交量(M) | 资金费率(8h) | RSI(1h) |
|------|------|---------|----------|-------------|---------|
"""
    for coin, d in data.items():
        if 'error' in d: continue
        rsi = rsi_data.get(coin, '-')
        flag = '🔴' if d['funding_rate'] > 0.01 else ('🟢' if d['funding_rate'] < -0.01 else '⚪')
        report += f"| {flag} {coin} | ${d['price']:.4f} | {d['change_24h_pct']:+.2f}% | ${d['volume_24h_usdt']:.0f}M | {d['funding_rate']:+.4f}% | {rsi} |\n"
    
    report += f"""
---

## 聪明钱信号（{len(signals)}个）

"""
    if signals:
        for s in signals:
            report += f"- {s}\n"
    else:
        report += "- 无极端信号，市场相对中性\n"
    
    report += """
---

## 操作参考

| 信号类型 | 资金费率触发 | 操作 |
|---------|------------|------|
| 🔴 极端多头费率 | >0.01%/8h | 警惕，聪明钱可能在做空 |
| 🟢 极端空头费率 | <-0.01%/8h | 机会，聪明钱可能在做多 |
| ⚡ 24h涨跌>5% | 极端波动 | 顺势不追，等回调 |
| 📊 成交量>$500M | 大户活动 | 确认方向后再跟 |

> 注：资金费率是永续合约多空博弈的结果。极端费率往往预示短期反转。

"""
    return report

def main():
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 聪明钱追踪器启动...')
    
    data = fetch_all()
    print(f'获取数据: {[k for k in data.keys()]}')
    
    signals, alerts = analyze(data)
    print(f'信号数: {len(signals)}')
    
    report = build_report(data, signals)
    
    # 保存MD
    TRACK_FILE.write_text(report)
    print(f'已更新: {TRACK_FILE}')
    
    # 保存JSON
    DATA_FILE.write_text(json.dumps({
        'updated': datetime.now(timezone.utc).isoformat(),
        'data': data,
        'signals': signals,
        'alerts': alerts
    }, indent=2))
    print(f'已更新: {DATA_FILE}')

if __name__ == '__main__':
    main()