#!/usr/bin/env python3
"""Render a "Most Used Languages" card as a standalone SVG.

The usual source for this card is the public github-readme-stats instance,
which is rate limited for everyone at once and goes down for long stretches.
Since the workflow already talks to the GraphQL API and publishes to the
output branch, the card is built here instead and depends on nothing else.

Usage:
    GITHUB_TOKEN=... top_languages.py --user LOGIN --out PATH
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"

WIDTH = 340
PAD = 16
# Mesma cor dos demais títulos do perfil, que seguem o tema do leitor.
TITLE_LIGHT = "#1F2328"
TITLE_DARK = "#e6edf3"
TEXT_COLOR = "#7d8590"
TRACK_COLOR = "#7d859033"
FONT = ('-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,'
        'sans-serif')

TITLE_Y = 15
BAR_Y, BAR_H = 33, 9
LEGEND_Y, ROW_H, COLS = 63, 20, 2

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER,
                 isFork: false, privacy: PUBLIC) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch_languages(login: str, token: str) -> dict[str, tuple[int, str]]:
    """Total bytes per language across the user's own public, non-fork repos."""
    totals: dict[str, tuple[int, str]] = {}
    cursor = None

    while True:
        payload = json.dumps({
            "query": QUERY,
            "variables": {"login": login, "cursor": cursor},
        }).encode()
        request = urllib.request.Request(API, data=payload, headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-top-languages",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)

        if "errors" in body:
            raise SystemExit(f"graphql error: {body['errors']}")

        repos = body["data"]["user"]["repositories"]
        for repo in repos["nodes"]:
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                size, color = totals.get(name, (0, edge["node"]["color"]))
                totals[name] = (size + edge["size"], color or "#8b949e")

        if not repos["pageInfo"]["hasNextPage"]:
            return totals
        cursor = repos["pageInfo"]["endCursor"]


def build(langs: list[tuple[str, float, str]], title: str) -> str:
    """langs: (name, percentage, colour), already sorted and trimmed.

    A media query would be simpler than shipping two files, but Chrome
    renders an <img>-embedded SVG under the light scheme regardless of the
    page, so the theme has to be chosen outside, by <picture>.
    """
    rows = (len(langs) + COLS - 1) // COLS
    height = LEGEND_Y + rows * ROW_H
    inner = WIDTH - PAD * 2

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="Most used languages">',
        f"<style>text{{font-family:{FONT}}}"
        f".t{{font-size:15px;font-weight:600;fill:{title}}}"
        f".l{{font-size:11.5px;fill:{TEXT_COLOR}}}</style>",
        f'<text class="t" x="{PAD}" y="{TITLE_Y}">Most Used Languages</text>',
        f'<rect x="{PAD}" y="{BAR_Y}" width="{inner}" height="{BAR_H}" '
        f'rx="{BAR_H / 2}" fill="{TRACK_COLOR}"/>',
        # The bar is clipped to its own rounded shape so the segments inside
        # can be plain rectangles and still end with round caps.
        f'<clipPath id="bar"><rect x="{PAD}" y="{BAR_Y}" width="{inner}" '
        f'height="{BAR_H}" rx="{BAR_H / 2}"/></clipPath>',
        '<g clip-path="url(#bar)">',
    ]

    x = float(PAD)
    for _, pct, color in langs:
        w = inner * pct / 100
        out.append(f'<rect x="{x:.1f}" y="{BAR_Y}" width="{w:.1f}" '
                   f'height="{BAR_H}" fill="{color}"/>')
        x += w
    out.append("</g>")

    col_w = inner / COLS
    for i, (name, pct, color) in enumerate(langs):
        cx = PAD + (i % COLS) * col_w
        cy = LEGEND_Y + (i // COLS) * ROW_H
        out.append(f'<circle cx="{cx + 5:.1f}" cy="{cy:.1f}" r="5" '
                   f'fill="{color}"/>')
        out.append(f'<text class="l" x="{cx + 16:.1f}" y="{cy + 4:.1f}">'
                   f"{escape(name)} {pct:.1f}%</text>")

    out.append("</svg>")
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--theme", default="light",
                        choices=("light", "dark"))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")

    totals = fetch_languages(args.user, token)
    if not totals:
        raise SystemExit("no languages found")

    ranked = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)
    top = ranked[:args.count]
    # Percentages are of the top slice, so the bar fills the track exactly.
    total = sum(size for _, (size, _) in top)
    langs = [(name, size / total * 100, color) for name, (size, color) in top]

    with open(args.out, "w", encoding="utf-8") as fh:
        title = TITLE_DARK if args.theme == "dark" else TITLE_LIGHT
        fh.write(build(langs, title) + "\n")

    print(f"{args.out}: " + ", ".join(f"{n} {p:.1f}%" for n, p, _ in langs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
