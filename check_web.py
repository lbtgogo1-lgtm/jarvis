"""Check the actual local SearXNG JSON API, optionally weather (explicit network use)."""

import argparse
import asyncio
import json
from backend import config, web_tools


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--weather", help="Optional location, e.g. Seoul")
    args = parser.parse_args()
    settings = config.load() | {
        "web_enabled": True,
        "web_provider": "searxng",
        "searxng_url": web_tools.searxng_url(args.url),
    }
    status = await web_tools.web_status(settings, force=True)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if args.weather:
        try:
            data = await web_tools.weather(args.weather)
            print(json.dumps(data, ensure_ascii=False, indent=2))
        except web_tools.WebError as error:
            print(str(error))
            return 1
    return 0 if status["connected"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
