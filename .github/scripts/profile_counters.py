#!/usr/bin/env python3
"""Compute the profile counters and write them as shields.io endpoint files.

shields.io can read a badge straight from the GitHub API, but those dynamic
badges share one rate limit across every shields user and go blank often.
Computing the numbers here instead — in the workflow that already publishes to
the output branch — costs one authenticated request and makes the badges as
reliable as the branch itself.

Usage:
    GITHUB_TOKEN=... profile_counters.py --user LOGIN --out DIR
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

API = "https://api.github.com/graphql"
TZ = ZoneInfo("America/Sao_Paulo")

# Sampled from the profile banner, warmest to deepest.
COLOR_REPOS = "C92227"
COLOR_COMMITS = "7C1D40"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
    }
  }
}
"""


def month_bounds(now: dt.datetime) -> tuple[str, str]:
    """UTC ISO bounds of the calendar month `now` falls in, local time."""
    last_day = calendar.monthrange(now.year, now.month)[1]
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(day=last_day, hour=23, minute=59, second=59,
                      microsecond=0)
    to_utc = lambda d: d.astimezone(dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    return to_utc(start), to_utc(end)


def fetch(login: str, token: str, now: dt.datetime) -> tuple[int, int]:
    start, end = month_bounds(now)
    payload = json.dumps({
        "query": QUERY,
        "variables": {"login": login, "from": start, "to": end},
    }).encode()
    request = urllib.request.Request(
        API,
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-profile-counters",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)

    if "errors" in body:
        raise SystemExit(f"graphql error: {body['errors']}")

    user = body["data"]["user"]
    if user is None:
        raise SystemExit(f"user {login!r} not found")

    return (user["repositories"]["totalCount"],
            user["contributionsCollection"]["totalCommitContributions"])


def write_badge(path: str, label: str, message: str, color: str) -> None:
    """Write one shields.io endpoint file.

    See https://shields.io/badges/endpoint-badge — style stays in the badge
    URL so the README keeps control of how the row looks.
    """
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({
            "schemaVersion": 1,
            "label": label,
            "message": message,
            "color": color,
            "cacheSeconds": 3600,
        }, fh, ensure_ascii=False)
        fh.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set")

    now = dt.datetime.now(TZ)
    try:
        repos, commits = fetch(args.user, token, now)
    except urllib.error.HTTPError as err:
        raise SystemExit(f"github api returned {err.code}: {err.read()[:200]}")

    write_badge(os.path.join(args.out, "counters-repos.json"),
                "public repos", str(repos), COLOR_REPOS)
    write_badge(os.path.join(args.out, "counters-commits.json"),
                f"commits in {now:%b}", str(commits), COLOR_COMMITS)

    print(f"public repos: {repos} | commits in {now:%B}: {commits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
