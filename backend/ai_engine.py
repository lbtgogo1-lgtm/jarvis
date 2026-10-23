import httpx, json

URL = "http://127.0.0.1:11434"


async def models():
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        r = await client.get(URL + "/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json()["models"]]


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
