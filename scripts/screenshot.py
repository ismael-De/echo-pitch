"""Headless screenshot of the UI mid-match: python scripts/screenshot.py [url] [out.png] [wait_s]"""
import sys
import time

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/?match=EP-2026-002&speed=60&start=82&club=home&autoplay=1"
out = sys.argv[2] if len(sys.argv) > 2 else "docs/ui.png"
wait = float(sys.argv[3]) if len(sys.argv) > 3 else 9

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    pg.goto(url)
    time.sleep(wait)
    pg.screenshot(path=out, full_page=True)
    b.close()
print(out)
