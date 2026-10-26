import httpx, json

URL = "http://127.0.0.1:11434"


async def models():
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        r = await client.get(URL + "/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json()["models"]]


async def plan_tools(settings, messages, tools):
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15, connect=3), trust_env=False
    ) as client:
        response = await client.post(
            URL + "/api/chat",
            json={
                "model": settings["model"],
                "stream": False,
                "think": False,
                "messages": [
                    {
                        "role": "system",
                        "content": "필요한 인터넷 도구만 선택하세요. 검색어에는 질문과 관련된 최소 정보만 넣으세요. 날씨는 get_weather를 사용하고 location에는 도시명과 필요한 국가만 넣으세요. 오늘·이번주·구글에서·알려줘 같은 문구는 location에 포함하지 마세요. 사용자가 말하지 않은 지역을 추측하지 마세요. URL은 사용자 제공 주소만 지정하세요.",
                    }
                ]
                + messages[-6:],
                "tools": tools,
                "options": {"temperature": 0, "num_predict": 256, "num_ctx": 8192},
            },
        )
        response.raise_for_status()
        calls = response.json().get("message", {}).get("tool_calls", [])
        return calls if isinstance(calls, list) else []


async def stream(settings, messages):
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(180, connect=5), trust_env=False
    ) as client:
        async with client.stream(
            "POST",
            URL + "/api/chat",
            json={
                "model": settings["model"],
                "messages": [{"role": "system", "content": settings["personality"]}]
                + messages,
                "stream": True,
                "think": False,
                "options": {"temperature": settings["temperature"], "num_ctx": 8192},
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    item = json.loads(line)
                    if item.get("error"):
                        raise RuntimeError(item["error"])
                    yield item.get("message", {}).get("content", "")
