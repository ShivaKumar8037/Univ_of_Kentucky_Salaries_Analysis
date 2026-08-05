"""
Shared visual system for the PDF report and the interactive dashboard.

One palette, one set of type sizes, one formatter vocabulary, used everywhere, so
the two deliverables read as a single piece of work.

BRAND
-----
Built on the University of Kentucky visual identity: Wildcat Blue #0033A0, with
Mercury (serif) for display type and Avenir (sans) for text.

One deliberate departure. Wildcat Blue is a *chrome* colour here -- headers,
rules, headings -- but not a data-mark fill. Measured against the chart surface
it falls below the lightness band a categorical series needs (it fails the
validator's first check outright), and large areas of it read as a solid block
rather than a readable mark. Data marks therefore use BLUE, a lighter step of
the same hue that passes every gate. The two sit together as one blue family.

VALIDATION
----------
Hues were checked with the dataviz palette validator, not chosen by eye:
  - full-time / part-time pair (BLUE / ORANGE): all-pairs CVD deltaE 28.4,
    normal-vision 39.0, both above 3:1 contrast -- safe to carry meaning by
    colour, which is what the dashboard legend relies on.
  - four-slot categorical set: worst adjacent CVD deltaE 9.1 (target >=8),
    normal-vision 22.9 (floor >=15).
  - AQUA and YELLOW fall below 3:1 contrast on a light surface, so wherever they
    carry meaning the mark is directly labelled and never relies on hue alone.
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# --- University of Kentucky brand -------------------------------------------

UK_BLUE = "#0033A0"        # Wildcat Blue -- chrome only, never a data fill
UK_BLUE_DARK = "#00256f"   # pressed / deep chrome
UK_BLUE_TINT = "#e8eefb"   # pale wash for banded rows and callouts

# --- data palette (validated) ------------------------------------------------

BLUE = "#1b52c4"     # slot 1 -- the data-mark step of Wildcat Blue
ORANGE = "#eb6834"   # slot 2 -- pairs with BLUE for two-series charts
AQUA = "#1baf7a"     # slot 3
YELLOW = "#eda100"   # slot 4
MAGENTA = "#e87ba4"  # slot 5
VIOLET = "#4a3aa7"   # slot 6
RED = "#e34948"      # slot 7

CATEGORICAL = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, VIOLET, RED]

# Fixed semantic roles. Colour follows the entity, never its rank, so these do
# not get reassigned when a filter changes which series are on screen.
FULL_TIME = BLUE
PART_TIME = ORANGE
PREV_YEAR = "#b0aea6"   # neutral: last year is context
CURR_YEAR = BLUE        # this year is the subject
MISSING = "#c9c7bf"     # "Not reported" -- deliberately colourless

# Single-hue sequential ramp (blue, light -> dark)
SEQUENTIAL = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
    "#184f95", "#104281", "#0d366b",
]

# Chrome and ink
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# De-emphasis fill for "everything except the point being made"
CONTEXT = "#d8d7d0"

# Avenir is the UK brand sans and ships with macOS; the rest are graceful
# fallbacks. Mercury is a licensed serif, so the display stack falls back to
# widely available serifs rather than shipping a substitute that pretends to be it.
FONT_STACK = ["Avenir Next", "Avenir", "Nunito Sans", "Helvetica Neue", "Arial", "DejaVu Sans"]
SERIF_STACK = ["Mercury Display", "Georgia", "Times New Roman", "DejaVu Serif"]

# Author / attribution, carried into both deliverables.
AUTHOR = "Shiva Kumar P"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/shivakumar-p-/"
AUTHOR_GITHUB = "https://github.com/ShivaKumar8037"

# The interactive companion to the PDF. Every page of the report links here, so
# a reader who arrives with only the PDF can always reach the live version.
DASHBOARD_URL = "https://shivakumar8037.github.io/Univ_of_Kentucky_Salaries_Analysis/"


def _available(stack: list[str]) -> list[str]:
    """Keep only fonts installed on this machine, preserving preference order.

    Mercury is a licensed face and Avenir ships with macOS, so neither is
    guaranteed. Filtering here keeps matplotlib from emitting a findfont warning
    per text object and silently choosing something arbitrary.
    """
    from matplotlib import font_manager
    installed = {f.name for f in font_manager.fontManager.ttflist}
    found = [f for f in stack if f in installed]
    return found or stack[-1:]


def apply_style() -> None:
    """Set matplotlib rcParams for the whole report."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": "sans-serif",
            "font.sans-serif": _available(FONT_STACK),
            "font.serif": _available(SERIF_STACK),
            "text.color": INK,
            "axes.labelcolor": INK_SECONDARY,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "grid.linestyle": "-",
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.labelsize": 10,
            "axes.titlesize": 12,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "figure.dpi": 110,
            "pdf.fonttype": 42,  # embed TrueType so text stays selectable
        }
    )


def strip_spines(ax, keep=("left", "bottom")) -> None:
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


def no_grid_x(ax) -> None:
    ax.grid(axis="x", visible=False)


def no_grid_y(ax) -> None:
    ax.grid(axis="y", visible=False)


# --- formatters --------------------------------------------------------------

def usd(value: float, decimals: int = 0) -> str:
    return f"${value:,.{decimals}f}"


def usd_compact(value: float) -> str:
    """1_600_000 -> '$1.6M'; 87_500 -> '$88k'."""
    a = abs(value)
    if a >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    if a >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    if a >= 1_000:
        return f"${value/1_000:.0f}k"
    return f"${value:,.0f}"


def pct(value: float, decimals: int = 1) -> str:
    return f"{value*100:.{decimals}f}%"


# --- page furniture ----------------------------------------------------------

PAGE_W, PAGE_H = 11.0, 8.5  # landscape letter


def dashboard_link(fig, on_dark: bool = False) -> None:
    """Stamp the clickable pointer to the interactive dashboard, top right.

    Called by `new_page`, so every page in the report carries it — a reader who
    was handed only the PDF is never more than one click from the live version.

    Top right is the one region no page template writes into: the kicker and
    headline are left-aligned and the longest of them ends near x=0.46.

    No arrow glyph. Avenir Next has no U+2197, and a missing glyph renders as a
    tofu box, so the affordance is carried by weight and colour instead.
    """
    fig.text(0.945, 0.952, "Click here for the interactive dashboard",
             fontsize=8, fontweight="bold", ha="right", va="bottom",
             color="#cfdcf6" if on_dark else UK_BLUE,
             url=DASHBOARD_URL)


def new_page(on_dark: bool = False):
    """A blank landscape-letter figure, carrying the dashboard link.

    `on_dark` lightens that link for pages whose masthead runs under it.
    """
    fig = plt.figure(figsize=(PAGE_W, PAGE_H))
    dashboard_link(fig, on_dark=on_dark)
    return fig


def page_title(fig, kicker: str, title: str, takeaway: str | None = None) -> None:
    """Standard page header: section kicker, headline, and a plain-language takeaway.

    The takeaway is the sentence a reader should leave with. Putting it above the
    chart rather than in a caption means the point survives skim-reading.
    """
    # Spaced-out kicker: matplotlib has no letter-spacing, so space the glyphs.
    fig.text(0.055, 0.945, " ".join(kicker.upper()), fontsize=8.5, color=UK_BLUE,
             fontweight="bold")
    fig.text(0.055, 0.900, title, fontsize=19, color=INK, fontweight="bold", va="top")
    if takeaway:
        fig.text(0.055, 0.845, takeaway, fontsize=10.5, color=INK_SECONDARY,
                 va="top", wrap=True)


def page_footer(fig, note: str, page_no: int | None = None) -> None:
    fig.text(0.055, 0.035, note, fontsize=7.5, color=INK_MUTED, va="bottom")
    if page_no is not None:
        fig.text(0.945, 0.035, str(page_no), fontsize=8, color=INK_MUTED,
                 va="bottom", ha="right")


def label_bars(ax, bars, values, formatter=usd_compact, pad=None, inside=False,
               fontsize=9, color=None) -> None:
    """Direct-label horizontal bars.

    Required wherever a low-contrast hue carries meaning, and generally
    preferable to making the reader trace a bar back to an axis.
    """
    xmax = ax.get_xlim()[1]
    pad = pad if pad is not None else xmax * 0.012
    for bar, value in zip(bars, values):
        w = bar.get_width()
        y = bar.get_y() + bar.get_height() / 2
        if inside and w > xmax * 0.25:
            ax.text(w - pad, y, formatter(value), va="center", ha="right",
                    fontsize=fontsize, color=color or SURFACE, fontweight="bold")
        else:
            ax.text(w + pad, y, formatter(value), va="center", ha="left",
                    fontsize=fontsize, color=color or INK_SECONDARY)
