"""Regression scenarios from Korean weather requests (provider/model fixtures)."""

import asyncio
import json

import pytest

from backend import ai_engine, config, research, web_tools as web
from backend.public_web import WebError


def weather_fixture(monkeypatch):
    calls = []
    dates = [f"2026-10-{day}" for day in range(26, 32)] + ["2026-11-01"]

    async def response(method, url, **kwargs):
        params = kwargs["params"]
        calls.append((url, params))
        if "geocoding-api" in url:
            assert params["countryCode"] == "KR"
            if params["name"] != "Seoul":
                return {"generationtime_ms": 0.2}  # Actual empty Korean-name shape.
            return {
                "results": [
                    {
                        "name": "서울특별시",
                        "country": "대한민국",
                        "country_code": "KR",
                        "latitude": 37.566,
                        "longitude": 126.9784,
                    }
                ]
            }
        assert params["latitude"] == 37.566 and params["longitude"] == 126.9784
        assert params["forecast_days"] == 7
        return {
            "timezone": "Asia/Seoul",
            "current": {
                "time": "2026-10-26T15:30",
                "temperature_2m": 17.5,
                "precipitation": 0,
                "wind_speed_10m": 8,
                "weather_code": 0,
            },
            "current_units": {
                "time": "iso8601",
                "temperature_2m": "°C",
                "precipitation": "mm",
                "wind_speed_10m": "km/h",
                "weather_code": "wmo code",
            },
            "daily": {
                "time": dates,
                "weather_code": [0] * 7,
                "temperature_2m_min": [10] * 7,
                "temperature_2m_max": [20] * 7,
                "precipitation_sum": [0] * 7,
                "wind_speed_10m_max": [10] * 7,
            },
            "daily_units": {
                "time": "iso8601",
                "weather_code": "wmo code",
                "temperature_2m_min": "°C",
                "temperature_2m_max": "°C",
                "precipitation_sum": "mm",
                "wind_speed_10m_max": "km/h",
            },
        }

    monkeypatch.setattr(web, "request_json", response)
    return calls, dates


@pytest.mark.parametrize(
    "question",
    [
        "이번주 서울 날씨 알려줘",
        "이번 주 서울 날씨 알려줘",
        "구글에서 대한민국 서울의 날씨 알려줘",
        "오늘 서울특별시 날씨 알려줘",
        "/날씨 서울",
        "/날씨 Seoul, South Korea",
        "weather in Seoul",
    ],
)
@pytest.mark.parametrize("model_location", [None, "Seoul", "이번주 서울"])
def test_korean_weather_request_reaches_real_pipeline(
    monkeypatch, question, model_location
):
    calls, dates = weather_fixture(monkeypatch)

    async def plan(*args):
        if model_location is None:
            raise RuntimeError("model tool calling unavailable")
        return [
            {
                "function": {
                    "name": "get_weather",
                    "arguments": {"location": model_location},
                }
            }
        ]

    monkeypatch.setattr(ai_engine, "plan_tools", plan)
    result = asyncio.run(
        research.prepare(
            config.DEFAULT | {"web_enabled": True},
            [{"role": "user", "content": question}],
            question,
        )
    )
    assert result["answer"] is None and result["connected"]
    assert len(result["sources"]) == 1 and not result["warnings"]
    source = result["sources"][0]
    assert source["weather"]["daily"]["time"] == dates
    assert source["weather"]["current"]["temperature_2m"] == 17.5
    assert "forecast_days=7" in source["url"]
    assert calls[-2][1]["name"] == "Seoul"
    # The complete, valid weather JSON reaches Ollama, including the seventh day.
    tool = next(message for message in result["messages"] if message["role"] == "tool")
    evidence = json.loads(tool["content"])["untrusted_sources"][0]
    assert json.loads(evidence["summary"])["daily"]["time"] == dates


@pytest.mark.parametrize(
    "question",
    ["이번주 날씨 알려줘", "이번 주말 날씨", "오늘 날씨는 어때?", "여기 날씨 알려줘"],
)
def test_missing_place_is_not_sent_as_a_location(monkeypatch, question):
    async def plan(*args):
        return []

    async def forbidden(*args, **kwargs):
        raise AssertionError("No place was supplied; must not geocode.")

    monkeypatch.setattr(ai_engine, "plan_tools", plan)
    monkeypatch.setattr(web, "request_json", forbidden)
    result = asyncio.run(
        research.prepare(config.DEFAULT | {"web_enabled": True}, [], question)
    )
    assert "어느 지역" in result["answer"] and not result["sources"]


def test_current_place_overrides_old_model_location(monkeypatch):
    weather_fixture(monkeypatch)

    async def plan(*args):
        return [
            {"function": {"name": "get_weather", "arguments": {"location": "부산"}}}
        ]

    monkeypatch.setattr(ai_engine, "plan_tools", plan)
    result = asyncio.run(
        research.prepare(
            config.DEFAULT | {"web_enabled": True},
            [
                {"role": "user", "content": "어제 부산 날씨"},
                {"role": "user", "content": "이번주 서울 날씨 알려줘"},
            ],
            "이번주 서울 날씨 알려줘",
        )
    )
    assert result["sources"][0]["weather"]["location"] == "서울특별시, 대한민국"


@pytest.mark.parametrize("city", ["오슬로", "삿포로", "San Francisco"])
def test_unmapped_city_is_preserved_for_geocoding(monkeypatch, city):
    queries = []

    async def response(method, url, **kwargs):
        queries.append(kwargs["params"]["name"])
        return {}

    async def plan(*args):
        return []

    monkeypatch.setattr(web, "request_json", response)
    monkeypatch.setattr(ai_engine, "plan_tools", plan)
    result = asyncio.run(
        research.prepare(
            config.DEFAULT | {"web_enabled": True}, [], f"이번주 {city} 날씨 알려줘"
        )
    )
    assert queries == [city] and not result["sources"]


def test_explicit_country_is_not_silently_changed(monkeypatch):
    calls = []

    async def response(method, url, **kwargs):
        calls.append(kwargs["params"])
        return {
            "results": [
                {
                    "name": "서울",
                    "country_code": "KR",
                    "latitude": 37.566,
                    "longitude": 126.9784,
                }
            ]
        }

    monkeypatch.setattr(web, "request_json", response)
    with pytest.raises(WebError, match="찾지 못했습니다"):
        asyncio.run(web.weather("미국 서울"))
    assert len(calls) == 2 and all(params["countryCode"] == "US" for params in calls)


@pytest.mark.parametrize(
    "failure_stage", ["geocoding-api", "api.open-meteo.com/v1/forecast"]
)
def test_weather_failure_identifies_service_without_generated_values(
    monkeypatch, failure_stage
):
    weather_fixture(monkeypatch)
    response = web.request_json

    async def failing(method, url, **kwargs):
        if failure_stage in url:
            raise WebError("외부 서비스 HTTP 503")
        return await response(method, url, **kwargs)

    async def plan(*args):
        return []

    monkeypatch.setattr(web, "request_json", failing)
    monkeypatch.setattr(ai_engine, "plan_tools", plan)
    result = asyncio.run(
        research.prepare(
            config.DEFAULT | {"web_enabled": True}, [], "이번주 서울 날씨 알려줘"
        )
    )
    assert not result["sources"]
    assert "Open-Meteo" in result["answer"] and "WEB CONNECTED" in result["answer"]
    stage = "지역 검색 실패" if "geocoding" in failure_stage else "날씨 조회 실패"
    assert any(stage in warning and "503" in warning for warning in result["warnings"])
