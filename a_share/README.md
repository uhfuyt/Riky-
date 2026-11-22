# A股量化交易技术库

> 2026-11-22 建立。全部结论有回测实测数据支撑，可用本目录脚本复现。

## 快速开始

```bash
# 1. 建环境
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python pandas numpy requests akshare

# 2. 拉数据（30只个股 + 16只ETF，各750天）
./.venv/bin/python scripts/fetch_long_data.py
./.venv/bin/python scripts/fetch_etf_kline.py

# 3. 跑回测
./.venv/bin/python scripts/run_backtest_v2.py 2000 etf
./.venv/bin/python scripts/run_oos_test.py
./.venv/bin/python scripts/run_rolling_windows.py
./.venv/bin/python scripts/run_guosen_real_cost.py
./.venv/bin/python scripts/run_stock_capital.py
```

## 核心结论（数据说话）

| 问题 | 答案 | 证据 |
|---|---|---|
| 2000元 + 5元佣金门槛能做吗 | ❌ **不能** | ETF -3.28%，12窗口仅3个赚钱 |
| 免五后能做吗 | ✅ **能** | +2.49%，8/12赚钱（提升5.8个百分点） |
| 5元门槛下本金门槛 | ETF **2万+** / 个股 **5000元单票满仓** | 佣金占比测算 |
| 唯一通过样本外检验的策略 | 动量突破 `0.998 / MA20 / MA20` | IS +26.79% → OOS +9.01% |
| 但滚动窗口超额 | **+0.04% ≈ 0** | 主要是 beta 不是 alpha |
| 个股 vs ETF | **ETF 完胜** | 回撤 -9.5% vs -22.1%，费用 1.9% vs 5.46% |
| 5元门槛下分散持仓 | **亏钱** | 10000元2只 -3.25% vs 1只满仓 +3.41% |

## 目录结构

```
docs/           技术知识库（A股量化技术知识库_2026-11-22.md）
scripts/        全部回测 / 数据采集脚本（15个）
data_results/   回测结果 JSON + 实测日志（可复现）
```

详细内容见 [docs/A股量化技术知识库_2026-11-22.md](docs/A股量化技术知识库_2026-11-22.md)

## 数据源（实测可用）

| 数据源 | 端点 | 状态 |
|---|---|---|
| 腾讯 fqkline（个股） | `web.ifzq.gtimg.cn/appstock/app/fqkline/get` | ✅ 750天 |
| 腾讯 kline（**ETF专用**） | `web.ifzq.gtimg.cn/appstock/app/kline/kline` | ✅ 750天（fqkline对ETF返回501） |
| 新浪财经 | `finance.sina.com.cn` | ✅ |
| 东方财富 push2his | `push2his.eastmoney.com` | ❌ 新加坡IP超时 |
| 同花顺 / 百度百科 | — | ❌ 403 |

## 外部技术采集

`scripts/fetch_x_quant.py` — 通过 `syndication.twitter.com` 抓取 X/Twitter 量化账号内容（无需 API Key）。
已采集 81 条，关键发现见知识库第七节。

## 免责声明

本项目为量化研究与教学用途。实盘交易有亏损风险，历史回测不代表未来收益。
所有费率数据来源已标注，实际费率以券商协议为准。
