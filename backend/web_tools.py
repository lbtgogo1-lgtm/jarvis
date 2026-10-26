"""Free local SearXNG search, optional Tavily, and Open-Meteo weather."""

import asyncio
import ipaddress
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlencode

import httpx
from bs4 import BeautifulSoup

from .public_web import WebError, public_url
from .weather_locations import geocoding_names


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def searxng_url(value):
    try:
        parts = urlsplit(value)
        host = parts.hostname
        allowed = host == "localhost" or (
            host is not None and ipaddress.ip_address(host).is_loopback
        )
        port = parts.port
    except (ValueError, TypeError):
        allowed = False
    if (
        not allowed
        or parts.scheme not in ("http", "https")
        or parts.username is not None
        or parts.password is not None
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
    ):
        raise ValueError("SearXNG는 로컬 주소(예: http://127.0.0.1:8080)만 지정하세요.")
    return value.rstrip("/")


async def request_json(method, url, *, local=False, **kwargs):
    try:
        async with asyncio.timeout(15):
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(12, connect=4),
                trust_env=not local,
                follow_redirects=False,
            ) as client:
                async with client.stream(method, url, **kwargs) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 2_000_000:
                            raise WebError(
                                "외부 서비스 응답이 크기 제한을 초과했습니다."
                            )
                    import json

                    payload = json.loads(body)
                    if not isinstance(payload, dict):
                        raise ValueError("JSON object expected")
                    return payload
    except httpx.HTTPStatusError as error:
        raise WebError(
            f"외부 서비스 HTTP {error.response.status_code}: 주소·JSON 검색 허용·API 인증을 확인하세요."
        ) from None
    except (httpx.HTTPError, TimeoutError, ValueError):
        raise WebError(
            "외부 서비스 연결 또는 JSON 응답 확인에 실패했습니다. 네트워크와 서비스 설정을 확인하세요."
        ) from None


def clean(value, size):
    return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)[
        :size
    ]


def source(item, provider, kind="search"):
    return {
        "title": clean(item.get("title"), 240),
        "url": public_url(item.get("url", "")),
        "summary": clean(
            item.get("content") or item.get("snippet") or item.get("summary"), 1500
        ),
        "published_at": clean(
            item.get("publishedDate")
            or item.get("published_date")
            or item.get("published_at"),
            80,
        )
        or None,
        "event_date": None,
        "retrieved_at": now(),
        "provider": provider,
        "kind": kind,
    }


async def search_web(settings, query, category="general", time_range=""):
    query = query.strip()[:500]
    if not query:
        raise WebError("검색어를 입력하세요.")
    provider = settings.get("web_provider", "searxng")
    if provider == "tavily":
        key = os.environ.get("TAVILY_API_KEY", "")
        if not key:
            raise WebError(
                "TAVILY_API_KEY가 없습니다. 무료 기본 검색인 SearXNG를 선택하거나 환경변수를 설정하세요."
            )
        payload = await request_json(
            "POST",
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "query": query,
                "topic": "news" if category == "news" else "general",
                "max_results": 5,
                "include_answer": False,
                "include_raw_content": False,
                **({"time_range": time_range} if time_range else {}),
            },
        )
    else:
        base = searxng_url(settings.get("searxng_url", "http://127.0.0.1:8080"))
        payload = await request_json(
            "GET",
            base + "/search",
            local=True,
            params={
                "q": query,
                "format": "json",
                "language": "ko-KR",
                "categories": category,
                "safesearch": 1,
                "time_range": time_range,
            },
        )
    if not isinstance(payload.get("results"), list):
        raise WebError(
            "JSON 검색 결과가 없습니다. SearXNG search.formats에 json이 포함되어야 합니다."
        )
    results = []
    seen = set()
    for raw in payload["results"][:20]:
        if not isinstance(raw, dict):
            continue
        try:
            entry = source(raw, provider, "news" if category == "news" else "search")
        except WebError:
            continue
        if entry["url"] not in seen:
            seen.add(entry["url"])
            results.append(entry)
        if len(results) == 5:
            break
    warnings = (
        ["일부 검색 엔진이 응답하지 않아 결과가 불완전할 수 있습니다."]
        if payload.get("unresponsive_engines")
        else []
    )
    key = (
        provider,
        settings.get("searxng_url"),
        bool(os.environ.get("TAVILY_API_KEY")),
    )
    _status_cache[key] = (
        time.monotonic(),
        {
            "enabled": True,
            "provider": provider,
            "connected": bool(results) or not warnings,
            "json_ready": True,
            "tavily_key_set": key[2],
            "checked_at": now(),
            "message": (
                "JSON 연결 정상. 상위 검색 엔진이 응답하지 않았습니다."
                if warnings and not results
                else "검색 서비스 JSON 연결 확인. 개별 사이트·엔진 가용성은 검색 시 확인합니다."
            ),
        },
    )
    return {"sources": results, "warnings": warnings}


async def weather(location):
    location = location.strip()[:120]
    names, country = geocoding_names(location)
    if not names:
        raise WebError("날씨를 확인할 지역을 입력하세요. 예: /날씨 서울")
    places = []
    for name in names:
        try:
            geo = await request_json(
                "GET",
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": name,
                    "count": 5,
                    "language": "ko",
                    "format": "json",
                    **({"countryCode": country} if country else {}),
                },
            )
        except WebError as error:
            raise WebError(f"Open-Meteo 지역 검색 실패: {error}") from None
        places = [
            place
            for place in (geo.get("results") or [])[:5]
            if isinstance(place, dict)
            and (not country or place.get("country_code") == country)
        ]
        if places:
            break
    if not places:
        raise WebError(
            f"Open-Meteo에서 지역 '{location}'을 찾지 못했습니다. "
            "도시명 또는 영문 도시명과 국가를 확인해 주세요. 예: /날씨 Seoul, South Korea"
        )
    place = places[0]
    try:
        latitude, longitude = float(place["latitude"]), float(place["longitude"])
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise WebError("위치 검색 서비스의 좌표 응답을 확인할 수 없습니다.") from None
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": 7,
    }
    try:
        data = await request_json(
            "GET", "https://api.open-meteo.com/v1/forecast", params=params
        )
    except WebError as error:
        raise WebError(f"Open-Meteo 날씨 조회 실패: {error}") from None
    if not data.get("current", {}).get("time") or not data.get("daily", {}).get("time"):
        raise WebError(
            "기준 시각 또는 예보가 없는 날씨 응답입니다. 수치를 확인할 수 없습니다."
        )
    # Keep only the requested fields and seven dates so the entire weather
    # evidence fits the model context without truncating JSON or the final days.
    current_keys = (
        "time",
        "temperature_2m",
        "precipitation",
        "wind_speed_10m",
        "weather_code",
    )
    daily_keys = (
        "time",
        "weather_code",
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "wind_speed_10m_max",
    )
    current = {key: data["current"].get(key) for key in current_keys}
    daily = {key: data["daily"].get(key, [])[:7] for key in daily_keys}
    # Provider data is untrusted: reject nested/oversized field values.
    for values in (current.values(), *(daily[key] for key in daily_keys)):
        if any(
            value is not None
            and (not isinstance(value, (str, int, float)) or len(str(value)) > 80)
            for value in values
        ):
            raise WebError("Open-Meteo 날씨 데이터 형식을 확인할 수 없습니다.")
    detail = {
        "location": ", ".join(
            str(place[k])[:120] for k in ("name", "admin1", "country") if place.get(k)
        ),
        "latitude": latitude,
        "longitude": longitude,
        "timezone": str(data.get("timezone") or "")[:80],
        "current": current,
        "current_units": {
            key: str(data.get("current_units", {}).get(key, ""))[:30]
            for key in current_keys
        },
        "daily": daily,
        "daily_units": {
            key: str(data.get("daily_units", {}).get(key, ""))[:30]
            for key in daily_keys
        },
        "forecast_period": "조회 지역의 오늘부터 최대 7일. 날짜별 time에 있는 기간만 확인 가능합니다.",
        "time_basis": "Open-Meteo 모델 기반 현재값의 기준 시각이며 관측소 실측값은 아닙니다.",
    }
    import json

    entry = {
        "title": "Open-Meteo · " + detail["location"],
        "url": "https://api.open-meteo.com/v1/forecast?" + urlencode(params),
        "summary": json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
        "published_at": None,
        "event_date": None,
        "observed_at": data["current"]["time"],
        "timezone": data.get("timezone"),
        "retrieved_at": now(),
        "provider": "Open-Meteo",
        "kind": "weather",
        "weather": detail,
    }
    warnings = (
        [
            "선택된 지역: "
            + detail["location"]
            + ". 동명이면 국가를 포함해 다시 검색하세요."
        ]
        if len(places) > 1
        else []
    )
    return {"sources": [entry], "warnings": warnings}


_status_cache = {}


async def web_status(settings, force=False):
    provider = settings.get("web_provider", "searxng")
    result = {
        "enabled": settings.get("web_enabled", False),
        "provider": provider,
        "connected": False,
        "json_ready": False,
        "tavily_key_set": bool(os.environ.get("TAVILY_API_KEY")),
    }
    if not result["enabled"]:
        return result | {"message": "인터넷 검색 OFF · 로컬 대화 사용 가능"}
    key = (provider, settings.get("searxng_url"), result["tavily_key_set"])
    cached = _status_cache.get(key)
    if (
        not force
        and cached
        and (provider == "tavily" or time.monotonic() - cached[0] < 180)
    ):
        return cached[1]
    if provider == "tavily" and not force:
        return result | {
            "message": (
                "Tavily 키가 설정되었습니다. 연결 점검 또는 검색 시 API가 호출됩니다."
                if result["tavily_key_set"]
                else "TAVILY_API_KEY가 없습니다. SearXNG를 선택하거나 환경변수를 설정하세요."
            )
        }
    try:
        await search_web(
            settings,
            "SearXNG" if provider == "searxng" else "internet search",
            "general",
        )
        result = _status_cache[key][1]
    except (WebError, ValueError) as error:
        result["message"] = str(error)
    _status_cache[key] = (time.monotonic(), result)
    return result
