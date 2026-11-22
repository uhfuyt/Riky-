#!/usr/bin/env python3
"""
ETF K线下载器
腾讯 fqkline 端点对ETF返回501, 但 /appstock/app/kline/kline 端点可用
"""
import os, sys, time, json
import pandas as pd
import requests

DATA_DIR = "/home/admin/.hermes/mempalace/quant_trading/a_share/data"
DATALEN = 750
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    'Referer': 'https://gu.qq.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

ETF_LIST = [
    ('sh510300', '沪深300ETF'),
    ('sh510500', '中证500ETF'),
    ('sh512100', '中证1000ETF'),
    ('sh588000', '科创50ETF'),
    ('sz159915', '创业板ETF'),
    ('sh510880', '红利ETF'),
    ('sz159919', '沪深300ETF深'),
    ('sh513100', '纳指ETF'),
    ('sh513500', '标普500ETF'),
    ('sh512880', '证券ETF'),
    ('sh515180', '红利低波ETF'),
    ('sh516160', '新能源ETF'),
    ('sh515790', '光伏ETF'),
    ('sh512170', '医疗ETF'),
    ('sh512690', '酒ETF'),
    ('sz159941', '纳指ETF深'),
]


def fetch_etf(code, max_retry=4):
    out = os.path.join(DATA_DIR, f"{code}_qq_{DATALEN}.csv")
    if os.path.exists(out):
        try:
            df = pd.read_csv(out, parse_dates=['日期'])
            if len(df) >= 400:
                print(f"  [缓存] {code} {len(df)}行", flush=True)
                return True
        except Exception:
            pass

    url = f'https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param={code},day,,,{DATALEN}'
    for attempt in range(max_retry):
        try:
            r = requests.get(url, timeout=25, headers=HEADERS)
            r.raise_for_status()
            js = r.json()
            d = js.get('data', {}).get(code, {})
            kl = d.get('day') or d.get('qfqday')
            if not kl:
                raise ValueError(f"无数据: {str(js)[:120]}")
            rows = [{
                '日期': k[0], '开盘': float(k[1]), '收盘': float(k[2]),
                '最高': float(k[3]), '最低': float(k[4]),
                '成交量': float(k[5]) if len(k) > 5 else 0.0,
            } for k in kl]
            df = pd.DataFrame(rows)
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期').reset_index(drop=True)
            df.to_csv(out, index=False)
            print(f"  [OK] {code} {len(df)}行 {df['日期'].min().date()}~{df['日期'].max().date()}", flush=True)
            return True
        except Exception as e:
            wait = 3 * (attempt + 1)
            print(f"  [重试{attempt+1}] {code}: {e} → {wait}s", flush=True)
            time.sleep(wait)
    print(f"  [失败] {code}", flush=True)
    return False


def main():
    print(f"拉取 {len(ETF_LIST)} 只ETF × {DATALEN}天", flush=True)
    ok = 0
    for i, (code, name) in enumerate(ETF_LIST, 1):
        print(f"[{i}/{len(ETF_LIST)}] {code} {name}", flush=True)
        if fetch_etf(code):
            ok += 1
        time.sleep(1.0)
    print(f"\n完成: {ok}/{len(ETF_LIST)}", flush=True)


if __name__ == '__main__':
    main()
