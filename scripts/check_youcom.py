"""Run a one-query You.com smoke test without printing credentials."""
import asyncio
import sys

import httpx

from wimbl.config import settings
from wimbl.integrations.youcom import YouSearch


async def main() -> int:
    if not settings.you_api_key:
        print("ERROR: YOU_API_KEY is not set. Add it to your local .env file.")
        return 2
    # Never print headers, settings, or exception request objects that could expose secrets.
    try:
        # Bypass the response cache: a smoke test must reach the live API.
        results = await YouSearch(use_cache=False).search("official tennis tournament dates", count=3)
    except httpx.HTTPStatusError as exc:
        print(f"ERROR: You.com returned HTTP {exc.response.status_code}.")
        try:
            print(exc.response.text[:1000])
        except Exception:
            pass
        return 1
    except (httpx.RequestError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {str(exc)[:500]}")
        return 1
    if not results:
        print("WARNING: request succeeded but no web results were normalized.")
        print("Check the API response schema and account/product access.")
        return 1
    print(f"SUCCESS: received {len(results)} result(s)")
    for index, result in enumerate(results, start=1):
        print(f"{index}. {result['title']}\n   {result['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
