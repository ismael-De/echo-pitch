"""Hostile judge's-eye QA pass: fresh Chromium profile, visible-UI clicks only, plus API abuse probes.

python scripts/e2e_qa.py [--base URL]
"""
import argparse, json, sys, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright

VOICE = {"en": "en-GB-RyanNeural", "ar": "ar-SA-HamedNeural", "es": "es-ES-AlvaroNeural", "fr": "fr-FR-HenriNeural", "pt": "pt-BR-AntonioNeural"}
EN_WORDS = ["Kick off", "Audio-first", "Producer", "Audit log", "Time", "Line", "Evidence", "Approver", "How to try", "Close", "verified"]
R = {"ok": True, "checks": []}


def check(name, cond, **d):
    R["checks"].append({"name": name, "pass": bool(cond), **d}); R["ok"] &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name, json.dumps(d, ensure_ascii=False)[:300], flush=True)


def http(base, path, method="GET", body=None, headers=None):
    req = urllib.request.Request(base + path, method=method, data=body, headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r: return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def api_probes(base):
    s, b, h = http(base, "/")
    h = {k.lower(): v for k, v in h.items()}
    check("csp_and_nosniff", "frame-ancestors" in h.get("content-security-policy", "") and h.get("x-content-type-options") == "nosniff")
    check("cache_busted_assets", "/static/app.js?v=" in b and "/static/style.css?v=" in b and "no-cache" in h.get("cache-control", ""))
    s, b, _ = http(base, "/api/replays", "POST", b'{"match_id":"../../etc/passwd"}'); check("path_traversal_404", s == 404 and "Traceback" not in b, status=s)
    s, b, _ = http(base, "/api/replays", "POST", b'{bad json'); check("malformed_json_422", s == 422 and "Traceback" not in b, status=s)
    s, b, _ = http(base, "/api/tts", "POST", json.dumps({"text": "x" * 5000}).encode()); check("tts_oversize_422", s == 422, status=s)
    s, b, _ = http(base, "/api/tts", "POST", json.dumps({"text": "hi", "lang": "de"}).encode()); check("tts_bad_lang_422", s == 422, status=s)
    s, b, _ = http(base, "/api/tts", "POST", json.dumps({"text": "<speak>x</speak>' \"><voice name='x'>", "lang": "en"}).encode())
    check("tts_ssml_injection_safe", s in (200, 503) , status=s)
    s, b, _ = http(base, "/api/config"); check("config_no_secrets", s == 200 and not any(k in b.lower() for k in ("key\"", "secret", "password", "token", "endpoint\"")), body=b[:200])
    s, b, _ = http(base, "/api/replays/nope/audit"); check("unknown_replay_404", s == 404 and "Traceback" not in b, status=s)
    s, b, h = http(base, "/api/health", headers={"Origin": "https://evil.example"}); h = {k.lower(): v for k, v in h.items()}
    check("no_wildcard_cors", h.get("access-control-allow-origin") not in ("*", "https://evil.example"), acao=h.get("access-control-allow-origin"))
    import httpx  # one keep-alive connection = one real client IP (the test box's egress IP rotates per connection)
    time.sleep(61)
    with httpx.Client(timeout=20) as c:
        codes = [c.post(base + "/api/tts", json={"text": "rate probe", "lang": "en"}, headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code for i in range(60)]
    check("tts_rate_limited_even_with_spoofed_xff", 429 in codes, first429=codes.index(429) if 429 in codes else None)


def ui(base):
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=user-gesture-required"])
        ctx = b.new_context(); errs, tts = [], []
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        sent = {}
        def onreq(r):
            if r.url.endswith("/api/tts"): sent[id(r)] = time.time(); tts.append((sent[id(r)], json.loads(r.post_data or "{}").get("lang")))
        def onresp(r):
            if r.url.endswith("/api/tts") and r.ok: tts.append((sent.get(id(r.request), 0), "voice:" + (r.headers.get("x-voice") or "")))
        pg.on("request", onreq); pg.on("response", onresp)
        pg.goto(base + "/", wait_until="networkidle")
        check("title_favicon_howto", "Echo Pitch" in pg.title() and pg.locator("link[rel=icon]").count() == 1 and pg.locator("#howto:visible").count() == 1)
        # audit before kickoff: friendly message, not JSON
        pg.click("#auditBtn"); pg.wait_for_timeout(400)
        check("audit_before_match_friendly", pg.locator("#auditModal:visible").count() and "{" not in pg.inner_text("#auditModal"))
        pg.click("#auditClose")
        pg.click("#audioBtn"); pg.click("#startBtn"); pg.wait_for_timeout(1200); pg.click("#startBtn")  # kick off twice
        pg.wait_for_timeout(12000)
        for lang in ["ar", "es", "fr", "pt", "en", "ar"]:  # switch mid-match with audio on
            t0 = time.time(); pg.select_option("#langSel", lang); pg.wait_for_timeout(9000)
            after = [x for x in tts if x[0] > t0 + 0.05]
            langs = {x[1] for x in after if not str(x[1]).startswith("voice:")}; voices = {x[1][6:] for x in after if str(x[1]).startswith("voice:")}
            check(f"lang_switch_{lang}_voice", langs == {lang} and (not voices or voices == {VOICE[lang]}),
                  dir=pg.evaluate("document.documentElement.dir"), langs=sorted(langs), voices=sorted(voices))
            check(f"rtl_{lang}", pg.evaluate("document.documentElement.dir") == ("rtl" if lang == "ar" else "ltr"))
            pg.click("#auditBtn"); pg.wait_for_selector("#auditRows tr", timeout=8000)
            txt = pg.inner_text("#auditModal"); rows = pg.locator("#auditRows tr").count()
            left = [w for w in EN_WORDS if lang != "en" and w in txt and w not in ("Line",)]
            check(f"audit_panel_{lang}", rows > 0 and '"verdict"' not in txt and '{"' not in txt and not left,
                  rows=rows, english_left=left, head=txt[:80])
            pg.screenshot(path=f"/tmp/qa_audit_{lang}.png"); pg.click("#auditClose")
            if lang != "en":
                vis = pg.inner_text("header") + pg.inner_text("#howto") + pg.eval_on_selector_all("header select option:checked", "els => els.map(e => e.textContent).join(' ')")
                check(f"no_english_header_{lang}", not [w for w in ("Kick off", "Audio-first", "Producer", "How to try", "Match", "Speed", "None", "Restart") if w in vis], text=vis[:120])
        # toggle mashing in every order
        for seq in ["audioBtn a11yBtn approvalBtn", "approvalBtn a11yBtn audioBtn", "a11yBtn audioBtn approvalBtn a11yBtn"]:
            for _ in range(5):
                for bt in seq.split(): pg.click("#" + bt, delay=10)
        pg.wait_for_timeout(1500)
        check("mash_state_consistent", all(pg.get_attribute("#" + x, "aria-pressed") in ("true", "false") for x in ("audioBtn", "a11yBtn", "approvalBtn"))
              and pg.evaluate("document.body.classList.contains('a11y')") == (pg.get_attribute("#a11yBtn", "aria-pressed") == "true"))
        # producer approve/reject
        if pg.get_attribute("#approvalBtn", "aria-pressed") != "true": pg.click("#approvalBtn")
        pg.wait_for_timeout(15000)
        ap = pg.locator(".pending .ap:visible").count(); note = pg.inner_text(".producer") if pg.locator(".producer:visible").count() else ""
        check("producer_feedback", ap > 0 or len(note) > 20, approve_buttons=ap)
        if ap:
            pg.locator(".pending .ap:visible").first.click(); pg.wait_for_timeout(600)
            if pg.locator(".pending .rj:visible").count(): pg.locator(".pending .rj:visible").first.click(); pg.wait_for_timeout(600)
            pg.click("#auditBtn"); pg.wait_for_selector("#auditRows tr"); txt = pg.inner_text("#auditModal")
            check("audit_shows_producer_decision", "Approved" in txt or "Rejected" in txt); pg.click("#auditClose")
        # second tab + reload mid-match
        p2 = ctx.new_page(); p2.on("pageerror", lambda e: errs.append("tab2:" + str(e))); p2.goto(base + "/", wait_until="networkidle"); p2.click("#startBtn"); p2.wait_for_timeout(5000)
        check("two_tabs", p2.locator("#ticker li").count() > 0 and pg.locator("#ticker li").count() > 0)
        pg.reload(wait_until="networkidle"); pg.click("#startBtn"); pg.wait_for_timeout(5000)
        check("reload_mid_match", pg.locator("#ticker li").count() > 0)
        # XSS through query params
        p3 = ctx.new_page(); p3.on("dialog", lambda d: errs.append("XSS dialog") or d.dismiss())
        p3.goto(base + "/?lang=<img src=x onerror=alert(1)>&persona=<script>alert(1)</script>&club=\"><svg onload=alert(1)>&voice=';alert(1)//&start=abc", wait_until="networkidle")
        p3.wait_for_timeout(1500); check("xss_query_params", "XSS dialog" not in errs)
        p3.close(); p2.close()
        # slow network
        cdp = ctx.new_cdp_session(pg); cdp.send("Network.enable"); cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 600, "downloadThroughput": 50000, "uploadThroughput": 20000})
        pg.reload(); pg.wait_for_load_state("load", timeout=60000); pg.click("#startBtn"); pg.wait_for_timeout(12000)
        check("slow_network_still_streams", pg.locator("#ticker li").count() > 0)
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        # speech failing -> browser fallback, no crash
        pg.route("**/api/tts", lambda r: r.fulfill(status=502, body="speech failed")); pg.click("#audioBtn"); pg.wait_for_timeout(3000)
        check("speech_failure_no_crash", pg.locator("#ticker li").count() > 0); pg.unroute("**/api/tts")
        real = [e for e in errs if "429" not in e and "502" not in e and "Failed to load resource" not in e]
        check("no_console_errors", not real, errors=real[:4])
        # viewports
        for name, vp in (("mobile", {"width": 390, "height": 844}), ("tablet", {"width": 820, "height": 1180})):
            for lang in ("en", "ar"):
                c2 = b.new_context(viewport=vp, is_mobile=name == "mobile"); q = c2.new_page(); q.goto(base + "/", wait_until="networkidle")
                q.select_option("#langSel", lang); q.click("#startBtn"); q.wait_for_timeout(3000)
                ov = q.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                q.click("#auditBtn"); q.wait_for_timeout(1500)
                box = q.locator("#auditModal .modal-body").bounding_box()
                check(f"{name}_{lang}_layout", ov <= 1 and box and box["width"] <= vp["width"], overflow_px=ov)
                q.screenshot(path=f"/tmp/qa_{name}_{lang}.png", full_page=False); c2.close()
        b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--base", default="https://echo-pitch-web.blackriver-a826d80e.uaenorth.azurecontainerapps.io")
    ap.add_argument("--no-api", action="store_true"); a = ap.parse_args()
    ui(a.base)
    if not a.no_api: api_probes(a.base)
    fails = [c["name"] for c in R["checks"] if not c["pass"]]
    print("ALL_PASS" if not fails else "FAIL " + ", ".join(fails)); sys.exit(0 if not fails else 1)
