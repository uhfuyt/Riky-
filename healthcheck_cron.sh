#!/bin/bash
# 暗黑星火 · 虚拟盘心跳wrapper (供cron调用)
# 正常时静默(空stdout→不汇报), 异常时才推送
# 用ALERT_FLAG或DEAD数组触发

WORKSPACE="/home/admin/charon"
HC="$WORKSPACE/healthcheck_papers.sh"

OUT=$("$HC" 2>&1)
EXIT=$?

# 死掉已重启的关键词
if echo "$OUT" | grep -q "重启"; then
  echo "$OUT"
  exit 0
fi
# 严重告警(>=3个进程日志>10min)也汇报
COUNT_WARN=$(echo "$OUT" | grep -c "日志陈旧")
if [ "$COUNT_WARN" -ge 3 ]; then
  echo "$OUT"
  exit 0
fi
# 否则静默
exit 0