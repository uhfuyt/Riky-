#!/usr/bin/env python3
"""
indicators.py — 常用技术指标计算（纯numpy实现，无TA-Lib依赖）
用法:
    import indicators as ind
    ind.ema(close, 12)
    ind.rsi(close, 14)
"""
import numpy as np


def ema(values, span):
    """指数移动平均"""
    v = np.asarray(values, dtype=float)
    alpha = 2.0 / (span + 1)
    out = np.empty_like(v)
    out[0] = v[0]
    for i in range(1, len(v)):
        out[i] = alpha * v[i] + (1 - alpha) * out[i - 1]
    return out


def sma(values, window):
    """简单移动平均"""
    v = np.asarray(values, dtype=float)
    out = np.full_like(v, np.nan)
    for i in range(window - 1, len(v)):
        out[i] = v[i - window + 1:i + 1].mean()
    return out


def rsi(close, period=14):
    """相对强弱指标 (Wilder平滑)"""
    c = np.asarray(close, dtype=float)
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # Wilder 平滑 = EMA with alpha=1/period
    avg_gain = ema(gain, period * 2 - 1)
    avg_loss = ema(loss, period * 2 - 1)
    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    out = 100 - (100 / (1 + rs))
    out[0] = 50.0  # 首值中性
    return out


def atr(high, low, close, period=14):
    """平均真实波幅"""
    h, l, c = np.asarray(high, float), np.asarray(low, float), np.asarray(close, float)
    tr = np.empty_like(c)
    tr[0] = h[0] - l[0]
    for i in range(1, len(c)):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return ema(tr, period * 2 - 1)


def bollinger(close, window=20, num_std=2):
    """布林带: 返回 (中轨, 上轨, 下轨)"""
    c = np.asarray(close, float)
    mid = sma(c, window)
    std = np.full_like(c, np.nan)
    for i in range(window - 1, len(c)):
        std[i] = c[i - window + 1:i + 1].std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower


def macd(close, fast=12, slow=26, signal=9):
    """MACD: 返回 (dif, dea, hist)"""
    c = np.asarray(close, float)
    dif = ema(c, fast) - ema(c, slow)
    dea = ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist


def momentum(close, window=10):
    """动量: 当前价 / N期前价 - 1"""
    c = np.asarray(close, float)
    out = np.full_like(c, np.nan)
    out[window:] = c[window:] / c[:-window] - 1.0
    return out


if __name__ == "__main__":
    # 自测: 用一段假数据验证不报错
    fake = np.array([100, 101, 99, 102, 105, 104, 103, 106, 108, 107, 110, 111, 109, 112, 115, 114, 113, 116, 118, 117], dtype=float)
    print("ema12:", np.round(ema(fake, 12)[-3:], 2))
    print("rsi14:", np.round(rsi(fake, 14)[-3:], 2))
    print("sma5 :", np.round(sma(fake, 5)[-3:], 2))
    print("✅ 指标自测通过")
