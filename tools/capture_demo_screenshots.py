from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_OUTPUT_DIR = Path("docs/assets/demo")


def wait_for_app(page: Page) -> None:
    page.wait_for_selector("#metrics .metric", timeout=15_000)
    page.wait_for_load_state("networkidle")


def show_view(page: Page, view: str) -> None:
    page.locator(f"[data-view='{view}']").click()
    page.wait_for_timeout(500)


def screenshot(page: Page, output_dir: Path, filename: str) -> None:
    page.screenshot(path=output_dir / filename, full_page=True)


def select_first_target(page: Page) -> None:
    target_select = page.locator("#targetSelect")
    first_value = target_select.locator("option").nth(1).get_attribute("value")
    if first_value:
        target_select.select_option(first_value)


def capture(base_url: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.goto(base_url, wait_until="networkidle")
        wait_for_app(page)

        screenshot(page, output_dir, "01-dashboard.png")

        show_view(page, "profile")
        screenshot(page, output_dir, "02-profile-evidence.png")

        show_view(page, "advisors")
        screenshot(page, output_dir, "03-advisor-sources.png")

        show_view(page, "targets")
        screenshot(page, output_dir, "04-target-tracker.png")

        show_view(page, "materials")
        select_first_target(page)
        page.locator("#matchBtn").click()
        page.wait_for_function(
            "() => document.querySelector('#materialTitle').textContent.trim() === '匹配分析报告'",
            timeout=15_000,
        )
        screenshot(page, output_dir, "05-match-report.png")

        page.locator("#emailBtn").click()
        page.wait_for_selector("#qualityView .quality-summary", timeout=20_000)
        screenshot(page, output_dir, "06-material-quality.png")

        page.locator("#pptxBtn").click()
        page.wait_for_selector("#presentationTaskView a", timeout=20_000)
        screenshot(page, output_dir, "07-pptx-download.png")

        show_view(page, "report")
        page.locator("#generateReportBtn").click()
        page.wait_for_function(
            "() => document.querySelector('#reportView').textContent.trim() !== '尚未生成报告'",
            timeout=15_000,
        )
        screenshot(page, output_dir, "08-progress-report.png")

        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture Stage 9 demo screenshots.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    capture(args.base_url, args.output_dir)


if __name__ == "__main__":
    main()
