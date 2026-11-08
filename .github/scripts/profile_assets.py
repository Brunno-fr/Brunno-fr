#!/usr/bin/env python3
"""Build truthful, self-hosted SVG cards for the Brunno-fr profile README."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGIN = "Brunno-fr"
OUT = Path("dist")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REST = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"


def request_json(url: str, body: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Brunno-fr-profile-assets",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    payload = json.dumps(body).encode() if body is not None else None
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=payload, headers=headers)
    try:
        with urlopen(req, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"GitHub API request failed: {url} ({exc})") from exc


def svg_shell(title: str, width: int, height: int, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
<defs><linearGradient id="accent" x1="0" x2="1"><stop stop-color="#ff6a00"/><stop offset="1" stop-color="#9d4edd"/></linearGradient></defs>
<rect width="100%" height="100%" rx="14" fill="#0d1117" stroke="#30363d"/>
{body}</svg>'''


def text(x: int, y: int, value: str, size: int = 14, color: str = "#c9d1d9", weight: int = 400) -> str:
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}">{escape(value)}</text>'


def write_stats(repos: list[dict], languages: dict[str, int], total_contributions: int) -> None:
    # Keep all totals limited to repositories GitHub marks public.
    repos = [repo for repo in repos if repo.get("private") is False]
    owned = [r for r in repos if not r.get("fork") and not r.get("archived")]
    public_count = len(repos)
    stars = sum(r.get("stargazers_count", 0) for r in owned)
    forks = sum(r.get("forks_count", 0) for r in owned)
    metrics = [
        ("CONTRIBUTIONS · 12 MONTHS", total_contributions),
        ("PUBLIC REPOSITORIES", public_count),
        ("STARS RECEIVED · OWN REPOS", stars),
        ("FORKS · OWN REPOS", forks),
    ]
    pieces = [text(24, 34, "GitHub public activity", 19, "#f0f6fc", 700)]
    pieces.append('<rect x="24" y="47" width="116" height="3" rx="2" fill="url(#accent)"/>')
    for i, (label, value) in enumerate(metrics):
        x = 24 + (i % 2) * 226
        y = 80 + (i // 2) * 56
        pieces.append(text(x, y, f"{value:,}", 23, "#ff8a24", 700))
        pieces.append(text(x, y + 19, label, 9, "#8b949e", 600))
    pieces.append(text(24, 158, "Source: GitHub public API · refreshed daily", 10, "#6e7681"))
    OUT.joinpath("github-stats.svg").write_text(svg_shell("GitHub public activity statistics", 480, 176, "\n".join(pieces)), encoding="utf-8")


def write_languages(languages: dict[str, int]) -> None:
    sorted_langs = sorted(languages.items(), key=lambda item: item[1], reverse=True)[:7]
    total = sum(languages.values())
    pieces = [text(24, 34, "Top languages · public repositories", 18, "#f0f6fc", 700)]
    pieces.append('<rect x="24" y="47" width="116" height="3" rx="2" fill="url(#accent)"/>')
    if total == 0:
        pieces.append(text(24, 88, "No language data in public repositories yet.", 13, "#8b949e"))
    else:
        y = 75
        colors = ["#ff6a00", "#9d4edd", "#ff9b40", "#bd72df", "#d45d18", "#8063a6", "#b54b15"]
        for index, (name, size) in enumerate(sorted_langs):
            percent = size * 100 / total
            pieces.append(text(24, y + 12, name, 12, "#c9d1d9", 600))
            pieces.append(text(448, y + 12, f"{percent:.1f}%", 11, "#8b949e", 500))
            pieces.append(f'<rect x="24" y="{y + 20}" width="424" height="7" rx="4" fill="#21262d"/>')
            pieces.append(f'<rect x="24" y="{y + 20}" width="{max(2, 424 * percent / 100):.1f}" height="7" rx="4" fill="{colors[index]}"/>')
            y += 39
    pieces.append(text(24, 354, "Measured from language bytes in non-fork public repositories", 10, "#6e7681"))
    OUT.joinpath("top-languages.svg").write_text(svg_shell("Most used languages in public repositories", 480, 372, "\n".join(pieces)), encoding="utf-8")


def write_contributions(calendar: dict, from_date: datetime, to_date: datetime) -> None:
    weeks = calendar["weeks"]
    cell, gap, left, top = 11, 4, 48, 67
    width = left + len(weeks) * (cell + gap) + 20
    height = 190
    pieces = [text(20, 31, "Contribution graph · last 12 months", 17, "#f0f6fc", 700)]
    pieces.append(text(20, 52, f"{calendar['totalContributions']:,} contributions · {from_date:%d %b %Y} – {to_date:%d %b %Y}", 11, "#8b949e"))
    colors = ["#161b22", "#42220f", "#783b13", "#bd5316", "#ff8a24"]
    for row, label in enumerate(("Mon", "Wed", "Fri")):
        pieces.append(text(8, top + row * 2 * (cell + gap) + 10, label, 9, "#6e7681"))
    previous_month = None
    for wi, week in enumerate(weeks):
        days = week["contributionDays"]
        if days:
            month = datetime.fromisoformat(days[0]["date"]).strftime("%b")
            if month != previous_month:
                pieces.append(text(left + wi * (cell + gap), 63, month, 9, "#8b949e"))
                previous_month = month
        for day in days:
            date = datetime.fromisoformat(day["date"])
            # GitHub weekday: Sunday=0; place Monday at top.
            row = (date.weekday())
            count = day["contributionCount"]
            bucket = 0 if count == 0 else 1 if count <= 2 else 2 if count <= 5 else 3 if count <= 9 else 4
            x = left + wi * (cell + gap)
            y = top + row * (cell + gap)
            pieces.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{colors[bucket]}" stroke="#30363d" stroke-width=".5"><title>{date:%Y-%m-%d}: {count} contributions</title></rect>')
    pieces.append(text(width - 142, height - 12, "Less  ▪ ▪ ▪ ▪  More", 10, "#8b949e"))
    OUT.joinpath("contribution-graph.svg").write_text(svg_shell("GitHub contribution graph for the last 12 months", width, height, "\n".join(pieces)), encoding="utf-8")


def write_header() -> None:
    body = '''<rect x="1" y="1" width="998" height="168" rx="13" fill="#0a0d12" stroke="#30363d"/>
<path d="M26 42h20l10 12-10 12H26" fill="none" stroke="#ff6a00" stroke-width="4"/>
<text x="76" y="65" fill="#ff8a24" font-family="Consolas,monospace" font-size="32" font-weight="700">Hello, World! I'm Brunno</text>
<text x="77" y="101" fill="#c9d1d9" font-family="Consolas,monospace" font-size="17">Olá, mundo! Eu sou Brunno  ·  Developer | Technology Enthusiast</text>
<text x="77" y="132" fill="#9d4edd" font-family="Consolas,monospace" font-size="15">Building ideas into code  ·  Computer Engineering</text>
<rect x="77" y="146" width="870" height="2" fill="#21262d"/><rect x="77" y="146" width="870" height="2" fill="url(#accent)"><animate attributeName="opacity" values=".35;1;.35" dur="2.4s" repeatCount="indefinite"/></rect>
<rect x="950" y="42" width="3" height="30" fill="#ff6a00"><animate attributeName="opacity" values="1;0;1" dur=".9s" repeatCount="indefinite"/></rect>'''
    OUT.joinpath("profile-header.svg").write_text(svg_shell("Hello, World! I'm Brunno · Developer · Computer Engineering", 1000, 170, body), encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    page = 1
    repos: list[dict] = []
    while True:
        result = request_json(f"{REST}/users/{LOGIN}/repos?type=owner&per_page=100&sort=updated&page={page}")
        if not result:
            break
        repos.extend(result)
        if len(result) < 100:
            break
        page += 1

    # Keep all totals limited to repositories GitHub marks public.
    repos = [repo for repo in repos if repo.get("private") is False]
    owned = [r for r in repos if not r.get("fork") and not r.get("archived")]
    language_totals: dict[str, int] = {}
    # Avoid one request for forks and archived repositories; query each owned public repo's exact language byte counts.
    for repo in owned:
        data = request_json(repo["languages_url"])
        for language, size in data.items():
            language_totals[language] = language_totals.get(language, 0) + size

    end = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0)
    start = end - timedelta(days=365)
    query = '''query($login:String!, $from:DateTime!, $to:DateTime!){user(login:$login){contributionsCollection(from:$from,to:$to){contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}'''
    result = request_json(GRAPHQL, {"query": query, "variables": {"login": LOGIN, "from": start.isoformat(), "to": end.isoformat()}})
    if result.get("errors") or not result.get("data", {}).get("user"):
        raise RuntimeError("GitHub GraphQL did not return a public contribution calendar: " + json.dumps(result.get("errors", [])))
    calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    write_stats(repos, language_totals, calendar["totalContributions"])
    write_languages(language_totals)
    write_contributions(calendar, start, end)
    write_header()
    print(f"Generated profile SVGs from {len(repos)} public repositories and {calendar['totalContributions']} contributions.")


if __name__ == "__main__":
    main()


