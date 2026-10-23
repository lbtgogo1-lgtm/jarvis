import asyncio, json
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=[
                "--no-sandbox",
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
            ],
        )
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.context.grant_permissions(
            ["microphone"], origin="http://127.0.0.1:8000"
        )
        errors = []
        failed_http = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on(
            "response",
            lambda r: failed_http.append(r.status) if r.status >= 400 else None,
        )
        await page.goto("http://127.0.0.1:8000")
        await page.wait_for_timeout(3000)
        assert await page.locator("canvas").count() == 1
        assert "OLLAMA • OFFLINE" in await page.locator("#health").inner_text()
        await page.locator("#input").fill("안녕하세요")
        await page.locator("#form button").click()
        await page.wait_for_timeout(1000)
        assert "Ollama" in await page.locator("#error").inner_text()
        await page.locator("#settings").click()
        await page.wait_for_selector("dialog[open]")
        await page.locator("#quality").select_option("LOW")
        await page.locator("#config button[type=button]").click()
        await page.screenshot(path="/workspace/jarvis/data/hud-desktop.png")
        # Explicit fixtures exercise frontend streaming/recording only, never real AI/STT.
        await page.route(
            "**/api/sessions/*/chat",
            lambda route: route.fulfill(
                status=200,
                content_type="application/x-ndjson",
                body="".join(
                    json.dumps(e, ensure_ascii=False) + "\n"
                    for e in [{"token": "[테스트 대역] 한국어 응답"}, {"done": True}]
                ),
            ),
        )
        await page.locator("#input").fill("스트리밍 UI 시험")
        await page.locator("#form button").click()
        await page.wait_for_timeout(500)
        assert (
            "[테스트 대역] 한국어 응답" in await page.locator("#messages").inner_text()
        )
        await page.route(
            "**/api/stt",
            lambda route: route.fulfill(
                json={"text": "[테스트 대역] 음성 전사", "device": "synthetic"}
            ),
        )
        await page.locator("#mic").click()
        await page.wait_for_timeout(500)
        assert await page.locator("#state").inner_text() == "LISTENING"
        await page.locator("#mic").click()
        await page.wait_for_timeout(1000)
        assert "[테스트 대역] 음성 전사" in await page.locator("#messages").inner_text()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(500)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.screenshot(
            path="/workspace/jarvis/data/hud-mobile.png", full_page=True
        )
        assert not errors, errors
        print(
            json.dumps(
                {
                    "expected_http_failures": failed_http,
                    "fixture_stream_and_synthetic_microphone": True,
                    "javascript_errors": errors,
                    "canvas": True,
                    "ollama_error_ui": True,
                    "settings_dialog": True,
                    "mobile_no_horizontal_overflow": True,
                },
                ensure_ascii=False,
            )
        )
        await browser.close()


asyncio.run(main())
