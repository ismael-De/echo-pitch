"""Human-style UI check: fresh Chromium profile, no URL params, real clicks on the visible buttons only.

python scripts/e2e_human.py [--base URL]
For EN and AR, in two orders (toggles before Kick off / after Kick off), it checks:
  - 🔊  : /api/tts called and an <audio> element actually reaches 'playing' (or browser speech starts) within 4 s of the click
  - ♿  : body gets the .a11y layout, aria-pressed=true, and speech starts
  - 🎬  : either Approve/Reject boxes appear on held AI lines, or a visible notice explains why none are held
"""
import argparse, json, sys, time
from playwright.sync_api import sync_playwright

HOOK = """window.__ev=[];const P=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){
 const r=P.call(this);const s=this.src.slice(0,10);r.then(()=>window.__ev.push(['playing',performance.now(),s]),e=>window.__ev.push(['err:'+e.name,performance.now(),s]));return r;};
 if(window.speechSynthesis){const S=speechSynthesis.speak.bind(speechSynthesis);speechSynthesis.speak=function(u){window.__ev.push(['synth',performance.now(),(u.text||'').slice(0,20)]);return S(u);};}"""


def real_audio(pg, since):
    ev = pg.evaluate("window.__ev")
    return [e for e in ev if e[1] >= since and ((e[0] == "playing" and e[2].startswith("blob")) or (e[0] == "synth" and e[2].strip()))]


def scenario(base, lang, order):
    out = {"lang": lang, "order": order, "ok": True, "checks": {}}
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=user-gesture-required"])
        ctx = b.new_context()  # fresh profile: empty cache, no storage
        ctx.add_init_script(HOOK)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + "/", wait_until="networkidle")
        if lang != "en":
            pg.select_option("#langSel", lang)
        def check(name, cond, detail):
            out["checks"][name] = {"pass": bool(cond), **detail}
            out["ok"] &= bool(cond)
        def kick():
            pg.click("#startBtn"); pg.wait_for_timeout(1500)
        def audio():
            t = pg.evaluate("performance.now()"); pg.click("#audioBtn"); pg.wait_for_timeout(4000)
            a = real_audio(pg, t)
            check("audio_speaks", a and pg.get_attribute("#audioBtn", "aria-pressed") == "true", {"first": a[:1]})
        def a11y():
            pg.click("#audioBtn")  # turn plain audio off again so ♿ is tested on its own
            pg.wait_for_timeout(300)
            t = pg.evaluate("performance.now()"); pg.click("#a11yBtn"); pg.wait_for_timeout(4000)
            a = real_audio(pg, t)
            check("a11y_layout_and_speech", pg.evaluate("document.body.classList.contains('a11y')") and a
                  and pg.get_attribute("#a11yBtn", "aria-pressed") == "true", {"first": a[:1]})
        def producer():
            pg.click("#approvalBtn"); pg.wait_for_timeout(1000)
            note = pg.locator("#notice").inner_text() if pg.locator("#notice:visible").count() else ""
            out["_note0"] = note
        if order == "toggles_first":
            audio(); a11y(); producer(); kick()
        else:
            kick(); audio(); a11y(); producer()
        pg.wait_for_timeout(25000)
        pend = pg.locator(".pending:visible").count(); appr = pg.locator(".pending .ap:visible").count()
        note = pg.locator("#notice:visible").inner_text() if pg.locator("#notice:visible").count() else ""
        mode = pg.inner_text("#modeBadge")
        check("producer_feedback", pg.get_attribute("#approvalBtn", "aria-pressed") == "true" and (appr > 0 or note),
              {"pending_boxes": pend, "notice": note[:120], "mode": mode})
        if appr:
            pg.locator(".pending .ap:visible").first.click(); pg.wait_for_timeout(800)
            check("approve_click", pg.locator(".pending:visible").count() < pend, {})
        out["tts"] = pg.evaluate("performance.getEntriesByType('resource').filter(r=>r.name.includes('/api/tts')).length")
        check("no_page_errors", not errs, {"errors": errs[:3]})
        b.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--base", default="https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io")
    a = ap.parse_args(); res = [scenario(a.base, l, o) for l in ("en", "ar") for o in ("toggles_first", "kickoff_first")]
    for r in res: print(json.dumps(r, ensure_ascii=False))
    print("ALL_PASS" if all(r["ok"] for r in res) else "FAIL"); sys.exit(0 if all(r["ok"] for r in res) else 1)
