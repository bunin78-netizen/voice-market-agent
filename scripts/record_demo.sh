#!/bin/bash
# Запись демо-видео: экран (ffmpeg/x11grab) + звук (parec) → один MP4.
#
# Запуск:            bash scripts/record_demo.sh
# Остановка:         Ctrl+C (один раз! файл соберётся сам)
# Проверка за 6 с:   DURATION=6 bash scripts/record_demo.sh
#
# Переопределяемое:
#   AREA=1920x1080+1360+0   область экрана (ширинаxвысота+X+Y)
#   MIC=<источник>          что писать: микрофон или монитор звуковой карты
#   OUT=/путь/файл.mp4      куда положить результат
#   FPS=25                  частота кадров
#
# Почему видео пишется в MKV, а не сразу в MP4: у MP4 индекс (moov) пишется в конце,
# и если процесс убить — файл остаётся нечитаемым. MKV переживает обрыв.

set -u
cd "$(dirname "$0")/.." || exit 1

# AREA=auto — найти окно Telegram и записать именно его
detect_area() {
  command -v xwininfo >/dev/null || return 1
  DISPLAY="${DISPLAY:-:0}" xwininfo -root -tree 2>/dev/null \
    | grep -i 'telegram' | grep -vi 'media viewer' | grep -vi 'selection owner' \
    | sed -n 's/.*)  \([0-9]\{3,\}\)x\([0-9]\{3,\}\)+\([-0-9]\+\)+\([-0-9]\+\)  .*/\1 \2 \3 \4/p' \
    | awk '{ if ($1*$2 > best) { best=$1*$2; w=$1; h=$2; x=$3; y=$4 } } END { if (best > 100000) printf "%dx%d+%d+%d", w, h, x, y }'
}

AREA="${AREA:-auto}"
if [ "$AREA" = "auto" ]; then
  DETECTED=$(detect_area)
  if [ -n "$DETECTED" ]; then
    AREA="$DETECTED"
    echo "🔎 окно Telegram найдено: $AREA"
    HGT=$(echo "$AREA" | sed 's/x[0-9]*+/x/; s/x\([0-9]*\).*/\1/')
    if [ "${HGT:-0}" -lt 900 ]; then
      echo "⚠️  окно ниже 1080p — на YouTube текст будет мягче."
      echo "   Перетащи окно Telegram на монитор 1920x1080 и разверни его — тогда запись будет резкой."
    fi
  else
    AREA="1920x1080+1360+0"
    echo "⚠️  окно Telegram не найдено — пишу основной монитор: $AREA"
    echo "   (задай вручную: AREA=1024x1280+3280+0 bash scripts/record_demo.sh)"
  fi
fi
MIC="${MIC:-alsa_output.pci-0000_00_1f.3.analog-stereo.monitor}"
FPS="${FPS:-25}"
CRF="${CRF:-16}"   # ниже = чётче текст: 16 для интерфейсов, 14 если нужен максимум
DURATION="${DURATION:-}"
OUT_DIR="${OUT_DIR:-$HOME/Videos}"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="${OUT:-$OUT_DIR/voice-market-demo-$STAMP.mp4}"
WORK="${WORK:-$OUT_DIR/.work-$STAMP}"
mkdir -p "$WORK"
VIDEO="$WORK/screen.mkv"
AUDIO="$WORK/sound.wav"

for tool in ffmpeg parec ffprobe; do
  command -v "$tool" >/dev/null || { echo "❌ не найден $tool"; exit 1; }
done

STOPPING=0
VPID=""; APID=""

shutdown() {
  # повторные Ctrl+C игнорируем — иначе убьём сведение
  if [ "$STOPPING" = "1" ]; then return; fi
  STOPPING=1
  echo
  echo "⏹ останавливаю захват…"
  # SIGINT даёт ffmpeg дописать контейнер корректно
  [ -n "$APID" ] && kill -INT "$APID" 2>/dev/null
  [ -n "$VPID" ] && kill -INT "$VPID" 2>/dev/null
  local waited=0
  while [ -n "$VPID" ] && kill -0 "$VPID" 2>/dev/null && [ "$waited" -lt 15 ]; do
    sleep 1; waited=$((waited + 1))
  done
  [ -n "$VPID" ] && kill -0 "$VPID" 2>/dev/null && kill "$VPID" 2>/dev/null
  wait "$VPID" 2>/dev/null
  wait "$APID" 2>/dev/null
}
trap shutdown INT

echo "🎬 область: $AREA @ ${FPS}fps"
echo "🎙 звук:    $MIC"
echo "💾 результат: $OUT"
echo
echo "Запись начнётся через 5 секунд — переключись на окно Telegram."
sleep 5
echo "▶ ЗАПИСЬ. Говорить не нужно. Ctrl+C — стоп (один раз!)."
date +%s.%N > "$OUT.start" 2>/dev/null || true

TIME_FLAG=()
[ -n "$DURATION" ] && TIME_FLAG=(-t "$DURATION")

W="${AREA%%+*}"
REST="${AREA#*+}"
X="${REST%%+*}"
Y="${REST##*+}"

ffmpeg -hide_banner -loglevel error -stats_period 1 \
  -f x11grab -framerate "$FPS" -video_size "$W" -i ":0.0+$X,$Y" \
  -c:v libx264 -preset veryfast -crf "$CRF" -pix_fmt yuv420p \
  "${TIME_FLAG[@]}" "$VIDEO" &
VPID=$!

parec --device="$MIC" --format=s16le --rate=48000 --channels=1 --file-format=wav "$AUDIO" &
APID=$!

if [ -n "$DURATION" ]; then
  wait "$VPID" 2>/dev/null
  shutdown >/dev/null 2>&1
  trap - INT
else
  while kill -0 "$VPID" 2>/dev/null; do sleep 1; done
fi

sleep 1
trap - INT

# --- проверки перед сведением
VID_OK=1
ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 "$VIDEO" >/dev/null 2>&1 || VID_OK=0
AUD_OK=1
[ -s "$AUDIO" ] && ffprobe -v error -show_entries format=duration -of csv=p=0 "$AUDIO" >/dev/null 2>&1 || AUD_OK=0

if [ "$VID_OK" = "0" ]; then
  echo "❌ видео не записалось. Что было:"
  echo "   • окно Telegram на другом мониторе? см. docs/demo-voiceover.md (AREA=...)"
  echo "   • сессия X11 недоступна (проверь echo \$DISPLAY)"
  echo "   черновик файлов оставлен в $WORK"
  exit 1
fi

VDUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$VIDEO" 2>/dev/null | cut -d. -f1)
echo "⏹ захват остановлен: видео ${VDUR}s, звук $([ "$AUD_OK" = "1" ] && echo есть || echo НЕТ)"

if [ "$AUD_OK" = "1" ]; then
  LEVEL=$(ffmpeg -hide_banner -i "$AUDIO" -af volumedetect -f null - 2>&1 \
    | grep max_volume | sed 's/.*max_volume: //; s/ dB//')
  if [ -n "$LEVEL" ] && awk "BEGIN{exit !($LEVEL < -70)}"; then
    echo "⚠️  звук в записи почти тишина (максимум $LEVEL dB)."
    echo "   проверь, что звук системы идёт на тот же выход: wpctl status  (строка со звёздочкой — активный)"
    echo "   или задай MIC=<другой monitor> bash scripts/record_demo.sh"
  else
    echo "   уровень звука: максимум ${LEVEL:-?} dB"
  fi
  ffmpeg -hide_banner -loglevel error -y -i "$VIDEO" -i "$AUDIO" \
    -c:v copy -c:a aac -b:a 160k -movflags +faststart -shortest "$OUT"
else
  echo "⚠️  звука нет — сохраняю только видео"
  ffmpeg -hide_banner -loglevel error -y -i "$VIDEO" -c:v copy -movflags +faststart "$OUT"
fi

if ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" >/dev/null 2>&1 && [ -s "$OUT" ]; then
  SIZE=$(du -h "$OUT" | cut -f1)
  DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT" | cut -d. -f1)
  echo "✅ готово: $OUT ($SIZE, ${DUR}s)"
  echo "   посмотреть: ffplay -autoexit \"$OUT\""
  rm -rf "$WORK"
else
  echo "❌ сведение не удалось. Исходники целы: $WORK"
  echo "   соберём вручную: ffmpeg -i \"$VIDEO\" -i \"$AUDIO\" -c:v copy -c:a aac out.mp4"
  exit 1
fi
