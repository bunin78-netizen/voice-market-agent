#!/bin/bash
# Предполётная проверка перед записью демо: всё ли готово к дублю.
# Запуск:  bash scripts/demo_preflight.sh

cd "$(dirname "$0")/.." || exit 1
OK="✅"; BAD="❌"

echo "=== Проверка перед записью демо ==="
echo

# 1. бот
PID=$(pgrep -f 'python3 -m src\.bot' | head -1)
if [ -n "${PID:-}" ]; then
  echo "$OK бот запущен (pid $PID)"
else
  echo "$BAD бот не запущен — подними: bash scripts/restart_bot.sh"
fi

# 2. ключи
python3 - <<'PY'
import sys
sys.path.insert(0, '.')
from src import config, tts
checks = [
    ("Telegram-токен", bool(config.TELEGRAM_BOT_TOKEN)),
    ("AssemblyAI-ключ", bool(config.ASSEMBLYAI_API_KEY)),
    ("LLM (DeepSeek/OpenRouter)", bool(config.DEEPSEEK_API_KEY or config.OPENROUTER_API_KEY)),
    ("голос ElevenLabs", tts.available()),
]
for name, ok in checks:
    print(("✅ " if ok else "❌ ") + name)
PY

# 3. сеть до внешних сервисов
for url in https://api.assemblyai.com/v2/transcript https://api.elevenlabs.io/v1/voices https://api.binance.com/api/v3/ping; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url")
  case "$url" in
    *assemblyai*) name="AssemblyAI" ;;
    *elevenlabs*) name="ElevenLabs" ;;
    *) name="Binance" ;;
  esac
  if [ "$code" = "200" ] || [ "$code" = "401" ] || [ "$code" = "405" ]; then
    echo "$OK $name доступен (HTTP $code)"
  else
    echo "$BAD $name → HTTP $code"
  fi
done

# 4. прогреваем пайплайн, чтобы первый дубль отвечал быстро
echo
echo "…прогрев пайплайна (один запрос к модели и инструментам)"
python3 - <<'PY'
import sys, time
sys.path.insert(0, '.')
from src.agent import answer
t0 = time.time()
res = answer("Кратко: что с биткоином на часовом?")
print(f"✅ прогрев за {time.time()-t0:.1f}c | инструменты: {res.trace}")
PY

echo
echo "Вопросы для дубля:"
cat <<'EOT'
  1) голосом:  «Что с биткоином на четырёхчасовом?»
  2) голосом:  «Покажи график эфира за день»
  3) голосом:  «А что по настроению рынка?»
EOT
echo
echo "Запись:  bash scripts/record_demo.sh   (стоп — Ctrl+C)"
