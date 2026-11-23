"""
路径引导 — 让 scripts/ 和 engine/ 互相能找到对方的模块。
所有依赖 a_share_backtest_v2 / run_trend_filter_test 等的脚本
只需在开头加一行:

    import _pathsetup  # noqa: F401

放在 scripts/ 和 engine/ 各一份。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# engine/ 和 scripts/ 都要在 sys.path 里
for _p in (_ROOT, os.path.join(_ROOT, 'engine'), os.path.join(_ROOT, 'scripts')):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
