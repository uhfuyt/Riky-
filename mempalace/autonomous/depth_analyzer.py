#!/usr/bin/env python3
"""
depth_analyzer 存根模块
=======================
ds0_analyst_v3.py 依赖此模块进行订单簿深度分析。
原始文件缺失，此存根提供最小接口使ds0能加载运行。
深度分析功能暂时禁用（返回空数据）。
"""
import os
from pathlib import Path

_HISTORY_PATH = None

def set_history_path(path: str):
    """设置历史深度数据路径"""
    global _HISTORY_PATH
    _HISTORY_PATH = path

def analyze_symbols(symbols: list, kline_map: dict) -> dict:
    """
    分析指定币种的订单簿深度。
    存根版本：返回空结果（功能待恢复）
    """
    result = {}
    for sym in symbols:
        result[sym] = {
            'bid_walls': [],
            'ask_walls': [],
            'depth_imbalance': 0.0,
            'fakeout_risk': 'unknown',
            'large_orders': [],
        }
    return result

def get_depth_history(symbol: str, limit: int = 100) -> list:
    """读取历史深度数据（存根版本返回空列表）"""
    return []

def save_depth_snapshot(symbol: str, data: dict):
    """保存深度数据快照（存根版本——只写路径不写文件）"""
    if _HISTORY_PATH:
        Path(_HISTORY_PATH).parent.mkdir(parents=True, exist_ok=True)
