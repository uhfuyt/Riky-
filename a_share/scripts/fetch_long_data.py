#!/usr/bin/env python3
"""
A股长周期数据拉取器 (750天/3年)
后台跑, 拉腾讯前复权K线, 失败重试, 断点续传
"""
import os, sys, time, json, traceback
import pandas as pd
import requests

DATA_DIR = "/home/admin/.hermes/mempalace/quant_trading/a_share/data"
os.makedirs(DATA_DIR, exist_ok=True)

DATALEN = 750  # 约3年

def _to_qq_symbol(symbol):
    s = str(symbol).strip()
    if s.startswith(('sh', 'sz', 'bj')):
        return s.lower()   # 腾讯接口必须小写(sh510300), 大写会501
    if s.startswith(('6','9')):
        return 'sh' + s
    if s.startswith(('0','2','3')):
        return 'sz' + s
    if s.startswith(('4','8')):
        return 'bj' + s
    return 'sh' + s

def fetch_one(symbol, max_retry=4):
    qq = _to_qq_symbol(symbol)
    out = os.path.join(DATA_DIR, f"{qq}_qq_{DATALEN}.csv")
    if os.path.exists(out):
        try:
            df = pd.read_csv(out, parse_dates=['日期'])
            if len(df) >= 500:
                print(f"  [缓存] {qq} {len(df)}行", flush=True)
                return True
        except Exception:
            pass

    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
    params = {'param': f'{qq},day,,,{DATALEN},qfq'}
    headers = {'Referer': 'https://gu.qq.com/', 'User-Agent': 'Mozilla/5.0'}

    for attempt in range(max_retry):
        try:
            r = requests.get(url, params=params, timeout=25, headers=headers)
            r.raise_for_status()
            js = r.json()
            data = js.get('data', {}).get(qq, {})
            klines = data.get('qfqday') or data.get('day')
            if not klines:
                raise ValueError(f"无K线数据: {json.dumps(js)[:150]}")
            rows = []
            for k in klines:
                # [日期, 开, 收, 高, 低, 成交量]
                rows.append({
                    '日期': k[0],
                    '开盘': float(k[1]),
                    '收盘': float(k[2]),
                    '最高': float(k[3]),
                    '最低': float(k[4]),
                    '成交量': float(k[5]) if len(k) > 5 else 0.0,
                })
            df = pd.DataFrame(rows)
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期').reset_index(drop=True)
            df.to_csv(out, index=False)
            print(f"  [OK] {qq} {len(df)}行 {df['日期'].min().date()}~{df['日期'].max().date()}", flush=True)
            return True
        except Exception as e:
            wait = 3 * (attempt + 1)
            print(f"  [重试{attempt+1}] {qq}: {e} → 等待{wait}s", flush=True)
            time.sleep(wait)
    print(f"  [失败] {qq}", flush=True)
    return False

def main():
    # 中证100前30
    try:
        sys.path.insert(0, "/home/admin/.hermes/mempalace/quant_trading/a_share")
        from a_share_backtest_engine import get_universe
        df_uni = get_universe('000903')
        symbols = [r['成分券代码'] for r in df_uni.to_dict('records')[:30]]
        names = {r['成分券代码']: r.get('成分券名称', '') for r in df_uni.to_dict('records')[:30]}
    except Exception as e:
        print(f"获取股票池失败: {e}", flush=True)
        traceback.print_exc()
        return

    print(f"股票池: {len(symbols)}只, datalen={DATALEN}", flush=True)
    ok = 0
    for i, sym in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {sym} {names.get(sym,'')}", flush=True)
        if fetch_one(sym):
            ok += 1
        time.sleep(1.2)  # 别打爆腾讯接口

    # 沪深300基准
    print("拉取基准指数 sh000300", flush=True)
    try:
        url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get'
        r = requests.get(url, params={'param': f'sh000300,day,,,{DATALEN},qfq'}, timeout=25,
                         headers={'Referer': 'https://gu.qq.com/', 'User-Agent': 'Mozilla/5.0'})
        js = r.json()
        kl = js.get('data', {}).get('sh000300', {}).get('qfqday') or js.get('data', {}).get('sh000300', {}).get('day')
        rows = [{'日期': k[0], '开盘': float(k[1]), '收盘': float(k[2]), '最高': float(k[3]),
                 '最低': float(k[4]), '成交量': float(k[5]) if len(k) > 5 else 0.0} for k in kl]
        bdf = pd.DataFrame(rows)
        bdf['日期'] = pd.to_datetime(bdf['日期'])
        bdf = bdf.sort_values('日期').reset_index(drop=True)
        bdf.to_csv(os.path.join(DATA_DIR, f"sh000300_qq_{DATALEN}.csv"), index=False)
        print(f"  [OK] 沪深300 {len(bdf)}行", flush=True)
    except Exception as e:
        print(f"  [失败] 基准: {e}", flush=True)

    print(f"\n完成: {ok}/{len(symbols)} 只成功", flush=True)

if __name__ == '__main__':
    main()
