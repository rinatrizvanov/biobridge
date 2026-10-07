#!/usr/bin/env python3
"""Screenshots of the packaged BioBridge.app running the real SpliceAI engine.

    T=$(mktemp -d -t biobridge-screenshots)
    uv run python scripts/screenshots.py build/biobridge/macos/app/BioBridge.app "$T"

The app runs against an isolated data directory inside the given folder (this Mac,
not a clean machine). Inputs are the synthetic test files in tests/model/data. 200%
zoom is emulated the way browsers lay it out (a 1280 px window at 200% has a
640-CSS-pixel viewport at device scale 2). WebKit reuses the Chromium session cookie
because the app hands out one sign-in link per launch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from verify_packaged_app import DATA, app_pids, wait  # noqa: E402

from playwright.sync_api import expect, sync_playwright  # noqa: E402


def main() -> int:
    app, folder = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    shots = folder / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    home = folder / "Application Support" / "BioBridge"
    home.mkdir(parents=True, exist_ok=True)
    (home / "settings.json").write_text(json.dumps({"engine_license_ack": True,
                                                    "engine_license_ack_time": "screenshot run"}))
    link = folder / "auth-url"
    if app_pids(app):
        raise SystemExit("quit the running BioBridge first")
    subprocess.run(["open", "-n", "--env", f"BIOBRIDGE_HOME={home}", "--env", "BIOBRIDGE_NO_BROWSER=1",
                    "--env", f"BIOBRIDGE_AUTH_URL_FILE={link}", str(app)], check=True)
    wait(lambda: link.exists() and link.read_text().startswith("http://127.0.0.1:"), 900, "the sign-in link")
    made = []

    def save(page_or_locator, name, **kw):
        path = shots / name
        page_or_locator.screenshot(path=str(path), **kw)
        made.append(name)

    with sync_playwright() as p:
        chromium = p.chromium.launch()
        context = chromium.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2,
                                       accept_downloads=True)
        page = context.new_page()
        page.goto(link.read_text())
        expect(page.get_by_role("heading", name="Score variants with SpliceAI")).to_be_visible()
        save(page, "01-input-light.png")
        page.emulate_media(color_scheme="dark")
        save(page, "02-input-dark.png")
        page.emulate_media(color_scheme="light")

        page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(DATA / "runner_vs_cli_grch38.vcf")
        page.get_by_label("These coordinates are GRCh38 (hg38).").check()
        page.get_by_role("button", name="Run SpliceAI").click()
        expect(page.get_by_role("heading", name="Results")).to_be_visible(timeout=600_000)
        results_url = page.url
        for mode in ("light", "dark"):
            page.emulate_media(color_scheme=mode)
            page.evaluate("window.scrollTo(0, 0)")  # element screenshots below scroll the page
            save(page, f"03-results-top-{mode}.png")
            save(page, f"04-results-full-{mode}.png", full_page=True)
            save(page.locator(".bb-table-wrap").first, f"05-all-alleles-table-{mode}.png")
            save(page.locator("#r0"), f"06-record1-0.99-{mode}.png")      # donor loss 0.99
            save(page.locator("#r3"), f"07-record4-1.00-{mode}.png")      # deletion: donor loss 1.00
            save(page.locator("#r2"), f"08-record3-masked-zero-{mode}.png")
        page.emulate_media(color_scheme="light")

        # Keyboard tooltip
        figure = page.locator("#r0 figure")
        figure.scroll_into_view_if_needed()
        marks = page.locator("#r0 g.bb-mark")
        marks.nth(2).focus()
        page.keyboard.press("Tab")
        expect(page.locator(".bb-tooltip")).to_be_visible()
        f, t = figure.bounding_box(), page.locator(".bb-tooltip").bounding_box()
        x0, y0 = min(f["x"], t["x"]) - 12, min(f["y"], t["y"]) - 12
        x1, y1 = max(f["x"] + f["width"], t["x"] + t["width"]) + 12, max(f["y"] + f["height"], t["y"] + t["height"]) + 12
        save(page, "09-keyboard-tooltip.png", clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
        page.keyboard.press("Escape")

        # Narrow and 200% zoom (same session, different layout viewport)
        for name, size in (("10-narrow-375", {"width": 375, "height": 812}),
                           ("11-zoom-200-percent", {"width": 640, "height": 450})):
            page.set_viewport_size(size)
            page.goto(results_url)
            save(page, f"{name}-top.png")
            save(page.locator("#r0"), f"{name}-record1.png")
        page.set_viewport_size({"width": 1280, "height": 900})

        # WebKit, reusing the session cookie
        webkit = p.webkit.launch()
        wk = webkit.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        wk.add_cookies(context.cookies())
        wk_page = wk.new_page()
        wk_page.goto(results_url)
        expect(wk_page.get_by_role("heading", name="Results")).to_be_visible()
        for mode in ("light", "dark"):
            wk_page.emulate_media(color_scheme=mode)
            save(wk_page.locator("#r0"), f"12-webkit-record1-{mode}.png")
        webkit.close()

        # Progress, then Cancel
        page.goto(results_url.split("/jobs/")[0] + "/")
        page.get_by_label("VCF or VCF.gz, up to 1 MB").set_input_files(DATA / "runtime_50_alleles_grch38.vcf")
        page.get_by_label("These coordinates are GRCh38 (hg38).").check()
        page.get_by_role("button", name="Run SpliceAI").click()
        expect(page.locator("#bb-progress-text")).to_contain_text("Scored", timeout=120_000)
        expect(page.locator("#bb-progress-text")).not_to_contain_text("Scored 0 of", timeout=60_000)
        save(page, "13-progress.png")
        page.get_by_role("button", name="Cancel").click()
        expect(page.get_by_role("heading", name="Cancelled")).to_be_visible(timeout=30_000)
        save(page, "14-cancelled.png")
        page.get_by_role("button", name="Quit BioBridge").click()
        expect(page.get_by_role("heading", name="BioBridge is quitting")).to_be_visible()
        chromium.close()

    wait(lambda: not app_pids(app), 30, "the app to quit")
    (shots / "INDEX.txt").write_text("\n".join(made) + "\n")
    print(json.dumps({"folder": str(shots), "screenshots": made}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
