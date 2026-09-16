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

# лог не стираем: он нужен для привязки озвучки к событиям
if [ -f "$LOG" ]; then
  SIZE=$(stat -c%s "$LOG" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 2000000 ]; then mv "$LOG" "$LOG.prev"; else cp -f "$LOG" "$LOG.prev"; fi
fi
: > "$LOG.new"
nohup setsid python3 -m src.bot >> "$LOG.new" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
sleep 8
echo "новый pid: $(cat "$PIDFILE")"
cat "$LOG" "$LOG.new" 2>/dev/null | tail -3; cat "$LOG.new" 2>/dev/null >> "$LOG"; : > "$LOG.new"
