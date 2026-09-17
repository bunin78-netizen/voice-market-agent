#!/usr/bin/env python3
"""Собирает слайд-презентацию проекта (HTML → PDF через headless Chrome).

Запуск:
    python3 scripts/make_slides.py
    python3 scripts/make_slides.py --video ~/Videos/voice-market-DEMO.mp4 --out ~/voice-slides.pdf

Что делает:
  1. вырезает кадры из демо-видео для слайдов;
  2. рисует 9 слайдов 16:9 в тёмной теме;
  3. печатает PDF через google-chrome --headless.
"""
from __future__ import annotations

import argparse
import base64
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLIDES = ROOT / "tmp" / "slides"
AVATAR = Path("/home/cryptos/.openclaw/media/inbound/"
              "изображение_viber_2026-09-17_02-13-30-288---91bb2f5c-6178-429e-bd4a-6185f0e39af0.jpg")

BOT = "@VoiceMarketAgentBot"
REPO = "github.com/bunin78-netizen/voice-market-agent"


def b64(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    return f"data:{mime};base64,{data}"


def grab_frame(video: Path, t: float, out: Path, width: int = 1600) -> Path | None:
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(video),
         "-frames:v", "1", "-vf", f"scale={width}:-1", str(out)], capture_output=True)
    return out if res.returncode == 0 and out.exists() else None


CSS = """
  @page { size: 1280px 720px; margin: 0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'DejaVu Sans', Arial, sans-serif; background: #0d1117; }
  .slide { width: 1280px; height: 720px; padding: 56px 72px; background: #0d1117;
           color: #c9d1d9; position: relative; page-break-after: always; overflow: hidden; }
  .slide:last-child { page-break-after: auto; }
  h1 { font-size: 54px; color: #f0f6fc; line-height: 1.15; }
  h2 { font-size: 40px; color: #f0f6fc; margin-bottom: 28px; }
  p, li { font-size: 23px; line-height: 1.5; color: #c9d1d9; }
  ul { margin-left: 26px; }
  li { margin-bottom: 12px; }
  .accent { color: #58a6ff; }
  .muted { color: #8b949e; }
  .num { color: #58a6ff; font-weight: bold; }
  .foot { position: absolute; bottom: 26px; left: 72px; font-size: 17px; color: #6e7681; }
  .tag { display: inline-block; padding: 6px 14px; border: 1px solid #30363d; border-radius: 999px;
         font-size: 19px; color: #c9d1d9; margin: 0 8px 10px 0; }
  .cols { display: flex; gap: 40px; align-items: flex-start; }
  .col { flex: 1; }
  .shot { border: 1px solid #30363d; border-radius: 10px; width: 100%; }
  .pipe { display: flex; align-items: center; gap: 12px; margin: 18px 0; flex-wrap: wrap; }
  .box { border: 1px solid #30363d; border-radius: 10px; padding: 16px 18px; font-size: 20px;
         background: #161b22; }
  .box.hl { border-color: #58a6ff; color: #f0f6fc; }
  .arrow { color: #58a6ff; font-size: 26px; }
  .avatar { width: 132px; height: 132px; border-radius: 50%; border: 3px solid #30363d; object-fit: cover; }
  .big { font-size: 64px; color: #f0f6fc; }
  .note { margin-top: 22px; padding: 18px 22px; border-left: 4px solid #58a6ff;
          background: #161b22; border-radius: 8px; font-size: 21px; }
"""


def slides_html(frames: dict[float, Path | None]) -> str:
    shot_note = b64(frames[48]) if frames.get(48) else ""
    shot_chart = b64(frames[120]) if frames.get(120) else ""
    avatar = b64(AVATAR) if AVATAR.exists() else ""

    def img(src: str, caption: str = "") -> str:
        if not src:
            return ""
        cap = f'<p class="muted" style="font-size:17px;margin-top:10px">{caption}</p>' if caption else ""
        return f'<img class="shot" src="{src}">{cap}'

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<section class="slide">
  <div style="text-align:center; padding-top:70px">
    {'<img class="avatar" src="' + avatar + '">' if avatar else ''}
    <h1 style="margin-top:34px">Voice Market Agent</h1>
    <p class="accent" style="font-size:29px; margin-top:16px">A voice-first market copilot for Telegram</p>
    <p class="muted" style="margin-top:26px; font-size:22px">
      AssemblyAI · LLM tool calling · ElevenLabs · Binance API
    </p>
    <p style="margin-top:34px; font-size:22px">
      Bot <span class="accent">{BOT}</span> &nbsp;·&nbsp; Code <span class="accent">{REPO}</span>
    </p>
  </div>
  <p class="foot">AssemblyAI Voice Agent Hackathon · September 2026</p>
</section>

<section class="slide">
  <h2>The problem</h2>
  <p>Market updates are built for <span class="accent">eyes and hands</span>: a terminal, a chart, a list of indicators.</p>
  <ul style="margin-top:24px">
    <li>When your hands are busy — driving, cooking, working out — those minutes are simply lost.</li>
    <li>Chat assistants still expect typing: a keyboard is the busiest interface we own.</li>
    <li>Voice is the lowest-friction channel we already carry, and it is barely used for market data.</li>
  </ul>
  <div class="note">The question is not "how do we show a chart faster" — it is
    <span class="accent">how do we answer when nobody can look at the screen at all</span>.</div>
  <p class="foot">Voice Market Agent</p>
</section>

<section class="slide">
  <h2>The solution</h2>
  <div class="cols">
    <div class="col">
      <ul>
        <li>Send a <span class="accent">voice message</span> to the bot — in Telegram, on any device.</li>
        <li>The agent answers <span class="accent">out loud</span>, adds the numbers as text, and builds a chart on demand.</li>
        <li>No app to install, no new habit to learn: a voice note is already a familiar gesture.</li>
      </ul>
      <div class="note">Questions we tested end to end:<br>
        “What is Bitcoin doing today?”<br>
        “Show me a daily Ether chart”<br>
        “And what about market sentiment?”</div>
    </div>
    <div class="col">{img(shot_note, "A voice note in, a voice answer out — plus the numbers in writing")}</div>
  </div>
  <p class="foot">Voice Market Agent</p>
</section>

<section class="slide">
  <h2>How it works</h2>
  <div class="pipe">
    <div class="box">Telegram voice (OGG/Opus)</div><span class="arrow">→</span>
    <div class="box">ffmpeg → WAV 16 kHz</div><span class="arrow">→</span>
    <div class="box hl">AssemblyAI STT</div><span class="arrow">→</span>
    <div class="box hl">LLM + tool calling</div>
  </div>
  <div class="pipe">
    <div class="box">market data (Binance)</div><span class="arrow">→</span>
    <div class="box">indicators &amp; chart</div><span class="arrow">→</span>
    <div class="box hl">ElevenLabs TTS</div><span class="arrow">→</span>
    <div class="box">voice answer + text + chart</div>
  </div>
  <p style="margin-top:18px">Every step is a small module in the open-source repo:
    <span class="muted">stt.py, llm.py, market.py, tools.py, agent.py, tts.py, bot.py</span>.</p>
  <div class="note">Latency on live keys: recognition <span class="num">~6 s</span> →
    agent <span class="num">~4 s</span> → speech <span class="num">~1 s</span>.</div>
  <p class="foot">Voice Market Agent</p>
</section>

<section class="slide">
  <h2>How AssemblyAI is used</h2>
  <ul>
    <li><span class="accent">Speech-to-text</span> with <span class="accent">universal-3-5-pro</span>
      (fallback to universal-2) on short voice notes from a messenger.</li>
    <li><span class="accent">keyterms_prompt</span> glossary — RSI, Bollinger Bands, timeframe, price, volume —
      so domain vocabulary survives compression and quiet speech.</li>
    <li>Language pinned to Russian for short clips: auto-detection on 3–4 second audio
      produced wrong-language transcripts in testing.</li>
    <li>Polling API wrapped in its own retry loop; the rest of the pipeline stays provider-agnostic
      (local Whisper is kept as a development fallback).</li>
  </ul>
  <div class="note">Why it matters: “what is Bitcoin doing <span class="accent">today</span>” and
    “<span class="accent">daily</span> Ether chart” must both transcribe correctly — the whole agent
    depends on that text.</div>
  <p class="foot">Voice Market Agent</p>
</section>

<section class="slide">
  <h2>The agent decides — nothing is pre-scripted</h2>
  <p>The model receives tool definitions and picks them from the wording of the question:</p>
  <div style="margin-top:24px">
    <span class="tag">get_price</span>
    <span class="tag">get_indicators — SMA20, RSI(14), Bollinger Bands, volume</span>
    <span class="tag">get_market_snapshot</span>
    <span class="tag">get_fear_greed</span>
    <span class="tag">make_chart</span>
  </div>
  <ul style="margin-top:28px">
    <li>A question about the day pulls daily candles; a question about the chart renders one in the moment.</li>
    <li>Tool errors are returned to the model as data, so it explains a failure instead of the bot dying.</li>
    <li>Answered in 2–3 short spoken sentences, with the detail kept in writing for re-reading.</li>
  </ul>
  <p class="foot">Voice Market Agent</p>
</section>

<section class="slide">
  <h2>Answer in two layers</h2>
  <div class="cols">
    <div class="col">
      <ul>
        <li><span class="accent">Spoken part</span> — two or three sentences, no numbers read aloud as a list.</li>
        <li><span class="accent">Written part</span> — price, SMA20, RSI, Bollinger Bands, volume, in text.</li>
        <li>Rationale: listening and reading are different jobs — the voice carries the verdict, the text carries the precision.</li>
        <li>Voice is capped by sentence boundaries, so it never sounds cut off mid-thought.</li>
      </ul>
    </div>
    <div class="col">{img(shot_chart, "Charts are rendered on demand by the agent, straight from exchange candles")}</div>
  </div>
  <p class="foot">Voice Market Agent</p>
</section>

<section class="slide">
  <h2>Engineering notes</h2>
  <ul>
    <li>Messenger sends can time out: long request timeouts plus retries with backoff — a dropped
      reply is worse than a slow one.</li>
    <li>Text-to-speech goes straight to the REST endpoint with its own retries; the CLI wrapper was
      unreliable and is kept only as a fallback.</li>
    <li>Responses are split into a spoken part and written detail, so the voice never reads a wall of numbers.</li>
    <li>The demo itself is reproducible: silent screen capture + generated narration + the bot's own
      voice archive, aligned to logged events, with subtitle timings taken from the finished file.</li>
  </ul>
  <div class="note">Everything in the presentation is verifiable in the repository — same code that runs the bot.</div>
  <p class="foot">Voice Market Agent</p>
</section>

<section class="slide">
  <h2>Links &amp; what is next</h2>
  <ul>
    <li>Bot: <span class="accent">{BOT}</span></li>
    <li>Code (MIT): <span class="accent">{REPO}</span></li>
    <li>Video demo: three spoken questions, three spoken answers, two generated charts</li>
  </ul>
  <p style="margin-top:26px" class="muted">Next steps: portfolio-aware answers, streaming recognition
    for lower latency, more instruments and exchanges.</p>
  <p class="big" style="margin-top:44px">Ask the market. By voice.</p>
  <p class="foot">Voice Market Agent · AssemblyAI Voice Agent Hackathon</p>
</section>

</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(Path.home() / "Videos" / "voice-market-DEMO.mp4"))
    ap.add_argument("--out", default=str(Path.home() / "voice-market-slides.pdf"))
    args = ap.parse_args()

    SLIDES.mkdir(parents=True, exist_ok=True)
    video = Path(args.video).expanduser()
    frames: dict[float, Path | None] = {}
    if video.exists():
        for t in (48, 120):
            frames[t] = grab_frame(video, t, SLIDES / f"frame_{t}.png")
    else:
        print(f"⚠️  нет видео {video} — слайды соберутся без скриншотов")

    html_path = SLIDES / "slides.html"
    html_path.write_text(slides_html(frames), encoding="utf-8")

    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        print("❌ не найден google-chrome — HTML лежит здесь: " + str(html_path))
        return 1

    out = Path(args.out).expanduser()
    res = subprocess.run([
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        "--no-pdf-header-footer", f"--print-to-pdf={out}", html_path.as_uri(),
    ], capture_output=True, text=True, timeout=180)
    if not out.exists():
        print("❌ Chrome не собрал PDF:\n", (res.stderr or res.stdout)[:500])
        return 1
    print(f"✅ презентация: {out} ({out.stat().st_size // 1024} КБ)")
    print(f"   HTML: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
