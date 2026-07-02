#!/bin/bash
# 暗黑星火 · 精简看门狗 (只保活3个最优策略 + paper_engine_v1)
LOG_DIR="/home/admin/charon/bot_logs"
CH_DIR="/home/admin/charon"
SCRIPT_DIR="$CH_DIR/strategies"
PID_DIR="$CH_DIR/virtual_state/strategies"
mkdir -p "$PID_DIR"

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

# === 2) 只保活3个最优独立策略 (2026-07-02 加sol_turtle_paper) ===
STRATEGIES=(
    "combo31_paper:combo31_paper.py"
    "rsi_meanrev_paper:rsi_meanrev_paper.py"
    "sol_turtle_paper:sol_turtle_paper.py"
)

for entry in "${STRATEGIES[@]}"; do
    name="${entry%%:*}"
    script="${entry##*:}"
    pid_file="$PID_DIR/$name.pid"
    log_file="$LOG_DIR/${name}.log"

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
