"""The four-score plot: masked delta score as a bar, raw delta score as a dot.

One plot per scored row, on a fixed 0-1 axis with solid hairline reference lines at
the cutoffs characterised in the SpliceAI paper. Colours come from CSS tokens
(series-1 for masked bars, series-2 for raw dots; palette validated for light and
dark), so the SVG itself contains no hex values. Text uses ink tokens, never series
colours. Each event is a focusable hit target carrying its values for the tooltip;
the same values are in the table beside the plot. Missing values are not drawn.
"""

from __future__ import annotations

from html import escape

from biobridge.results import EVENT_NAMES, EVENTS, Row

W, H = 460, 236
LEFT, RIGHT, TOP, BOTTOM = 44, 124, 14, 46
PLOT_W, PLOT_H = W - LEFT - RIGHT, H - TOP - BOTTOM
BAND = PLOT_W / len(EVENTS)
BAR = 24      # bar thickness cap
RADIUS = 4    # rounded data end
DOT_R = 5     # raw marker radius (>= 8 px diameter)
CUTOFFS = ((0.2, "high recall"), (0.5, "recommended"), (0.8, "high precision"))


def _y(value: float) -> float:
    return TOP + PLOT_H * (1.0 - value)


def _bar_path(x: float, value: float) -> str:
    """A bar from the baseline with a rounded top and a square base."""
    top, base = _y(value), _y(0.0)
    h = base - top
    r = min(RADIUS, h, BAR / 2)
    return (f"M{x:.1f},{base:.1f} V{top + r:.1f} Q{x:.1f},{top:.1f} {x + r:.1f},{top:.1f} "
            f"H{x + BAR - r:.1f} Q{x + BAR:.1f},{top:.1f} {x + BAR:.1f},{top + r:.1f} V{base:.1f} Z")


def _fmt(v: float | None) -> str:
    return "NA" if v is None else f"{v:.2f}"


def four_score_svg(row: Row, uid: str) -> str:
    """Return an inline SVG for a scored row (empty string if the row has no scores)."""
    if all(row.raw.get(e) is None for e in EVENTS):
        return ""
    variant = f"{row.chrom}:{row.pos:,} {row.ref}>{row.alt}"
    title = f"Delta scores for {variant} in {row.gene}"
    desc = "; ".join(f"{EVENT_NAMES[e]} masked {_fmt(row.masked.get(e))}, raw {_fmt(row.raw.get(e))}"
                     for e in EVENTS)
    out = [f'<svg class="bb-plot" viewBox="0 0 {W} {H}" role="group" aria-labelledby="{uid}-t {uid}-d" '
           f'xmlns="http://www.w3.org/2000/svg">',
           f'<title id="{uid}-t">{escape(title)}</title>', f'<desc id="{uid}-d">{escape(desc)}</desc>']

    # Recessive scaffolding: hairline grid at 0 and 1, labelled reference lines at the cutoffs.
    for value in (0.0, 1.0):
        cls = "bb-axis" if value == 0.0 else "bb-grid"
        out.append(f'<line class="{cls}" x1="{LEFT}" x2="{LEFT + PLOT_W}" y1="{_y(value):.1f}" y2="{_y(value):.1f}"/>')
        out.append(f'<text class="bb-tick" x="{LEFT - 8}" y="{_y(value) + 4:.1f}" text-anchor="end">{value:.1f}</text>')
    for value, name in CUTOFFS:
        y = _y(value)
        out.append(f'<line class="bb-grid" x1="{LEFT}" x2="{LEFT + PLOT_W}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="bb-tick" x="{LEFT - 8}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
        out.append(f'<text class="bb-ref" x="{LEFT + PLOT_W + 8}" y="{y + 4:.1f}">{name}</text>')

    for i, event in enumerate(EVENTS):
        cx = LEFT + BAND * i + BAND / 2
        x = cx - BAR / 2
        masked, raw = row.masked.get(event), row.raw.get(event)
        position = row.position(event)
        label = (f"{EVENT_NAMES[event].capitalize()}: masked {_fmt(masked)}, raw {_fmt(raw)}"
                 + (f", at {row.chrom}:{position:,}" if position is not None else ""))
        out.append(f'<g class="bb-mark" tabindex="0" role="img" aria-label="{escape(label)}" '
                   f'data-event="{escape(EVENT_NAMES[event].capitalize())}" data-masked="{_fmt(masked)}" '
                   f'data-raw="{_fmt(raw)}" data-position="{escape(f"{row.chrom}:{position:,}") if position else "NA"}">')
        # Hit target: the whole band, larger than the mark.
        out.append(f'<rect class="bb-hit" x="{LEFT + BAND * i:.1f}" y="{TOP}" width="{BAND:.1f}" height="{PLOT_H}"/>')
        if masked is not None and masked > 0:
            out.append(f'<path class="bb-bar" d="{_bar_path(x, masked)}"/>')
        if raw is not None:
            out.append(f'<circle class="bb-dot" cx="{cx:.1f}" cy="{_y(raw):.1f}" r="{DOT_R}"/>')
        # One direct label per event, at the top of whichever mark is higher.
        if masked is not None:
            tip = max(masked, raw or 0.0)
            text = "masked" if (masked == 0.0 and raw is not None and raw >= 0.01) else f"{masked:.2f}"
            out.append(f'<text class="bb-value" x="{cx:.1f}" y="{_y(tip) - DOT_R - 5:.1f}" '
                       f'text-anchor="middle">{text}</text>')
        out.append("</g>")
        out.append(f'<text class="bb-cat" x="{cx:.1f}" y="{TOP + PLOT_H + 18:.1f}" text-anchor="middle">{event}</text>')
        out.append(f'<text class="bb-catname" x="{cx:.1f}" y="{TOP + PLOT_H + 33:.1f}" '
                   f'text-anchor="middle">{EVENT_NAMES[event]}</text>')
    out.append("</svg>")
    return "".join(out)
