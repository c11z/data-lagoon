# /// script
# requires-python = ">=3.12"
# dependencies = ["beautifulsoup4", "pillow", "plotly", "websocket-client", "pymupdf"]
# ///
"""Render the whole notebook (code cells + outputs) as ONE tall single-page PDF.

Why this exists
---------------
`marimo export html` renders the *app* view (outputs only, code hidden) and printing
it from a browser paginates badly and drops the code. This script instead produces a
single continuous image of the entire notebook — code cells included — as a one-page PDF.

Pipeline
--------
1. `marimo export ipynb --include-outputs`  -> a notebook with code + captured outputs.
2. `jupyter nbconvert --to html`            -> Jupyter-style "code above output" HTML.
3. marimo stores plotly figures as a custom `<marimo-plotly>` element that nbconvert
   cannot draw; rewrite each into a real plotly div + `Plotly.newPlot`, and inline
   plotly.js (offline — the CDN does not load in headless Chrome).
4. Headless Chrome full-page screenshot (`captureBeyondViewport`) -> one tall PNG.
5. Wrap the PNG in a single-page PDF (page sized to the image).

The marimo/nbconvert steps run in the PROJECT environment (they need the notebook's
own deps); the rest run from this script's isolated deps (declared above).

Usage
-----
    uv run analyses/2026-06-29-monzo-accounts-7d-active-users/build_screenshot_pdf.py

Outputs (in ./out/, gitignored — submission artifacts):
    out/notebook_screenshot.pdf   (1 page)
    out/notebook_screenshot.png

Set CHROME=/path/to/chrome to override Chrome auto-detection.
"""

import base64
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
NB = HERE / "notebook.py"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
PNG = OUT / "notebook_screenshot.png"
PDF = OUT / "notebook_screenshot.pdf"

# Capture at 3x CSS resolution for crisp text. A PDF page must stay within the
# 200-inch (14400 pt) format limit, else viewers rescale the oversized page and it
# looks fuzzy — so the page is capped just under that and the full-res image embedded.
SCALE = 3
MAX_PAGE_PT = 14000.0
# Chrome silently caps screenshot height (~38k px); capture in bands this tall (CSS px,
# pre-scale) and stitch, so a tall notebook never goes blank at the bottom.
BAND_CSS = 4000


def _chrome() -> str:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    candidates += [p for p in (shutil.which("google-chrome"), shutil.which("chromium")) if p]
    for c in candidates:
        if c and Path(c).exists():
            return c
    sys.exit("Chrome not found — set CHROME=/path/to/chrome")


def _uv(*args: str) -> None:
    # Run a uv command in the project env (cwd = notebook dir so uv finds the project).
    env = {**os.environ, "UV_SYSTEM_CERTS": "1"}
    subprocess.run(["uv", "run", *args], cwd=HERE, env=env, check=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        ipynb, html = td / "nb.ipynb", td / "full.html"

        print("[1/5] marimo export ipynb (code + outputs)…")
        _uv(
            "--with",
            "nbformat",
            "marimo",
            "export",
            "ipynb",
            "--include-outputs",
            "--sort",
            "top-down",
            str(NB),
            "-o",
            str(ipynb),
        )

        print("[2/5] nbconvert -> html…")
        _uv(
            "--with",
            "nbconvert",
            "--with",
            "nbformat",
            "jupyter",
            "nbconvert",
            "--to",
            "html",
            "--embed-images",
            "--output",
            "full",
            "--output-dir",
            str(td),
            str(ipynb),
        )

        print("[3/5] rewrite <marimo-plotly> -> plotly divs + inline plotly.js…")
        from bs4 import BeautifulSoup
        from plotly.offline import get_plotlyjs

        soup = BeautifulSoup(html.read_text(), "html.parser")
        n = 0
        for el in soup.find_all("marimo-plotly"):
            fig = json.loads(el["data-figure"])
            types = {t.get("type", "scatter") for t in fig.get("data", [])}
            height = 720 if "heatmap" in types else 460
            div = soup.new_tag("div", id=f"plt{n}", **{"class": "plotly-graph-div"})
            div["style"] = f"width:980px;height:{height}px;"
            scr = soup.new_tag("script")
            scr.string = (
                f'Plotly.newPlot("plt{n}",{json.dumps(fig.get("data", []))},'
                f"{json.dumps(fig.get('layout', {}))},{{responsive:false,staticPlot:true}});"
            )
            el.replace_with(div)
            div.insert_after(scr)
            n += 1
        doc = str(soup).replace("</head>", f"<script>{get_plotlyjs()}</script>\n</head>", 1)
        rendered = td / "rendered.html"
        rendered.write_text(doc)
        print(f"        rewrote {n} charts, inlined plotly.js")

        print("[4/5] headless Chrome full-page screenshot…")
        png_bytes = _screenshot(rendered)
        PNG.write_bytes(png_bytes)

        print("[5/5] wrap PNG in a single-page PDF…")
        import fitz

        pix = fitz.Pixmap(str(PNG))
        # Size the page to the image aspect, capping height under the PDF 14400 pt
        # limit; the full-resolution image is embedded, so it stays sharp.
        h = min(float(pix.height), MAX_PAGE_PT)
        w = pix.width * (h / pix.height)
        out = fitz.open()
        page = out.new_page(width=w, height=h)
        page.insert_image(fitz.Rect(0, 0, w, h), stream=png_bytes)
        out.save(str(PDF), deflate=True)
        dpi = round(pix.height / h * 72)
        mb = round(PDF.stat().st_size / 1e6, 1)
        print(f"\nDone -> {PDF}  ({mb} MB, 1 page, {round(w)}x{round(h)} pt, ~{dpi} DPI)")


def _screenshot(html_path: Path) -> bytes:
    from io import BytesIO

    from PIL import Image
    from websocket import create_connection

    port = 9444
    proc = subprocess.Popen(
        [
            _chrome(),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            "--window-size=1100,1400",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        page = None
        for _ in range(80):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                pages = [
                    t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")
                ]
                if pages:
                    page = pages[0]
                    break
            except Exception:
                pass
            time.sleep(0.2)
        ws = create_connection(page["webSocketDebuggerUrl"], max_size=256 * 1024 * 1024)
        i = 0

        def cmd(method, params=None):
            nonlocal i
            i += 1
            ws.send(json.dumps({"id": i, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == i:
                    return msg

        cmd("Page.enable")
        cmd("Page.navigate", {"url": html_path.resolve().as_uri()})
        time.sleep(6)  # let plotly draw the SVG charts
        m = cmd("Page.getLayoutMetrics")["result"]
        cs = m.get("cssContentSize") or m["contentSize"]
        w, h = math.ceil(cs["width"]), math.ceil(cs["height"])
        print(f"        content size: {w} x {h}")
        # Capture in vertical bands (Chrome caps screenshot height) and stitch.
        canvas = Image.new("RGB", (w * SCALE, h * SCALE), "white")
        y = 0
        while y < h:
            bh = min(BAND_CSS, h - y)
            shot = cmd(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "captureBeyondViewport": True,
                    "clip": {"x": 0, "y": y, "width": w, "height": bh, "scale": SCALE},
                },
            )
            band = Image.open(BytesIO(base64.b64decode(shot["result"]["data"])))
            canvas.paste(band, (0, y * SCALE))
            y += bh
        buf = BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
