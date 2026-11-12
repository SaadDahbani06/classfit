"""Record the 29-second pitch demo of the real, running website as a 1080p MP4.

    pip install playwright imageio-ffmpeg && playwright install chromium
    python scripts/record_demo.py

Writes "final product/ClassFit Demo (no heatmap).mp4". It starts the site itself, clicks
through it in a real browser and adds a cursor on top of the page, so
every score in the video comes from the engine. Re-run it whenever the site or the
demo data changes. The video has no sound: it is made to be talked over.
"""

from __future__ import annotations

import base64
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "final product" / "ClassFit Demo (no heatmap).mp4"
PORT = 8598
FPS = 30
LENGTH = 29.0  # seconds
# 1440x810 at this scale is exactly 1920x1080, so text is rendered sharp rather than upscaled.
VIEWPORT = {"width": 1440, "height": 810}
SCALE = 1920 / 1440

OVERLAY_JS = """(fox) => {
  const style = document.createElement('style');
  style.textContent = `
    [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
    #demo-cursor { position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 99999; pointer-events: none;
      background: #fff; clip-path: polygon(8% 0, 8% 84%, 30% 64%, 45% 98%, 60% 91%, 45% 58%, 74% 58%);
      filter: drop-shadow(0 2px 3px rgba(0, 0, 0, .65)); }
    #demo-cursor-edge { position: fixed; left: 0; top: 0; width: 26px; height: 26px; z-index: 99998; pointer-events: none;
      background: #190408; clip-path: polygon(0 -8%, 0 100%, 28% 76%, 42% 108%, 68% 96%, 53% 64%, 92% 64%); }
    #demo-ripple { position: fixed; width: 54px; height: 54px; margin: -27px; border-radius: 50%; z-index: 99997; opacity: 0;
      pointer-events: none; border: 4px solid #FF5A6E; }
    #demo-ripple.go { animation: demo-ripple 480ms ease-out; }
    @keyframes demo-ripple { from { opacity: 1; transform: scale(.3); } to { opacity: 0; transform: scale(1.2); } }
    #demo-end { position: fixed; inset: 0; z-index: 100000; display: flex; flex-direction: column; align-items: center;
      justify-content: center; text-align: center; opacity: 0; pointer-events: none; transition: opacity 600ms ease; color: #fff;
      background: radial-gradient(70% 90% at 12% 0%, #7E0A1D 0%, transparent 62%),
        radial-gradient(60% 90% at 100% 100%, #5C0716 0%, transparent 65%), #190408; }
    #demo-end.on { opacity: 1; }
    #demo-end img { width: 92px; height: 92px; filter: drop-shadow(0 2px 14px rgba(255, 90, 110, .5)); }
    #demo-end h2 { font: 800 92px/1 'Bricolage Grotesque', sans-serif; letter-spacing: -.035em; margin: 12px 0 0; padding: 0; color: #fff; }
    #demo-end p { font: 750 38px/1.2 'Bricolage Grotesque', sans-serif; letter-spacing: -.02em; margin: 18px 0 0; }
    #demo-end p em { font-style: normal; color: #FF5A6E; }
    #demo-end small { font: 500 16px/1.4 Inter, sans-serif; color: #E8CCD4; margin-top: 30px; }`;
  document.head.appendChild(style);
  document.body.insertAdjacentHTML('beforeend', `
    <div id="demo-ripple"></div><div id="demo-cursor-edge"></div><div id="demo-cursor"></div>
    <div id="demo-end"><img alt="" src="${fox}"><h2>ClassFit</h2>
      <p>Same course. Different experience. <em>Find your fit.</em></p>
      <small>Prototype with fictional demo data. Working name; student project, not affiliated with Marist University.</small></div>`);
  const place = (e) => { for (const id of ['demo-cursor', 'demo-cursor-edge'])
    document.getElementById(id).style.transform = `translate(${e.clientX}px, ${e.clientY}px)`; };
  window.addEventListener('mousemove', place, true);
  window.addEventListener('mousedown', (e) => { const r = document.getElementById('demo-ripple');
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; r.classList.remove('go'); void r.offsetWidth; r.classList.add('go'); }, true);
}"""

# Resolves when the scroll has finished, so the cursor aims at where things end up.
SCROLL_PAGE_JS = """([selector, margin]) => new Promise((done) => {
  const main = document.querySelector('[data-testid="stMain"]');
  const top = document.querySelector(selector).getBoundingClientRect().top - main.getBoundingClientRect().top + main.scrollTop - margin;
  if (Math.abs(top - main.scrollTop) < 2) return done();
  main.addEventListener('scrollend', () => done(), { once: true });
  setTimeout(done, 1500);
  main.scrollTo({ top, behavior: 'smooth' }); })"""


SCROLL_RESULTS_JS = """(selector) => new Promise((done) => {
  const pane = [...document.querySelectorAll('[data-testid="stColumn"]')].find(c => c.querySelector('[class*="st-key-results-pane"]'));
  const top = selector ? document.querySelector(selector).getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - 6 : 0;
  if (Math.abs(top - pane.scrollTop) < 2) return done();
  pane.addEventListener('scrollend', () => done(), { once: true });
  setTimeout(done, 1500);
  pane.scrollTo({ top, behavior: 'smooth' }); })"""


class Director:
    """Runs each beat at a fixed time on the video's clock, however long the site takes to respond."""

    def __init__(self, page: Page) -> None:
        self.page, self.start, self.x, self.y = page, time.monotonic(), 720.0, 400.0

    def at(self, seconds: float) -> None:
        wait = seconds - (time.monotonic() - self.start)
        if wait > 0:
            self.page.wait_for_timeout(wait * 1000)

    def glide(self, x: float, y: float, seconds: float = .7) -> None:
        steps = int(seconds * 60)
        for i in range(1, steps + 1):
            t = i / steps
            eased = t * t * (3 - 2 * t)
            self.page.mouse.move(self.x + (x - self.x) * eased, self.y + (y - self.y) * eased)
            self.page.wait_for_timeout(1000 / 60)
        self.x, self.y = x, y

    def glide_to(self, locator, seconds: float = .7) -> None:
        box = locator.bounding_box()
        self.glide(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, seconds)

    def click(self) -> None:
        self.page.mouse.down()
        self.page.wait_for_timeout(70)
        self.page.mouse.up()


def scroll_to(page: Page, selector: str, margin: int = 130) -> None:
    page.evaluate(SCROLL_PAGE_JS, [selector, margin])


def point_beside_score(d: Director, page: Page) -> None:
    box = page.locator(".cf-banner .cf-ring").bounding_box()  # beside the ring: the cursor must not hide the number
    d.glide(box["x"] + box["width"] + 8, box["y"] + box["height"] * .8, .8)


def perform(page: Page) -> None:
    """Two example students, lingering on each match card so the presenter can explain why it matched."""
    d = Director(page)
    rows = page.locator('[class*="st-key-card-top-"] .cf-tracks li')

    def walk_rows(*moves: tuple[float, int]) -> None:
        for when, row in moves:
            d.at(when)
            box = rows.nth(row).bounding_box()
            d.glide(box["x"] + box["width"] * .42, box["y"] + box["height"] / 2, .6)

    def show_card() -> None:
        scroll_to(page, ".st-key-workspace", margin=12)  # more room: the whole card fits on screen
        page.evaluate(SCROLL_RESULTS_JS, '[class*="st-key-card-top-"]')

    def back_to_top() -> None:
        page.evaluate(SCROLL_RESULTS_JS, None)
        scroll_to(page, ".st-key-example-strip", margin=130)

    # Student 1
    d.at(1.0)
    d.glide_to(page.get_by_role("button", name="Try example student 1"), .8)
    d.at(2.2)
    d.click()
    page.wait_for_selector(".cf-banner")
    point_beside_score(d, page)
    d.at(5.0)
    show_card()
    walk_rows((6.2, 0), (7.8, 3), (9.4, 1), (11.0, 4))

    # Student 2
    d.at(12.6)
    back_to_top()
    d.glide_to(page.get_by_role("button", name="Switch to student 2"), .6)
    d.at(14.2)
    d.click()
    page.wait_for_selector("text=Example student 2 (fictional)")
    point_beside_score(d, page)
    d.at(16.8)
    show_card()
    walk_rows((18.0, 1), (19.6, 2), (21.2, 4), (22.8, 0))

    # Missing answers are never guessed
    d.at(24.2)
    back_to_top()
    d.glide_to(page.locator(".cf-board-open"), .6)

    d.at(26.8)
    page.evaluate("document.getElementById('demo-end').classList.add('on')")
    d.at(LENGTH + .1)


def record() -> tuple[float, list[tuple[float, bytes]]]:
    fox = "data:image/svg+xml;base64," + base64.b64encode((ROOT / "assets" / "classfit-fox.svg").read_bytes()).decode()
    frames: list[tuple[float, bytes]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE).new_page()
        page.goto(f"http://localhost:{PORT}")
        page.wait_for_selector(".st-key-hero")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(1500)  # let the opening animations finish
        page.evaluate(OVERLAY_JS, fox)
        page.mouse.move(720, 400)
        cdp = page.context.new_cdp_session(page)

        def on_frame(event: dict) -> None:
            frames.append((event["metadata"]["timestamp"], base64.b64decode(event["data"])))
            cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

        cdp.on("Page.screencastFrame", on_frame)
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 100, "maxWidth": 1920, "maxHeight": 1080})
        started = time.time()
        perform(page)
        cdp.send("Page.stopScreencast")
        browser.close()
    return started, frames


def encode(started: float, frames: list[tuple[float, bytes]]) -> None:
    """The browser only sends a frame when the page changes; hold each one until the next, at a steady frame rate."""
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg",
               "-framerate", str(FPS), "-i", "-", "-vf", "scale=1920:1080:flags=lanczos:in_color_matrix=bt601:in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p",
               # Standard HD colour tags, so QuickTime and PowerPoint show the same Marist red as the browser.
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
               "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-movflags", "+faststart", str(OUTPUT)]
    encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
    index = 0
    for number in range(int(LENGTH * FPS)):
        while index + 1 < len(frames) and frames[index + 1][0] - started <= number / FPS:
            index += 1
        encoder.stdin.write(frames[index][1])
    encoder.stdin.close()
    if encoder.wait():
        sys.exit("Encoding failed.")


def main() -> None:
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
                               "--server.port", str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=1)
                break
            except OSError:
                time.sleep(.5)
        started, frames = record()
    finally:
        server.terminate()
    print(f"Captured {len(frames)} frames.")
    encode(started, frames)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
