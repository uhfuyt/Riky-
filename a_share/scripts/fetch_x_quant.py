#!/usr/bin/env python3
"""
X/Twitter 量化内容采集器
=========================
用 syndication.twitter.com 的 timeline-profile 端点(无需 API key)
抓取公开账号的推文 → 提取量化/A股相关技术内容
"""
import os, sys, json, re, html, time
import urllib.request

OUT_DIR = os.path.expanduser("~/.hermes/mempalace/quant_trading/a_share/knowledge")
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
}

# 量化交易相关账号 (英文技术 + 中文市场)
ACCOUNTS = [
    # 量化先驱 / 学术
    'epchan', 'macroops', 'therobotjames',
    # 平台 / 工程
    'QuantConnect', 'pyquantnews', 'NautilusTrader', 'hudsonthames',
    # 因子 / 统计
    'Quantpedia', 'alphaarchitect', 'Robeco',
    # 中文 / A股
    'qinbafrank', 'Marlin_Quant', 'wallstreetcn',
    # 加密量化(对照用)
    'cryptoquant_com',
]

KEYWORDS = [
    # 策略类
    'alpha', 'factor', 'momentum', 'mean reversion', 'mean-reversion', 'arbitrage',
    'backtest', 'overfit', 'sharpe', 'drawdown', 'regime', 'volatility',
    'machine learning', 'ML', 'transformer', 'neural', 'LLM', 'reinforcement',
    # 执行类
    'execution', 'slippage', 'impact', 'microstructure', 'latency', 'TCA',
    # A股/中国市场
    'A-share', 'A股', 'CSI', 'China', '北上', '沪深', '因子', '选股', 'alpha因子',
    'tushare', 'wind', '聚宽', '米筐', 'backtrader', 'vnpy',
    # 小资金/风控
    'position sizing', 'kelly', 'risk', 'commission', 'fee', 'transaction cost',
]


def fetch_timeline(handle):
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None


def parse_tweets(raw):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                  raw, flags=re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []

    tweets = []

    def walk(o):
        if isinstance(o, dict):
            if 'full_text' in o and isinstance(o.get('full_text'), str):
                tweets.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)

    walk(data)
    # 去重
    seen, out = set(), []
    for t in tweets:
        tid = t.get('id_str') or t.get('id')
        if tid in seen:
            continue
        seen.add(tid)
        out.append(t)
    return out


def score(txt):
    t = txt.lower()
    hits = [k for k in KEYWORDS if k.lower() in t]
    return len(hits), hits


def main():
    all_items = []
    for handle in ACCOUNTS:
        raw = fetch_timeline(handle)
        if not raw:
            print(f"[跳过] @{handle} 抓取失败")
            continue
        tweets = parse_tweets(raw)
        kept = 0
        for t in tweets:
            txt = html.unescape(t.get('full_text', ''))
            if len(txt) < 40:
                continue
            sc, hits = score(txt)
            if sc == 0:
                continue
            all_items.append({
                'source': f"X/@{handle}",
                'date': t.get('created_at', ''),
                'text': txt,
                'likes': t.get('favorite_count', 0),
                'retweets': t.get('retweet_count', 0),
                'score': sc,
                'keywords': hits[:6],
                'url': f"https://x.com/{handle}/status/{t.get('id_str', '')}",
            })
            kept += 1
        print(f"[OK] @{handle}: {len(tweets)}条 → 命中 {kept}条")
        time.sleep(1.2)

    # 按相关度+互动量排序
    all_items.sort(key=lambda x: (x['score'], x['likes']), reverse=True)

    out = os.path.join(OUT_DIR, 'x_quant_raw.json')
    with open(out, 'w') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=1)

    print(f"\n共采集 {len(all_items)} 条量化相关内容 → {out}")

    # 打印Top 20摘要
    print("\n" + "=" * 80)
    print("Top 20 (按相关度+互动)")
    print("=" * 80)
    for it in all_items[:20]:
        print(f"\n[{it['source']}] {it['date'][:16]} ❤{it['likes']} 关键词:{','.join(it['keywords'][:4])}")
        print(f"  {it['text'][:280]}")


if __name__ == '__main__':
    main()
