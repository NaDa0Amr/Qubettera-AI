"""Diagnose the browser's discussion SSE lifecycle against a running frontend."""

import os
import time

from playwright.sync_api import sync_playwright


def main():
    base_url = os.environ.get("STREAM_PROBE_URL", "http://localhost:3000")
    mode = os.environ.get("STREAM_PROBE_MODE", "fake")
    duration = int(os.environ.get("STREAM_PROBE_SECONDS", "20"))
    started = time.monotonic()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        def log(kind, detail):
            print(f"{time.monotonic() - started:.2f}s {kind} {detail}", flush=True)

        page.on("request", lambda request: log("REQUEST", request.url) if "/api/week3/discuss" in request.url else None)
        page.on("requestfailed", lambda request: log("FAILED", f"{request.url} {request.failure}"))
        page.on("response", lambda response: log("RESPONSE", f"{response.status} {response.url}") if "/api/week3/discuss" in response.url else None)
        page.on("console", lambda message: log("CONSOLE", f"{message.type}: {message.text}") if message.type == "error" else None)
        page.on("pageerror", lambda error: log("PAGE_ERROR", error))
        page.on("framenavigated", lambda frame: log("NAVIGATED", frame.url) if frame == page.main_frame else None)

        page.goto(f"{base_url}/discussions", wait_until="networkidle")
        page.locator("#topic-input").fill("Compare dense and sparse model layers for a constrained deployment with evidence.")
        if mode == "fake":
            page.get_by_role("button", name="Advanced").click()
            page.get_by_role("radio", name="Fake (no LLM)").check()
        else:
            cards = page.locator('[data-testid^="persona-card-"]')
            for index in range(cards.count() - 1, 1, -1):
                cards.nth(index).click()
        page.locator("#start-discussion-btn").click()

        last = None
        max_draft_chars = 0
        saw_parallel_drafts = False
        until = time.monotonic() + duration
        while time.monotonic() < until:
            current = (page.url, page.locator("main").inner_text()[:200] if page.locator("main").count() else "")
            if current != last:
                log("STATE", repr(current))
                last = current
            drafts = page.locator('article[aria-label$="is speaking"]')
            if drafts.count() > 0:
                max_draft_chars = max(max_draft_chars, *(len(item.inner_text()) for item in drafts.all()))
            saw_parallel_drafts |= drafts.count() >= 2
            page.wait_for_timeout(500)

        log("SUMMARY", f"max_draft_chars={max_draft_chars} parallel_drafts={saw_parallel_drafts}")
        if mode == "live" and max_draft_chars < 40:
            raise AssertionError("Live token text never became visible in the chat")
        browser.close()


if __name__ == "__main__":
    main()
