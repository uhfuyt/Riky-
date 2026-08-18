#!/usr/bin/env python3
"""
fetch_klines.py — 免费K线数据获取（币安公开API，无需API Key）
用法:
    python fetch_klines.py --symbol BTCUSDT --interval 1h --limit 720
    python fetch_klines.py --symbol ETHUSDT --interval 1d --limit 365 --out eth_daily.csv
"""
import argparse
import csv
import json
import time
import urllib.request


def fetch_binance_klines(symbol: str, interval: str, limit: int = 1000) -> list:
    """从币安公开接口拉K线。返回 [ts, open, high, low, close, volume] 列表。"""
    url = (f"https://api.binance.com/api/v3/klines"
           f"?symbol={symbol}&interval={interval}&limit={limit}")
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())
    return [[int(k[0]), float(k[1]), float(k[2]), float(k[3]),
             float(k[4]), float(k[5])] for k in data]


def save_csv(rows: list, path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ts", "open", "high", "low", "close", "volume"])
        writer.writerows(rows)
    print(f"✅ 已保存 {len(rows)} 根K线到 {path}")


def main():
    parser = argparse.ArgumentParser(description="币安K线获取（免费，无需Key）")
    parser.add_argument("--symbol", default="BTCUSDT", help="交易对，默认BTCUSDT")
    parser.add_argument("--interval", default="1h", help="周期：1m/5m/15m/1h/4h/1d，默认1h")
    parser.add_argument("--limit", type=int, default=720, help="K线数量，默认720（30天1h）")
    parser.add_argument("--out", default=None, help="输出CSV路径，默认打印到终端")
    args = parser.parse_args()

    print(f"⏳ 拉取 {args.symbol} {args.interval} x {args.limit} 根...")
    rows = fetch_binance_klines(args.symbol, args.interval, args.limit)
    if not rows:
        print("❌ 返回空数据，检查symbol/interval")
        return

    print(f"✅ 拉到 {len(rows)} 根K线")
    print(f"   最新收盘价: {rows[-1][4]}  ({rows[-1][0]})")
    if args.out:
        save_csv(rows, args.out)
    else:
        print("   前3行示例:")
        for r in rows[:3]:
            print(f"   {r}")


if __name__ == "__main__":
    main()
