"""Minimal MCP server for sourced event research (Brave Search + Open-Meteo)."""

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("event-research")
USER_AGENT = "event-handler-research/1.0 (MCP; contact repository maintainer)"


def request_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"External research request failed: {exc}") from exc


@mcp.tool()
def search_web(query: str, count: int = 5) -> str:
    """Search the live web via Brave Search and return source titles, URLs, and snippets."""
    query = query.strip()
    if not query or len(query) > 400:
        raise ValueError("query must contain 1-400 characters")
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY is not configured; add it to the environment and restart Claude Code")
    count = max(1, min(int(count), 8))
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": query, "count": count, "safesearch": "moderate"}
    )
    payload = request_json(url, {"X-Subscription-Token": api_key, "Accept": "application/json"})
    results = payload.get("web", {}).get("results", [])
    return json.dumps(
        {
            "query": query,
            "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sources": [
                {"title": item.get("title", ""), "url": item.get("url", ""), "snippet": item.get("description", "")}
                for item in results[:count]
                if item.get("url", "").startswith(("https://", "http://"))
            ],
        },
        ensure_ascii=False,
    )


@mcp.tool()
def get_weather_forecast(latitude: float, longitude: float, start_date: str, end_date: str) -> str:
    """Fetch daily event-location weather from Open-Meteo; forecast dates must be within 16 days."""
    if not -90 <= float(latitude) <= 90 or not -180 <= float(longitude) <= 180:
        raise ValueError("latitude/longitude are outside valid ranges")
    try:
        start = dt.date.fromisoformat(start_date)
        end = dt.date.fromisoformat(end_date)
    except ValueError as exc:
        raise ValueError("dates must use YYYY-MM-DD") from exc
    today = dt.date.today()
    if end < start or start < today or end > today + dt.timedelta(days=16):
        raise ValueError("Open-Meteo forecast is available only for dates from today through 16 days ahead")
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "auto",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
    )
    payload = request_json("https://api.open-meteo.com/v1/forecast?" + query)
    return json.dumps(
        {
            "location": {"latitude": latitude, "longitude": longitude, "timezone": payload.get("timezone")},
            "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "daily": payload.get("daily", {}),
            "source": "https://open-meteo.com/en/docs",
            "units": payload.get("daily_units", {}),
            "forecast_horizon_note": "Forecast; conditions are uncertain and should be rechecked near the event.",
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
