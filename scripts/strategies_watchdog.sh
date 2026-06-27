#!/bin/bash
# 暗黑星火 · 综合虚拟盘看门狗
# 保活: paper_engine_v1 + 10个独立策略

CH_DIR="/home/admin/charon"
STATE_PID="$CH_DIR/virtual_state/strategies"

# === 1) paper_engine_v1 主守护 ===
PID_FILE="$CH_DIR/virtual_state/engine.pid"
if [ -f "$PID_FILE" ]; then
    OLD=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
        :  # alive
    else
        cd "$CH_DIR"
        nohup python3 -u scripts/paper_engine_v1.py >> bot_logs/paper_engine.log 2>&1 &
        echo $! > "$PID_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] watchdog: paper_engine_v1 PID=$!" >> bot_logs/paper_engine.log
    fi
fi

# === 2) 10个独立策略 ===
mkdir -p "$STATE_PID"
STRATEGIES=(
    "bear_short_paper:bear_short_paper.py"
    "combo31_paper:combo31_paper.py"
    "futures_paper:futures_paper.py"
    "macd_rsi_paper:macd_rsi_paper.py"
    "macd_trend_paper:macd_trend_paper.py"
    "meanrevert_paper:meanrevert_paper.py"
    "pairs_paper:pairs_paper.py"
    "rsi_meanrev_paper:rsi_meanrev_paper.py"
    "sovereign_gpt_paper:sovereign_gpt_paper.py"
    "turtle_paper:turtle_paper.py"
)

for entry in "${STRATEGIES[@]}"; do
    name="${entry%%:*}"
    script="${entry##*:}"
    pid_file="$STATE_PID/$name.pid"
    log_file="$CH_DIR/bot_logs/${name}.log"

    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            continue
        fi
    fi

    cd "$CH_DIR"
    nohup python3 -u "strategies/$script" >> "$log_file" 2>&1 &
    new_pid=$!
    echo "$new_pid" > "$pid_file"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] watchdog: $name PID=$new_pid" >> "$log_file"
done
