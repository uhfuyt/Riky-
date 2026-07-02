#!/bin/bash
# 暗黑星火 · 虚拟盘心跳健康检查
# 每4小时执行: 检查所有paper进程,异常修复/正常不打扰
# 报告风格: 一行一进程 | PID | 状态 | PnL | 最后日志时间

WORKSPACE="/home/admin/charon"
LOG_DIR="$WORKSPACE/bot_logs"
RPT="$WORKSPACE/bot_logs/healthcheck_$(date +%Y%m%d_%H%M).log"
ALERT_FLAG="$WORKSPACE/bot_logs/.need_attention"

# 待监控的paper进程(关键词) + 期望日志后缀
# 2026-07-02精简: 删macd_rsi(亏)/rsi_meanrev(平庸)/sol_turtle双开, 保留最强3个
# 2026-07-02扩展: 加combo31_multi (6币种三层门控, 熊市做空)
# 2026-07-02终极: 加ds0_compound_100u (5阶段金字塔, 100U→$12,800任务)
declare -A PROCS=(
  ["combo31_paper"]="strategies/combo31_paper.py"
  ["combo31_multi"]="strategies/combo31_multi.py"
  ["paper_engine_v1"]="scripts/paper_engine_v1.py"
  ["sol_turtle_paper"]="strategies/sol_turtle_paper.py"
  ["ds0_compound_100u"]="strategies/ds0_compound_100u.py"
)
# 启动命令(start_cmd): 用于重启时拉起
declare -A START_CMDS=(
  ["combo31_paper"]="cd /home/admin/charon && python3 -u strategies/combo31_paper.py"
  ["combo31_multi"]="cd /home/admin/charon && python3 -u strategies/combo31_multi.py"
  ["paper_engine_v1"]="cd /home/admin/charon && python3 -u scripts/paper_engine_v1.py"
  ["sol_turtle_paper"]="cd /home/admin/charon && python3 -u strategies/sol_turtle_paper.py"
  ["ds0_compound_100u"]="cd /home/admin/charon && python3 -u strategies/ds0_compound_100u.py"
)

echo "=== [DS-0] 健康检查 $(date '+%F %T') ===" | tee "$RPT"
echo "--- 进程 ---" | tee -a "$RPT"

DEAD=()
WARN=()
OK=0

for name in "${!PROCS[@]}"; do
  pat="${PROCS[$name]}"
  pid=$(pgrep -f "python.*$pat" | head -1)
  if [ -z "$pid" ]; then
    DEAD+=("$name")
    echo "🔴 $name | 进程缺失 (pattern=$pat)" | tee -a "$RPT"
    continue
  fi

  # CPU% 长时间<0.5% 且 累计<5min CPU 可能卡死
  cpu=$(ps -p "$pid" -o pcpu= 2>/dev/null | tr -d ' ')
  etime=$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ')
  rss_kb=$(ps -p "$pid" -o rss= 2>/dev/null | tr -d ' ')

  # 找对应日志(取最近一个)
  log=$(ls -t $LOG_DIR/${name}.log 2>/dev/null | head -1)
  if [ -z "$log" ]; then
    # 兼容旧路径
    log="$LOG_DIR/${name%.log}.log"
    [ ! -f "$log" ] && log="$LOG_DIR/paper_engine.log"
  fi

  last_line_time=""
  last_line=""
  if [ -f "$log" ]; then
    last_line_time=$(stat -c %y "$log" 2>/dev/null | cut -d. -f1)
    last_line=$(tail -1 "$log" 2>/dev/null | head -c 200)
    # 5分钟没新日志 = 嫌疑
    age_min=$(( ( $(date +%s) - $(stat -c %Y "$log") ) / 60 ))
    # 策略轮询周期可能是1m/5m/15m, 设10min阈值
    if [ "$age_min" -gt 10 ]; then
      WARN+=("$name: 日志陈旧 ${age_min}min")
      echo "🟡 $name | PID=$pid | CPU=${cpu}% | RSS=$((rss_kb/1024))MB | 日志${age_min}min前" | tee -a "$RPT"
    else
      echo "🟢 $name | PID=$pid | CPU=${cpu}% | RSS=$((rss_kb/1024))MB | ${age_min}min前活跃" | tee -a "$RPT"
      OK=$((OK+1))
    fi
  else
    echo "🟡 $name | PID=$pid | CPU=${cpu}% | RSS=$((rss_kb/1024))MB | 日志未找到: $log" | tee -a "$RPT"
    WARN+=("$name: 日志缺失")
  fi

  # 内存爆炸 (>600MB) -> 怀疑泄漏
  if [ "$rss_kb" -gt 600000 ]; then
    WARN+=("$name: RSS=$((rss_kb/1024))MB 内存异常大")
  fi
done

# --- 自动修复 ---
echo "--- 修复 ---" | tee -a "$RPT"
if [ ${#DEAD[@]} -gt 0 ]; then
  echo "🛠 死掉的进程: ${DEAD[*]}" | tee -a "$RPT"
  for d in "${DEAD[@]}"; do
    pat="${PROCS[$d]}"
    cmd="${START_CMDS[$d]:-cd $WORKSPACE && python3 -u $pat}"
    log="$LOG_DIR/${d}.restart.log"
    echo "[$(date '+%T')] 重启 $d ($cmd)" | tee -a "$log"
    cd "$WORKSPACE"
    # 用setsid+nohup启动, 脱离父进程, 防止watchdog被kill时子进程跟着死
    setsid bash -c "$cmd" >> "$log" 2>&1 < /dev/null &
    new_pid=$!
    sleep 2
    if kill -0 "$new_pid" 2>/dev/null; then
      echo "✅ $d 重启成功 PID=$new_pid" | tee -a "$RPT" "$log"
    else
      echo "🔴 $d 重启失败" | tee -a "$RPT" "$log"
    fi
  done
  touch "$ALERT_FLAG"
else
  echo "✅ 无需重启" | tee -a "$RPT"
fi

# --- 摘要 ---
SUMMARY="[DS-0] 心跳 | 🟢${OK}正常"
[ ${#WARN[@]} -gt 0 ] && SUMMARY="$SUMMARY | 🟡告警:${#WARN[@]}(${WARN[*]})"
[ ${#DEAD[@]} -gt 0 ] && SUMMARY="$SUMMARY | 🔴已重启:${#DEAD[@]}(${DEAD[*]})"

echo "$SUMMARY" | tee -a "$RPT"
echo "$SUMMARY"