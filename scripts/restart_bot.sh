#!/bin/bash
# Перезапуск Voice Market Agent: гасит прошлый процесс по pidfile и поднимает новый.
# Запускать так:  bash scripts/restart_bot.sh
cd "$(dirname "$0")/.." || exit 1
PIDFILE=tmp/bot.pid
LOG=tmp/bot.log

if [ -f "$PIDFILE" ]; then
  OLD=$(cat "$PIDFILE")
  if kill -0 "$OLD" 2>/dev/null; then
    kill "$OLD" && echo "остановлен старый процесс $OLD"
    sleep 2
  fi
fi

# подстраховка: ищем осиротевшие процессы по имени модуля
for p in $(pgrep -f 'python3 -m src\.bot' 2>/dev/null); do
  [ "$p" != "$$" ] && kill "$p" 2>/dev/null && echo "добит $p"
done
sleep 1

: > "$LOG"
nohup setsid python3 -m src.bot >> "$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
sleep 8
echo "новый pid: $(cat "$PIDFILE")"
tail -3 "$LOG"
