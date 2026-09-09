#!/usr/bin/env python3
"""Add month labels on top of a snk (Platane/snk) contribution-grid SVG.

The snk action only renders the grid of day cells; GitHub's own contribution
graph also shows a month ruler above it. This script infers the grid geometry
from the generated SVG, maps each column back to a calendar week, and injects
the month labels in a strip added above the drawing area.

Usage:
    add_month_labels.py FILE.svg [--color '#57606a'] [--lang en|pt]
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "pt": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
           "Jul", "Ago", "Set", "Out", "Nov", "Dez"],
}

FONT = ('-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,'
        'sans-serif')

# Vertical room added above the original viewBox to host the labels.
STRIP_HEIGHT = 20
# Baseline offset of the text, measured from the original top of the viewBox.
BASELINE_OFFSET = 6
# Minimum gap (in columns) between the first label and the next one, so a
# nearly-finished month at the left edge does not collide with its successor.
MIN_FIRST_GAP = 3

CELL_RE = re.compile(r'<rect class="c[^"]*" x="([-\d.]+)" y="([-\d.]+)"')
VIEWBOX_RE = re.compile(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"')
HEIGHT_RE = re.compile(r'(<svg\b[^>]*?)height="([\d.]+)"')


def read_grid(svg: str) -> tuple[list[float], int]:
    """Return the sorted column x positions and the row index of the last cell.

    The last column of a snk grid is the current (partial) week, so the number
    of cells in it tells us today's weekday index (Sunday == 0).
    """
    cells = [(float(x), float(y)) for x, y in CELL_RE.findall(svg)]
    if not cells:
        raise SystemExit("no contribution cells found; is this a snk svg?")

    columns = sorted({x for x, _ in cells})
    last_x = columns[-1]
    rows = sorted({y for x, y in cells if x == last_x})
    ys = sorted({y for _, y in cells})
    return columns, ys.index(rows[-1])


def month_labels(columns: list[float], today_row: int, today: dt.date,
                 lang: str) -> list[tuple[float, str]]:
    """Pair each column that opens a new month with its label."""
    last_col = len(columns) - 1
    names = MONTHS[lang]

    # Sunday that opens each column.
    sundays = [today - dt.timedelta(days=(last_col - i) * 7 + today_row)
               for i in range(len(columns))]

    labels: list[tuple[int, str]] = [(0, names[sundays[0].month - 1])]
    for i in range(1, len(sundays)):
        if sundays[i].month != sundays[i - 1].month:
            labels.append((i, names[sundays[i].month - 1]))

    # Drop the leading label when its month has almost no room left on screen.
    if len(labels) > 1 and labels[1][0] < MIN_FIRST_GAP:
        labels.pop(0)

    return [(columns[i], name) for i, name in labels]


def inject(svg: str, labels: list[tuple[float, str]], color: str) -> str:
    m = VIEWBOX_RE.search(svg)
    if not m:
        raise SystemExit("no viewBox found; is this a snk svg?")
    min_x, min_y, width, height = (float(v) for v in m.groups())

    if 'class="month"' in svg:
        raise SystemExit("month labels already present")

    svg = svg.replace(
        m.group(0),
        f'viewBox="{min_x:g} {min_y - STRIP_HEIGHT:g} {width:g} '
        f'{height + STRIP_HEIGHT:g}"',
        1,
    )
    svg = HEIGHT_RE.sub(
        lambda h: f'{h.group(1)}height="{float(h.group(2)) + STRIP_HEIGHT:g}"',
        svg,
        count=1,
    )

    baseline = min_y - BASELINE_OFFSET
    style = (f'<style>.month{{font:10px {FONT};fill:{color}}}</style>')
    texts = "".join(
        f'<text class="month" x="{x:g}" y="{baseline:g}">{name}</text>'
        for x, name in labels
    )
    return svg.replace("</svg>", f"{style}{texts}</svg>", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--color", default="#57606a",
                        help="label color (default: GitHub light muted)")
    parser.add_argument("--lang", default="en", choices=sorted(MONTHS))
    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as fh:
        svg = fh.read()

    columns, today_row = read_grid(svg)
    labels = month_labels(columns, today_row, dt.date.today(), args.lang)
    with open(args.file, "w", encoding="utf-8") as fh:
        fh.write(inject(svg, labels, args.color))

    print(f"{args.file}: {len(labels)} month labels "
          f"({', '.join(n for _, n in labels)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
