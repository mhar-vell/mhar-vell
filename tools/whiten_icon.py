#!/usr/bin/env python3
"""Repaint a devicon SVG white, for use on a dark background.

The three icons this exists for are monochrome and nearly black, which
leaves them invisible against a dark profile. Their colour arrives three
different ways — a fill attribute, an inline style, or nothing at all and
therefore the default — so rather than rewrite each shape, an !important
rule is injected, which outranks all three.

Usage:
    whiten_icon.py SOURCE.svg DEST.svg [--color '#fff']
"""

from __future__ import annotations

import argparse
import re
import sys

RULE = "<style>*{fill:%s !important;stroke:none !important}</style>"


def whiten(svg: str, color: str) -> str:
    match = re.search(r"<svg[^>]*>", svg)
    if not match:
        raise SystemExit("no <svg> element found")
    end = match.end()
    return svg[:end] + RULE % color + svg[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("dest")
    parser.add_argument("--color", default="#ffffff")
    args = parser.parse_args()

    with open(args.source, encoding="utf-8") as fh:
        svg = fh.read()
    with open(args.dest, "w", encoding="utf-8") as fh:
        fh.write(whiten(svg, args.color))

    print(f"{args.dest}: repainted {args.color}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
