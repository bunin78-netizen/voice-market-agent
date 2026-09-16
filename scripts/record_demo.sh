#!/bin/bash
# Запись демо-видео: экран (ffmpeg/x11grab) + микрофон (parec) → один MP4.
#
# Запуск:            bash scripts/record_demo.sh
# Остановка:         Ctrl+C (файл соберётся автоматически)
# Проверка за 6 с:   DURATION=6 bash scripts/record_demo.sh
#
# Переопределяемое:
#   AREA=1920x1080+1360+0   область экрана (X Y — левый верхний угол)
#   MIC=<имя источника>     микрофон (см. `pactl list short sources` / `pw-cli ls Source`)
#   OUT=/путь/файл.mp4      куда писать
#   FPS=25                  частота кадров

set -u
cd "$(dirname "$0")/.." || exit 1

AREA="${AREA:-1920x1080+1360+0}"
MIC="${MIC:-alsa_input.pci-0000_00_1f.3.analog-stereo}"
FPS="${FPS:-25}"
DURATION="${DURATION:-}"
OUT_DIR="${OUT_DIR:-$HOME/Videos}"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="${OUT:-$OUT_DIR/voice-market-demo-$STAMP.mp4}"
TMP_DIR=$(mktemp -d)
VIDEO="$TMP_DIR/video.mp4"
AUDIO="$TMP_DIR/audio.wav"

for tool in ffmpeg parec; do
  command -v "$tool" >/dev/null || { echo "❌ не найден $tool"; exit 1; }
done

cleanup() {
  # гасим дочерние процессы захвата
  [ -n "${VPID:-}" ] && kill "$VPID" 2>/dev/null
  [ -n "${APID:-}" ] && kill "$APID" 2>/dev/null
  wait "$VPID" 2>/dev/null
  wait "$APID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "🎬 область: $AREA @ ${FPS}fps"
echo "🎙 микрофон: $MIC"
echo "💾 результат: $OUT"
echo
echo "Запись начнётся через 5 секунд — переключись на окно Telegram."
sleep 5
echo "▶ ЗАПИСЬ (Ctrl+C — стоп)"

TIME_FLAG=()
[ -n "$DURATION" ] && TIME_FLAG=(-t "$DURATION")

ffmpeg -hide_banner -loglevel error \
  -f x11grab -framerate "$FPS" -video_size "${AREA%%+*}" -i ":0.0+$(echo "$AREA" | cut -d+ -f2),$(echo "$AREA" | cut -d+ -f3)" \
  -c:v libx264 -preset ultrafast -crf 26 -pix_fmt yuv420p "${TIME_FLAG[@]}" "$VIDEO" &
VPID=$!

parec --device="$MIC" --format=s16le --rate=48000 --channels=1 --file-format=wav "$AUDIO" &
APID=$!

if [ -n "$DURATION" ]; then
  wait "$VPID" 2>/dev/null
else
  echo "   пишу… нажми Ctrl+C, когда закончишь"
  wait "$VPID" 2>/dev/null
fi
cleanup >/dev/null 2>&1
trap - EXIT INT TERM

echo
echo "⏹ запись остановлена, собираю файл…"
ffmpeg -hide_banner -loglevel error -y \
  -i "$VIDEO" -i "$AUDIO" \
  -c:v copy -c:a aac -b:a 160k -shortest "$OUT" || {
    echo "⚠️ звук не подхватился — сохраняю только видео"
    cp "$VIDEO" "$OUT"
  }

rm -rf "$TMP_DIR"
if [ -f "$OUT" ]; then
  SIZE=$(du -h "$OUT" | cut -f1)
  DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT" 2>/dev/null | cut -d. -f1)
  echo "✅ готово: $OUT ($SIZE, ${DUR}s)"
  echo "   проверь звук:  ffplay -autoexit \"$OUT\""
else
  echo "❌ файл не создан"
  exit 1
fi
