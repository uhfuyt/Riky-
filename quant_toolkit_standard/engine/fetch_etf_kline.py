#!/usr/bin/env python3
"""
ETF K线下载器
腾讯 fqkline 端点对ETF返回501, 但 /appstock/app/kline/kline 端点可用
"""
import os, sys, time, json
import pandas as pd
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
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


def _is_fresh(df, max_stale_days=5):
    """判断本地日线是否够新。

    A股周末/节假日没有新bar, 所以不能简单比"今天"。
    规则: 数据最后一天距今 <= max_stale_days 个自然日 → 视为新鲜。
    超过 → 需要重新拉取 (可能是真缺数据, 也可能是数据源出问题了)。
    """
    try:
        last = pd.to_datetime(df['日期']).max()
        today = pd.Timestamp.now().normalize()
        age = (today - last).days
        return age <= max_stale_days
    except Exception:
        return False


def fetch_etf(code, max_retry=4, force=False):
    """拉取单个ETF的日线。

    ⚠️ 缓存短路 bug (2026-11-22 修复):
    原实现只要本地文件 >=400 行就直接 return True，导致**永远不更新**，
    纸盘因此卡在旧数据上 (实测卡在 2026-11-20)。
    现在: force=True 或本地数据不够新 → 重新拉取并覆盖。
    """
    out = os.path.join(DATA_DIR, f"{code}_qq_{DATALEN}.csv")
    if os.path.exists(out) and not force:
        try:
            df = pd.read_csv(out, parse_dates=['日期'])
            if len(df) >= 400 and _is_fresh(df):
                print(f"  [缓存] {code} {len(df)}行 最新{df['日期'].max().date()}", flush=True)
                return True
            # 数据过期 → 继续走网络拉取
            print(f"  [过期] {code} {len(df)}行 最新{df['日期'].max().date()} → 重新拉取", flush=True)
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
            # ⚠️ 原子写入: 先写临时文件再 rename。
            # 直接 to_csv 覆盖的话, 中途失败会毁掉已有历史数据,
            # 纸盘/回测立刻失去基准。
            tmp = out + '.tmp'
            df.to_csv(tmp, index=False)
            os.replace(tmp, out)
            print(f"  [OK] {code} {len(df)}行 {df['日期'].min().date()}~{df['日期'].max().date()}", flush=True)
            return True
        except Exception as e:
            wait = 3 * (attempt + 1)
            print(f"  [重试{attempt+1}] {code}: {e} → {wait}s", flush=True)
            time.sleep(wait)
    print(f"  [失败] {code}", flush=True)
    return False


def main():
    force = '--force' in sys.argv
    print(f"拉取 {len(ETF_LIST)} 只ETF × {DATALEN}天{' (强制刷新)' if force else ''}", flush=True)
    ok = 0
    for i, (code, name) in enumerate(ETF_LIST, 1):
        print(f"[{i}/{len(ETF_LIST)}] {code} {name}", flush=True)
        if fetch_etf(code, force=force):
            ok += 1
        time.sleep(1.0)
    print(f"\n完成: {ok}/{len(ETF_LIST)}", flush=True)
    return 0 if ok == len(ETF_LIST) else 1


if __name__ == '__main__':
    raise SystemExit(main())
