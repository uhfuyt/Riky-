#!/bin/bash
# 暗黑星火 · 11个独立paper脚本看门狗
LOG_DIR="/home/admin/charon/bot_logs"
SCRIPT_DIR="/home/admin/charon/strategies"
PID_DIR="/home/admin/charon/virtual_state/strategies"
mkdir -p "$PID_DIR"

# 要保活的策略 (按PnL筛选: 正收益+有持仓优先)
STRATEGIES=(
    "macd_rsi_paper:macd_rsi_paper.py:300"
    "rsi_meanrev_paper:rsi_meanrev_paper.py:7200"
    "combo31_paper:combo31_paper.py:7200"
)

for entry in "${STRATEGIES[@]}"; do
    name="${entry%%:*}"
    rest="${entry#*:}"
    script="${rest%%:*}"

    pid_file="$PID_DIR/$name.pid"
    log_file="$LOG_DIR/${name}.log"

    # 检查进程
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            continue  # 还在跑,跳过
        fi
    fi

    # 启动
    cd /home/admin/charon
    nohup python3 -u "$SCRIPT_DIR/$script" >> "$log_file" 2>&1 &
    new_pid=$!
    echo "$new_pid" > "$pid_file"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] watchdog启动 $name PID=$new_pid" >> "$log_file"
done
