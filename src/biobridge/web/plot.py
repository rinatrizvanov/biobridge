"""The four-score plot: masked delta score as a bar, raw delta score as a dot.

One plot per scored row, on a fixed 0-1 axis. Hairline reference lines mark the
cutoffs characterised in the SpliceAI paper (0.2, 0.5, 0.8); their meaning is given
in the figure caption, so the plot needs no labels beside it and stays readable at
narrow widths. Margins leave room for a value label above a score of 1.00 and for
two-line category names. Colours come from CSS tokens (series-1 masked bars,
series-2 raw dots; validated for light and dark), so the SVG contains no hex values.
Text uses ink tokens. Each event is a focusable hit target that carries its values
for the tooltip; the same values are in the table beside the plot. Missing values
are not drawn.
"""

from __future__ import annotations

from html import escape

from biobridge.results import EVENT_NAMES, EVENTS, Row, short_allele

W, H = 360, 266
LEFT, RIGHT, TOP, BOTTOM = 40, 12, 30, 62
PLOT_W, PLOT_H = W - LEFT - RIGHT, H - TOP - BOTTOM
BAND = PLOT_W / len(EVENTS)
BAR = 22      # bar thickness (<= 24)
RADIUS = 4    # rounded data end
DOT_R = 5     # raw marker radius (>= 8 px diameter), plus a 2 px surface ring
TICK, VALUE, CODE, NAME = 11, 12, 12, 11   # font sizes in SVG units
TICKS = (0.0, 0.2, 0.5, 0.8, 1.0)


def _y(value: float) -> float:
    return TOP + PLOT_H * (1.0 - value)


def _bar_path(x: float, value: float) -> str:
    """A bar from the baseline with a rounded top and a square base."""
    top, base = _y(value), _y(0.0)
    r = min(RADIUS, base - top, BAR / 2)
    return (f"M{x:.1f},{base:.1f} V{top + r:.1f} Q{x:.1f},{top:.1f} {x + r:.1f},{top:.1f} "
            f"H{x + BAR - r:.1f} Q{x + BAR:.1f},{top:.1f} {x + BAR:.1f},{top + r:.1f} V{base:.1f} Z")


def _fmt(v: float | None) -> str:
    return "NA" if v is None else f"{v:.2f}"


def _text(cls: str, x: float, y: float, size: int, content: str, anchor: str = "middle") -> str:
    return (f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'text-anchor="{anchor}">{escape(content)}</text>')


def four_score_svg(row: Row, uid: str) -> str:
    """Return an inline SVG for a scored row (empty string if the row has no scores)."""
    if all(row.raw.get(e) is None for e in EVENTS):
        return ""
    variant = f"{row.chrom}:{row.pos:,} {short_allele(row.ref)}>{short_allele(row.alt)}"
    title = f"Delta scores for {variant} in {row.gene}"
    desc = "; ".join(f"{EVENT_NAMES[e]} masked {_fmt(row.masked.get(e))}, raw {_fmt(row.raw.get(e))}"
                     for e in EVENTS)
    out = [f'<svg class="bb-plot" viewBox="0 0 {W} {H}" role="group" aria-labelledby="{uid}-t {uid}-d" '
           f'xmlns="http://www.w3.org/2000/svg">',
           f'<title id="{uid}-t">{escape(title)}</title>', f'<desc id="{uid}-d">{escape(desc)}</desc>']

    for value in TICKS:
        y = _y(value)
        cls = "bb-axis" if value == 0.0 else ("bb-grid" if value == 1.0 else "bb-ref-line")
        out.append(f'<line class="{cls}" x1="{LEFT}" x2="{LEFT + PLOT_W}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(_text("bb-tick", LEFT - 8, y + 4, TICK, f"{value:.1f}", "end"))

    for i, event in enumerate(EVENTS):
        band_x = LEFT + BAND * i
        cx = band_x + BAND / 2
        masked, raw = row.masked.get(event), row.raw.get(event)
        position = row.position(event)
        where = f"{row.chrom}:{position:,}" if position is not None else "NA"
        label = f"{EVENT_NAMES[event].capitalize()}: masked {_fmt(masked)}, raw {_fmt(raw)}, at {where}"
        out.append(f'<g class="bb-mark" tabindex="0" role="img" aria-label="{escape(label)}" '
                   f'data-event="{escape(EVENT_NAMES[event].capitalize())}" data-masked="{_fmt(masked)}" '
                   f'data-raw="{_fmt(raw)}" data-position="{escape(where)}">')
        # Hit and focus target: the whole band, larger than the marks.
        out.append(f'<rect class="bb-hit" x="{band_x + 2:.1f}" y="{TOP - 24}" width="{BAND - 4:.1f}" '
                   f'height="{PLOT_H + 24}" rx="4"/>')
        if masked is not None and masked > 0:
            out.append(f'<path class="bb-bar" d="{_bar_path(cx - BAR / 2, masked)}"/>')
        if raw is not None:
            out.append(f'<circle class="bb-dot" cx="{cx:.1f}" cy="{_y(raw):.1f}" r="{DOT_R}"/>')
        if masked is not None:  # one direct label, above whichever mark is higher
            tip = max(masked, raw or 0.0)
            text = "masked" if (masked == 0.0 and raw is not None and raw >= 0.01) else f"{masked:.2f}"
            out.append(_text("bb-value", cx, _y(tip) - DOT_R - 6, VALUE, text))
        out.append("</g>")
        first, second = EVENT_NAMES[event].split(" ")
        out.append(_text("bb-cat", cx, TOP + PLOT_H + 20, CODE, event))
        out.append(_text("bb-catname", cx, TOP + PLOT_H + 36, NAME, first))
        out.append(_text("bb-catname", cx, TOP + PLOT_H + 51, NAME, second))  # 15-unit leading
    out.append("</svg>")
    return "".join(out)
