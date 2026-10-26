"""Linux browser integration with explicitly simulated Ollama/SearXNG services.

Runs real FastAPI, SQLite, HTTP streaming and WebGL. Does not verify model quality
or live Internet results. Refuses occupied ports instead of stopping any process.
"""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import urllib.request

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
state = {
    "offline": False,
    "tool_failure": False,
    "queries": [],
    "used_tool_result": False,
}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, value, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(value, ensure_ascii=False).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == "/api/tags":
            self.respond({"models": [{"name": "qwen3:8b"}]})
        elif self.path == "/config":
            self.respond(
                {
                    "engines": [
                        {"name": name, "disabled": False}
                        for name in ("google", "naver", "google news", "naver news")
                    ]
                }
            )
        elif self.path.startswith("/search?"):
            params = parse_qs(urlsplit(self.path).query)
            query = params.get("q", [""])[0]
            state["queries"].append(query)
            time.sleep(2 if "취소" in query else 0.8)
            if state["offline"]:
                self.respond({"error": "fixture offline"}, 503)
            else:
                self.respond(
                    {
                        "results": [
                            {
                                "title": '[테스트 대역] AI 기사 <img src=x onerror="window.bad=1">',
                                "url": "https://example.org/news",
                                "content": "공개 검색 요약 테스트입니다.",
                                "publishedDate": "2026-10-25",
                                "engine": params.get("engines", ["google"])[0],
                            }
                        ]
                    }
                )
        else:
            self.respond({}, 404)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if payload.get("tools"):
            query = next(
                m["content"]
                for m in reversed(payload["messages"])
                if m["role"] == "user"
            )
            calls = (
                []
                if state["tool_failure"]
                else [
                    {
                        "function": {
                            "name": "search_web",
                            "arguments": {"query": query, "category": "news"},
                        }
                    }
                ]
            )
            self.respond(
                {"message": {"role": "assistant", "content": "", "tool_calls": calls}}
            )
        else:
            state["used_tool_result"] |= any(
                m["role"] == "tool" for m in payload["messages"]
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            try:
                for token in ["[테스트 대역] ", "한국어 ", "요약 답변 ", "[1]"]:
                    self.wfile.write(
                        (json.dumps({"message": {"content": token}}) + "\n").encode()
                    )
                    self.wfile.flush()
                    time.sleep(0.08)
                self.wfile.write(b'{"done":true}\n')
            except (BrokenPipeError, ConnectionResetError):
                pass


async def browser_checks(artifacts):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=[
                "--no-sandbox",
                "--use-gl=angle",
                "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader",
            ],
        )
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto("http://127.0.0.1:8000")
        await page.locator("#health").filter(has_text="OLLAMA • ONLINE").wait_for()
        await page.locator("#tts").uncheck()
        await page.locator("#input").fill("/뉴스 오늘 AI 기술")
        await page.locator("#form button").click()
        await page.locator("#state").filter(has_text="SEARCHING WEB").wait_for()
        assert await page.locator("canvas").count() == 1
        await page.screenshot(path=str(artifacts / "searching.png"))
        await page.locator(".message.assistant span").last.filter(
            has_text="요약 답변"
        ).wait_for()
        await page.wait_for_function(
            "document.querySelector('#input').disabled === false"
        )
        assert (
            await page.locator(".source-card a").last.get_attribute("href")
            == "https://example.org/news"
        )
        assert (
            "발행일: 2026-10-25 · 사건일: 미확인"
            in await page.locator(".source-card").last.inner_text()
        )
        assert await page.evaluate("window.bad === undefined")
        assert state["used_tool_result"]
        await page.reload()
        await page.locator(".source-card a").wait_for()
        await page.wait_for_function(
            "document.querySelector('#input').disabled === false"
        )
        await page.locator("#input").fill("/검색 취소 테스트")
        await page.locator("#form button").click()
        await page.locator("#state").filter(has_text="SEARCHING WEB").wait_for()
        await page.locator("#cancel").click()
        await page.wait_for_function(
            "!document.querySelector('#input').disabled && document.querySelector('#web-status').textContent !== 'SEARCHING WEB'"
        )
        state["tool_failure"] = True
        await page.locator("#input").fill("/검색 최신 기술")
        await page.locator("#form button").click()
        await page.locator(".message.assistant span").last.filter(
            has_text="요약 답변"
        ).wait_for()
        await page.wait_for_function(
            "document.querySelector('#input').disabled === false"
        )
        assert any("최신 기술" in q for q in state["queries"])
        # Named engines use the same source/stream path; result pages are separate links.
        for engine, text in (
            ("google", "구글에서 로컬 AI 검색해줘"),
            ("naver", "네이버에서 영상 편집 검색해줘"),
        ):
            await page.locator("#input").fill(text)
            await page.locator("#form button").click()
            await page.locator(".message.assistant span").last.filter(
                has_text="요약 답변"
            ).wait_for()
            await page.wait_for_function("!document.querySelector('#input').disabled")
            assert (
                "searxng · " + engine
                in await page.locator(".source-card").last.inner_text()
            )
            assert engine in await page.locator(".search-links a").last.get_attribute(
                "href"
            )
        await page.reload()
        await page.locator(".search-links a").last.wait_for()
        assert "naver.com" in await page.locator(".search-links a").last.get_attribute(
            "href"
        )
        # Popups are real browser tabs; external pages are explicit fixtures, not live searches.
        await page.context.route(
            "https://www.google.com/**",
            lambda route: route.fulfill(
                body="Google navigation fixture", content_type="text/html"
            ),
        )
        await page.context.route(
            "https://search.naver.com/**",
            lambda route: route.fulfill(
                body="Naver navigation fixture", content_type="text/html"
            ),
        )
        await page.wait_for_function("!document.querySelector('#input').disabled")
        await page.locator("#input").fill("한국어 & GPU")
        async with page.expect_popup() as opened:
            await page.locator("#open-google").click()
        popup = await opened.value
        await popup.wait_for_load_state()
        assert parse_qs(urlsplit(popup.url).query) == {"q": ["한국어 & GPU"]}
        assert await popup.evaluate("window.opener === null")
        await popup.close()
        await page.locator("#input").fill("네이버에서 영상 아이디어 검색창 열어줘")
        await page.locator("#form button").click()
        await page.locator(".message.assistant span").last.filter(
            has_text="버튼을 누르면"
        ).wait_for()
        async with page.expect_popup() as opened:
            await page.locator(".search-links a").last.click()
        popup = await opened.value
        await popup.wait_for_load_state()
        assert urlsplit(popup.url).hostname == "search.naver.com"
        assert parse_qs(urlsplit(popup.url).query) == {"query": ["영상 아이디어"]}
        assert await popup.evaluate("window.opener === null")
        await popup.close()
        state["offline"] = True
        await page.locator("#input").fill("/검색 최신 뉴스")
        await page.locator("#form button").click()
        await page.locator(".message.assistant span").last.filter(
            has_text="가져오지 못했습니다"
        ).wait_for()
        await page.wait_for_function(
            "document.querySelector('#input').disabled === false"
        )
        await page.locator("#input").fill("안녕하세요")
        await page.locator("#form button").click()
        await page.locator(".message.assistant span").last.filter(
            has_text="요약 답변"
        ).wait_for()
        await page.wait_for_function(
            "document.querySelector('#input').disabled === false"
        )
        await page.locator("#settings").click()
        await page.wait_for_selector("dialog[open]")
        await page.locator("#web_enabled").uncheck()
        await page.get_by_role("button", name="저장", exact=True).click()
        await page.wait_for_function("!document.querySelector('#dialog').open")
        await page.locator("#input").fill("/검색 인터넷 꺼짐 확인")
        await page.locator("#form button").click()
        await page.locator(".message.assistant span").last.filter(
            has_text="OFF 상태"
        ).wait_for()
        assert not any("꺼짐 확인" in q for q in state["queries"])
        # Weather presentation is a separate, explicitly simulated UI response.
        weather = {
            "location": "[테스트 대역] 서울",
            "timezone": "Asia/Seoul",
            "current": {
                "time": "2026-10-26T12:00",
                "temperature_2m": 17.5,
                "precipitation": 0,
                "wind_speed_10m": 8,
            },
            "current_units": {
                "temperature_2m": "°C",
                "precipitation": "mm",
                "wind_speed_10m": "km/h",
            },
            "daily": {
                "time": [f"2026-10-{day}" for day in range(26, 32)] + ["2026-11-01"],
                "temperature_2m_max": [20] * 7,
                "temperature_2m_min": [10] * 7,
                "precipitation_sum": [1] * 7,
                "wind_speed_10m_max": [9] * 7,
            },
            "daily_units": {
                "temperature_2m_max": "°C",
                "temperature_2m_min": "°C",
                "precipitation_sum": "mm",
                "wind_speed_10m_max": "km/h",
            },
            "time_basis": "모델 기반 현재값 · 테스트 대역",
        }
        weather_events = [
            {
                "sources": [
                    {
                        "id": 1,
                        "title": "Open-Meteo · 테스트",
                        "url": "https://api.open-meteo.com/v1/forecast",
                        "published_at": None,
                        "event_date": None,
                        "observed_at": "2026-10-26T12:00",
                        "timezone": "Asia/Seoul",
                        "retrieved_at": "2026-10-26T03:00:00+00:00",
                        "provider": "Open-Meteo",
                        "weather": weather,
                    }
                ]
            },
            {"token": "[테스트 대역] 날씨 카드"},
            {"done": True},
        ]
        await page.route(
            "**/api/sessions/*/chat",
            lambda route: route.fulfill(
                status=200,
                content_type="application/x-ndjson",
                body="".join(
                    json.dumps(e, ensure_ascii=False) + "\n" for e in weather_events
                ),
            ),
        )
        await page.wait_for_function(
            "document.querySelector('#input').disabled === false"
        )
        await page.locator("#input").fill("날씨 카드 UI 검사")
        await page.locator("#form button").click()
        await page.locator(".source-card").last.filter(has_text="17.5 °C").wait_for()
        assert "2026-10-27 예보" in await page.locator(".source-card").last.inner_text()
        assert "2026-11-01 예보" in await page.locator(".source-card").last.inner_text()
        assert "Asia/Seoul" in await page.locator(".source-card").last.inner_text()
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.screenshot(path=str(artifacts / "web-mobile.png"), full_page=True)
        assert not errors, errors
        await browser.close()
        print(
            json.dumps(
                {
                    "searching_webgl": True,
                    "native_tool_protocol_fixture": True,
                    "explicit_command_fallback": True,
                    "source_links_and_dates": True,
                    "sources_after_reload": True,
                    "cancel_resets_search_status": True,
                    "search_failure_keeps_local_chat": True,
                    "off_prevents_search": True,
                    "weather_ui_units_time_forecast_fixture": True,
                    "named_google_naver_search_fixture": True,
                    "search_links_after_reload": True,
                    "google_naver_new_tabs": True,
                    "javascript_errors": errors,
                    "artifacts": str(artifacts),
                },
                ensure_ascii=False,
            )
        )


def main():
    # Never reuse an unrelated running application or its database.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8000))
    artifacts = Path(tempfile.mkdtemp(prefix="jarvis-web-browser-"))
    data = artifacts / "data"
    data.mkdir()
    (data / "settings.json").write_text(
        json.dumps({"web_enabled": True, "searxng_url": "http://127.0.0.1:8080"})
    )
    services = []
    process = None
    try:
        for port in (11434, 8080):
            server = ThreadingHTTPServer(("127.0.0.1", port), Fixture)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            services.append(server)
        with (artifacts / "server.log").open("w") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=ROOT,
                env=os.environ | {"JARVIS_DATA": str(data)},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(80):
                if process.poll() is not None:
                    raise RuntimeError(
                        "Test server failed; inspect " + str(artifacts / "server.log")
                    )
                try:
                    with opener.open("http://127.0.0.1:8000/api/ready", timeout=0.5):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Test server not ready")
            asyncio.run(browser_checks(artifacts))
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(10)
        for server in services:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
