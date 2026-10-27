"""Real-browser audio check: click 🔊, kick off, and record /api/tts calls and <audio> play() outcomes.

python scripts/e2e_audio.py [--base URL] [--lang en ar]   (needs Playwright + Chromium)
Uses Chromium's strict --autoplay-policy=user-gesture-required so autoplay blocking is caught.
"""
import argparse
import json
import sys
import time

from playwright.sync_api import sync_playwright

HOOK = """()=>{window.__ev=[];const P=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){
 const t=performance.now();const r=P.call(this);window.__ev.push(['play',t]);
 r.then(()=>window.__ev.push(['playing',performance.now()]),e=>window.__ev.push(['error:'+e.name,performance.now()]));return r;};}"""


def run(base, lang, secs):
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=user-gesture-required"])
        pg = b.new_page()
        tts, errs = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.on("response", lambda r: "/api/tts" in r.url and tts.append(
            (round(time.time() - t0, 2), r.status, r.headers.get("x-voice"))))
        pg.goto(f"{base}/?match=EP-2026-002&speed=30&lang={lang}", wait_until="networkidle")
        pg.evaluate(HOOK)
        t0 = time.time()
        start = pg.evaluate("performance.now()")
        pg.click("#audioBtn")
        pg.click("#startBtn")
        pg.wait_for_timeout(secs * 1000)
        ev = pg.evaluate("window.__ev")
        b.close()
    playing = [round((t - start) / 1000, 2) for k, t in ev if k == "playing"]
    blocked = [k for k, _ in ev if k == "error:NotAllowedError"]
    return {"lang": lang, "tts_calls": len(tts), "tts_ok": sum(s == 200 for _, s, _ in tts),
            "voices": sorted({v for *_, v in tts if v}), "playing_events": len(playing),
            "first_speech_s": playing[1] if len(playing) > 1 else None,  # playing[0] is the silent unlock "blocked": len(blocked), "page_errors": errs[:5]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io")
    ap.add_argument("--lang", nargs="+", default=["en", "ar"])
    ap.add_argument("--secs", type=int, default=20)
    a = ap.parse_args()
    res = [run(a.base, lg, a.secs) for lg in a.lang]
    print(json.dumps(res, ensure_ascii=False))
    ok = all(r["playing_events"] >= 3 and r["blocked"] == 0 and r["first_speech_s"] is not None
             and r["first_speech_s"] < 5 and not r["page_errors"] for r in res)
    sys.exit(0 if ok else 1)
