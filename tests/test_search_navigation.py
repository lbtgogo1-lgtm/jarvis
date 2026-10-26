import asyncio
import json
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml
from fastapi.testclient import TestClient

import app as application
import prepare_web
from backend import ai_engine, config, database as db, research, web_tools as web
from backend.public_web import WebError
from backend.search_navigation import browser_request, search_links


@pytest.mark.parametrize(
    "text,engine,query,opening",
    [
        ("구글에서 최신 AI 기술 검색해줘", "google", "최신 AI 기술", False),
        (
            "네이버에서 RTX 3080 중고 가격 검색해서 알려줘",
            "naver",
            "RTX 3080 중고 가격",
            False,
        ),
        ("/구글 영상 편집 프로그램", "google", "영상 편집 프로그램", False),
        ("/naver AI news", "naver", "AI news", False),
        ("구글에서 로컬 AI 검색창 열어줘", "google", "로컬 AI", True),
        ("네이버에서 영상 아이디어 검색 결과를 띄워줘", "naver", "영상 아이디어", True),
        ("구글 열어줘", "google", "", True),
        ("네이버 창 띄워줘", "naver", "", True),
        (
            "구글에서 자동으로 문을 열어주는 장치 검색해줘",
            "google",
            "자동으로 문을 열어주는 장치",
            False,
        ),
    ],
)
def test_explicit_browser_requests(text, engine, query, opening):
    request = browser_request(text)
    assert request == {"engine": engine, "query": query, "open_only": opening}


@pytest.mark.parametrize(
    "engine,host,key",
    [("google", "www.google.com", "q"), ("naver", "search.naver.com", "query")],
)
def test_search_targets_encode_user_text_as_query_only(engine, host, key):
    query = "서울 & redirect=https://localhost/ # <script>alert(1)</script>"
    link = search_links(query, engine)[0]
    parts = urlsplit(link["url"])
    assert parts.scheme == "https" and parts.netloc == host
    assert parse_qs(parts.query) == {key: [query]} and not parts.fragment


@pytest.mark.parametrize(
    "engine,category,selected",
    [
        ("google", "general", "google"),
        ("naver", "general", "naver"),
        ("naver", "news", "naver news"),
        ("google", "news", "google news"),
    ],
)
def test_named_search_uses_only_requested_searxng_engine(
    monkeypatch, engine, category, selected
):
    calls = []

    async def response(method, url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs["local"]
        if url.endswith("/config"):
            return {"engines": [{"name": selected, "disabled": False}]}
        assert kwargs["params"]["engines"] == selected
        return {
            "results": [
                {
                    "title": "Actual selected engine",
                    "url": "https://example.org/match",
                    "content": "자료",
                    "engines": [selected],
                },
                {
                    "title": "Wrong engine",
                    "url": "https://example.org/wrong",
                    "engines": ["bing"],
                },
            ]
        }

    monkeypatch.setattr(web, "request_json", response)
    result = asyncio.run(
        web.search_web(
            config.DEFAULT | {"web_provider": "tavily"}, "AI", category, engine=engine
        )
    )
    assert len(calls) == 2 and len(result["sources"]) == 1
    assert result["sources"][0]["provider"] == "searxng · " + selected


@pytest.mark.parametrize(
    "entries",
    [[{"name": "bing", "enabled": True}], [{"name": "naver", "enabled": False}]],
)
def test_missing_engine_does_not_fall_back_to_other_engines(monkeypatch, entries):
    async def response(method, url, **kwargs):
        assert url.endswith("/config")
        return {"engines": entries}

    monkeypatch.setattr(web, "request_json", response)
    with pytest.raises(WebError, match="setup_web.bat"):
        asyncio.run(web.search_web(config.DEFAULT, "AI", engine="naver"))


def test_failed_search_keeps_browser_link_out_of_evidence(monkeypatch):
    async def plan(*args):
        return [
            {
                "function": {
                    "name": "search_web",
                    "arguments": {"query": "unrelated", "engine": "google"},
                }
            }
        ]

    async def failure(settings, **kwargs):
        assert kwargs["query"] == "영상 편집" and kwargs["engine"] == "naver"
        raise WebError("naver unavailable")

    monkeypatch.setattr(ai_engine, "plan_tools", plan)
    monkeypatch.setattr(web, "search_web", failure)
    result = asyncio.run(
        research.prepare(
            config.DEFAULT | {"web_enabled": True}, [], "네이버에서 영상 편집 검색해줘"
        )
    )
    assert result["answer"] and not result["sources"] and not result["connected"]
    assert result["search_links"][0]["engine"] == "naver"
    assert result["search_links"][0]["query"] == "영상 편집"
    assert not result["messages"]


def test_open_command_without_ollama_or_network_persists_link(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Navigation must not call a model or search provider")

    monkeypatch.setattr(ai_engine, "models", forbidden)
    monkeypatch.setattr(ai_engine, "plan_tools", forbidden)
    monkeypatch.setattr(web, "request_json", forbidden)
    monkeypatch.setattr(
        application.config, "load", lambda: config.DEFAULT | {"web_enabled": True}
    )
    client = TestClient(application.app)
    sid = client.post("/api/sessions").json()["id"]
    response = client.post(
        f"/api/sessions/{sid}/chat", json={"text": "구글에서 로컬 AI 검색창 열어줘"}
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]["done"] and not any(e.get("web") for e in events)
    assert any(e.get("search_links") for e in events)
    db.init()
    saved = client.get(f"/api/sessions/{sid}").json()[-1]
    assert saved["search_links"][0]["query"] == "로컬 AI" and "sources" not in saved
    assert "버튼을 누르면" in saved["content"]
    assert all("search_links" not in m for m in db.context(sid))


def test_off_does_not_create_navigation_action(monkeypatch):
    result = asyncio.run(
        research.prepare(config.DEFAULT | {"web_enabled": False}, [], "네이버 열어줘")
    )
    assert not result["search_links"] and "OFF" in result["answer"]


def test_searxng_upgrade_preserves_settings_secret_and_backup(tmp_path):
    target = tmp_path / "settings.yml"
    original = """use_default_settings:
  engines:
    keep_only: [google, bing]
server:
  secret_key: local-placeholder-secret
  limiter: true
search:
  formats: [html, json]
engines:
  - name: google
    disabled: false
  - name: naver
    disabled: true
"""
    target.write_text(original)
    prepare_web.enable_naver(target)
    changed = target.read_text()
    data = yaml.safe_load(changed)
    assert data["server"] == {"secret_key": "local-placeholder-secret", "limiter": True}
    assert data["use_default_settings"]["engines"]["keep_only"] == [
        "google",
        "bing",
        "naver",
        "naver news",
    ]
    engines = {item["name"]: item for item in data["engines"]}
    assert (
        not engines["naver"]["disabled"]
        and engines["naver news"]["naver_category"] == "news"
    )
    assert target.with_name("settings.before-naver.yml").read_text() == original
    prepare_web.enable_naver(target)
    assert target.read_text() == changed


def test_new_config_and_old_config_enable_same_supported_naver_categories(tmp_path):
    target = tmp_path / "settings.yml"
    target.write_text("use_default_settings: true\n")
    prepare_web.enable_naver(target)
    categories = {
        item["name"]: item["naver_category"]
        for item in yaml.safe_load(target.read_text())["engines"]
    }
    assert categories == {"naver": "general", "naver news": "news"}
