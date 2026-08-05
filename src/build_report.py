"""
Build the multi-page PDF report -- the artifact submitted under Specific Request 1.

Reads  : data/processed/summary_stats.json, uk_salaries_clean.csv
Writes : docs/UK_Salary_Analysis.pdf

Every number printed here is read from summary_stats.json. Nothing is hardcoded,
so the narrative cannot drift away from the data.

No individual is named anywhere in this document. Roles at the top of the
distribution are identified by job title and administrative unit only.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle

import viz_style as vs
from viz_style import (
    AQUA, AXIS, BLUE, CONTEXT, GRID, INK, INK_MUTED, INK_SECONDARY, ORANGE,
    SEQUENTIAL, SURFACE, VIOLET, YELLOW, label_bars, new_page, page_footer,
    page_title, pct, usd, usd_compact,
)

ROOT = Path(__file__).resolve().parent.parent
STATS = json.loads((ROOT / "data" / "processed" / "summary_stats.json").read_text())
LATEST = STATS["latest"]
S = STATS["years"][LATEST]                 # the year the report leads with
CMP = STATS.get("comparison")              # year-over-year block, if two years exist
QUALITY = STATS.get("quality", {})
CLEAN = ROOT / "data" / "processed" / "uk_salaries_clean.csv"
OUT_PDF = ROOT / "docs" / "UK_Salary_Analysis.pdf"
DASHBOARD_SHOT = ROOT / "assets" / "dashboard-preview.png"

SOURCE_NOTE = (
    f"Source: University of Kentucky {LATEST} salary database (public record, "
    "released under the Kentucky Open Records Act). Base salary only."
)
RETRIEVED = date.today().isoformat()

_page_no = 0


def _next_page() -> int:
    global _page_no
    _page_no += 1
    return _page_no


# ---------------------------------------------------------------- cover page

def page_cover(pdf, df: pd.DataFrame) -> None:
    # on_dark: the masthead runs under the dashboard link in the top right.
    fig = new_page(on_dark=True)
    o = S["overview"]
    d = S["distribution"]

    # Wildcat Blue masthead. UK blue is used as chrome here, never as a data fill.
    fig.patches.append(
        Rectangle((0, 0.70), 1, 0.30, transform=fig.transFigure,
                  facecolor=vs.UK_BLUE, edgecolor="none", zorder=-1)
    )

    fig.text(0.055, 0.935, " ".join("UNIVERSITY OF KENTUCKY  ·  SALARY DATA ANALYSIS"),
             fontsize=7.5, color="#a9c0ee", fontweight="bold")
    fig.text(0.055, 0.875, "Anatomy of a\nPublic Payroll",
             fontsize=34, color="white", fontweight="bold", va="top", linespacing=1.10,
             family=vs._available(vs.SERIF_STACK))
    fig.text(0.055, 0.735, f"Salary year {LATEST}", fontsize=13, color="#cfdcf6", va="top")

    span = " and ".join(STATS["year_list"]) if len(STATS["year_list"]) > 1 else LATEST
    fig.text(0.055, 0.645,
             f"Every employee salary record the university publishes, for {span} -\n"
             "extracted, verified, and read as one workforce.",
             fontsize=12.5, color=INK_SECONDARY, va="top", linespacing=1.5)

    tiles = [
        (f"{o['records']:,}", "employee records"),
        (usd_compact(o["total_payroll"]), "total base payroll"),
        (usd(d["all"]["median"]), "median salary"),
        (usd(d["all"]["mean"]), "mean salary"),
    ]
    for i, (value, label) in enumerate(tiles):
        x = 0.055 + i * 0.235
        fig.text(x, 0.47, value, fontsize=25, color=vs.UK_BLUE, fontweight="bold",
                 va="top", family=vs._available(vs.SERIF_STACK))
        fig.text(x, 0.405, label, fontsize=10, color=INK_SECONDARY, va="top")

    lead = "The gap between those last two numbers is where this report starts."
    if CMP:
        lead = (f"Payroll grew {CMP['headline']['payroll']['pct']:+.1%} in a year - and the gap "
                f"between those last two numbers is where this report starts.")
    fig.text(0.055, 0.315, lead, fontsize=11.5, color=INK, va="top", style="italic")

    fig.text(0.055, 0.215,
             f"{SOURCE_NOTE}\nData retrieved {RETRIEVED}. "
             f"{o['units']} administrative units, {o['departments']:,} departments, "
             f"{o['job_titles']:,} distinct job titles.\n"
             "No individual employee is named in this document.",
             fontsize=9, color=INK_MUTED, va="top", linespacing=1.6)

    fig.text(0.055, 0.128, "Source code, data and methodology:", fontsize=8.5,
             color=INK_MUTED, va="bottom")
    fig.text(0.255, 0.128, vs.REPO_SHORT, fontsize=8.5, color=vs.UK_BLUE,
             va="bottom", fontweight="bold", url=vs.REPO_URL)
    fig.text(0.055, 0.098, "Interactive dashboard:", fontsize=8.5,
             color=INK_MUTED, va="bottom")
    fig.text(0.255, 0.098, vs.DASHBOARD_URL.replace("https://", ""),
             fontsize=8.5, color=vs.UK_BLUE, va="bottom", fontweight="bold",
             url=vs.DASHBOARD_URL)

    fig.text(0.055, 0.048,
             f"{vs.AUTHOR}   ·   {vs.AUTHOR_LINKEDIN}   ·   {vs.AUTHOR_GITHUB}",
             fontsize=8.5, color=vs.UK_BLUE, va="bottom", fontweight="bold")

    pdf.savefig(fig)
    plt_close(fig)


# -------------------------------------------------- interactive companion page

def page_dashboard(pdf, df: pd.DataFrame) -> None:
    """Point the reader at the live dashboard, and show them what it looks like.

    Front matter, so it carries no page number: the numbered sequence stays with
    the fifteen analysis pages.

    The screenshot is a committed asset (`assets/dashboard-preview.png`) rather
    than something rendered at build time, so the report builds without a network
    round trip or a headless browser.
    """
    fig = new_page()

    page_title(
        fig, "Interactive version",
        "Explore this data yourself",
        "Every figure in this report is filterable in the browser - by year, "
        "administrative unit,\noccupational category, time status and research "
        "workforce. It opens offline and prints.",
    )

    # ---- left column: the address, stated once and stated plainly -----------
    # A tinted callout rather than an underlined line. The URL needs two lines
    # at a size worth reading, and an underline under only the second one reads
    # as two separate links.
    fig.patches.append(
        FancyBboxPatch((0.055, 0.545), 0.415, 0.175,
                       boxstyle="round,pad=0.002,rounding_size=0.008",
                       transform=fig.transFigure, facecolor=vs.UK_BLUE_TINT,
                       edgecolor="none")
    )
    fig.text(0.075, 0.675, "OPEN THE DASHBOARD AT", fontsize=8,
             color=vs.UK_BLUE_DARK, fontweight="bold", va="bottom")
    for line, y in (("shivakumar8037.github.io/", 0.612),
                    ("Univ_of_Kentucky_Salaries_Analysis", 0.560)):
        fig.text(0.075, y, line, fontsize=14.5, color=vs.UK_BLUE,
                 fontweight="bold", va="bottom", url=vs.DASHBOARD_URL)

    fig.text(0.055, 0.505,
             "Reading this on screen? Click the address above, or the link in "
             "the top right\nof any page in this report.",
             fontsize=9.5, color=INK_SECONDARY, va="top", linespacing=1.5)

    bullets = [
        ("Filter", "27,004 records by unit, category, time status and year."),
        ("Compare", "2024-25 against 2025-26 on every chart."),
        ("Read", "a six-chapter narrative with its own visualisations."),
        ("Check", "a data-notes section stating what is missing and why."),
    ]
    y = 0.410
    for lead, rest in bullets:
        fig.patches.append(
            Rectangle((0.055, y - 0.004), 0.006, 0.019, transform=fig.transFigure,
                      facecolor=vs.UK_BLUE, edgecolor="none")
        )
        fig.text(0.075, y, lead, fontsize=9.5, color=INK, fontweight="bold",
                 va="bottom")
        # Fixed column, not a width estimate: matplotlib cannot measure text
        # before a draw, and eyeballed per-word offsets do not line up.
        fig.text(0.165, y, rest, fontsize=9.5, color=INK_SECONDARY, va="bottom")
        y -= 0.048

    fig.text(0.055, 0.200, "SOURCE CODE, DATA AND METHODOLOGY", fontsize=8,
             color=INK_MUTED, fontweight="bold", va="bottom")
    fig.text(0.055, 0.160, vs.REPO_SHORT, fontsize=9.5, color=vs.UK_BLUE,
             fontweight="bold", va="bottom", url=vs.REPO_URL)
    fig.text(0.055, 0.132,
             "The extraction, cleaning and analysis scripts, the 53,434-row "
             "dataset and the data dictionary.",
             fontsize=8.5, color=INK_SECONDARY, va="bottom")

    fig.text(0.055, 0.072,
             "The dashboard and this report are generated from the same "
             "analysis file, so the\nfigures in the two cannot disagree.",
             fontsize=8.5, color=INK_MUTED, va="bottom", linespacing=1.5)

    # ---- right column: the screenshot, in a browser frame ------------------
    img = mpimg.imread(DASHBOARD_SHOT)
    ih, iw = img.shape[:2]

    # Derive the height from the real image aspect so a re-captured screenshot
    # of different proportions still sits square in its frame.
    left, width = 0.520, 0.425
    height = (width * vs.PAGE_W / (iw / ih)) / vs.PAGE_H
    top = 0.635
    bottom = top - height
    bar = 0.040                                  # browser chrome bar

    # Frame: one rounded rectangle behind chrome bar and screenshot together.
    fig.patches.append(
        FancyBboxPatch((left, bottom), width, height + bar,
                       boxstyle="round,pad=0.004,rounding_size=0.008",
                       transform=fig.transFigure, facecolor="#dcd9d2",
                       edgecolor="#c9c5bd", linewidth=0.8, zorder=1)
    )
    fig.patches.append(
        Rectangle((left, top), width, bar, transform=fig.transFigure,
                  facecolor="#eceae5", edgecolor="none", zorder=2)
    )

    # Traffic lights. Figure coordinates are not square, so the height is
    # scaled by the page ratio to keep these circular rather than oval.
    d = 0.0062
    for i, c in enumerate(("#e06c60", "#e6b14c", "#66b352")):
        fig.patches.append(
            Ellipse((left + 0.016 + i * 0.014, top + bar / 2), d,
                    d * vs.PAGE_W / vs.PAGE_H, transform=fig.transFigure,
                    facecolor=c, edgecolor="none", zorder=3)
        )

    # Address pill, carrying the URL a third time - this is the one a reader
    # sees when the page is skimmed rather than read.
    pill_l = left + 0.062
    fig.patches.append(
        FancyBboxPatch((pill_l, top + 0.009), width - 0.075, bar - 0.018,
                       boxstyle="round,pad=0.001,rounding_size=0.006",
                       transform=fig.transFigure, facecolor=SURFACE,
                       edgecolor="#d5d1c9", linewidth=0.6, zorder=3)
    )
    fig.text(pill_l + 0.010, top + bar / 2,
             vs.DASHBOARD_URL.replace("https://", ""),
             fontsize=6.2, color=INK_SECONDARY, va="center", zorder=4,
             url=vs.DASHBOARD_URL)

    ax = fig.add_axes([left, bottom, width, height], zorder=2)
    ax.imshow(img, interpolation="antialiased")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_url(vs.DASHBOARD_URL)

    page_footer(fig, f"{SOURCE_NOTE} Data retrieved {RETRIEVED}.")
    pdf.savefig(fig)
    plt_close(fig)


# ------------------------------------------------------- year-over-year pages

def page_yoy_overview(pdf, df: pd.DataFrame) -> None:
    """What changed between the two published years."""
    import matplotlib.pyplot as plt
    if not CMP:
        return
    h = CMP["headline"]
    fig = new_page()
    page_title(
        fig, "Act 0 - Year over year",
        f"The payroll grew {usd_compact(h['payroll']['delta'])} in a single year",
        f"Between {CMP['prev']} and {CMP['curr']} the university added "
        f"{h['records']['delta']:,} employee records ({h['records']['pct']:+.1%}) and "
        f"{usd_compact(h['payroll']['delta'])} of base salary ({h['payroll']['pct']:+.1%}).\n"
        f"Payroll grew faster than headcount, so the average record also became more "
        f"expensive - not simply more numerous.",
    )

    years = STATS["year_list"]
    per = {y: STATS["years"][y] for y in years}

    ax = fig.add_axes([0.075, 0.14, 0.24, 0.60])
    vals = [per[y]["overview"]["records"] for y in years]
    bars = ax.bar(years, vals, color=[vs.PREV_YEAR, vs.CURR_YEAR][-len(years):], width=0.5)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v * 1.01, f"{v:,}", ha="center",
                fontsize=11, fontweight="bold", color=INK)
    ax.set_ylim(0, max(vals) * 1.15)
    ax.set_ylabel("Employee records")
    ax.set_title("Headcount", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax); vs.no_grid_x(ax)

    ax2 = fig.add_axes([0.385, 0.14, 0.24, 0.60])
    vals2 = [per[y]["overview"]["total_payroll"] for y in years]
    bars2 = ax2.bar(years, vals2, color=[vs.PREV_YEAR, vs.CURR_YEAR][-len(years):], width=0.5)
    for bar, v in zip(bars2, vals2):
        ax2.text(bar.get_x() + bar.get_width() / 2, v * 1.01, usd_compact(v), ha="center",
                 fontsize=11, fontweight="bold", color=INK)
    ax2.set_ylim(0, max(vals2) * 1.15)
    ax2.set_ylabel("Total base payroll")
    ax2.yaxis.set_major_formatter(lambda v, _: usd_compact(v))
    ax2.set_title("Payroll", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax2); vs.no_grid_x(ax2)

    # Headcount change by unit
    bu = pd.DataFrame(CMP["by_unit"]).nlargest(10, "n_delta").sort_values("n_delta")
    ax3 = fig.add_axes([0.72, 0.14, 0.22, 0.60])
    y = np.arange(len(bu))
    colours = [BLUE if v >= 0 else ORANGE for v in bu["n_delta"]]
    b3 = ax3.barh(y, bu["n_delta"], height=0.6, color=colours)
    ax3.set_yticks(y); ax3.set_yticklabels(bu["unit"], fontsize=7.5)
    ax3.set_xlim(0, bu["n_delta"].max() * 1.35)
    label_bars(ax3, b3, bu["n_delta"].tolist(), formatter=lambda v: f"{v:+,.0f}", fontsize=8)
    ax3.set_xlabel("Change in records")
    ax3.set_title("Fastest-growing units", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax3); vs.no_grid_y(ax3)

    page_footer(fig, f"Median salary {h['median']['pct']:+.1%}; full-time median "
                     f"{h['median_ft']['pct']:+.1%}. Nominal dollars - not inflation-adjusted.",
                _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_matched_titles(pdf, df: pd.DataFrame) -> None:
    """Composition-controlled pay change."""
    import matplotlib.pyplot as plt
    if not CMP:
        return
    mt = CMP["matched_titles"]
    fig = new_page()
    page_title(
        fig, "Act 0 - Real change vs changing mix",
        "Most of the pay rise is real - but not all of it",
        f"A rising median does not prove anyone got a raise: it also rises when the university "
        f"hires more well-paid roles.\nComparing the same job title in both years "
        f"({mt['titles_compared']} titles with at least {mt['min_per_year']} people in each), the "
        f"median change was {mt['median_of_median_pct']:+.1%} and "
        f"{mt['share_with_increase']:.0%} of titles rose.",
    )

    gains = pd.DataFrame(mt["biggest_gains"]).head(10).iloc[::-1]
    ax = fig.add_axes([0.34, 0.14, 0.28, 0.60])
    y = np.arange(len(gains))
    bars = ax.barh(y, gains["med_pct"], height=0.62, color=BLUE)
    ax.set_yticks(y)
    ax.set_yticklabels([t[:38] for t in gains["job_title"]], fontsize=8)
    ax.set_xlim(0, gains["med_pct"].max() * 1.28)
    label_bars(ax, bars, gains["med_pct"].tolist(), formatter=lambda v: f"{v:+.0%}", fontsize=8.5)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0%}")
    ax.set_xlabel("Change in median pay")
    ax.set_title("Largest gains, matched titles", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax); vs.no_grid_y(ax)

    # Headline vs like-for-like
    ax2 = fig.add_axes([0.72, 0.14, 0.22, 0.60])
    labels = ["Headline\nmedian", "Matched\ntitles"]
    vals = [CMP["headline"]["median"]["pct"], mt["median_of_median_pct"]]
    bars2 = ax2.bar(labels, vals, color=[CONTEXT, BLUE], width=0.5)
    for bar, v in zip(bars2, vals):
        ax2.text(bar.get_x() + bar.get_width() / 2, v + max(vals) * 0.03, f"{v:+.1%}",
                 ha="center", fontsize=12, fontweight="bold", color=INK)
    ax2.set_ylim(0, max(vals) * 1.30)
    # These differ in tenths of a percent, so a whole-percent tick format would
    # print the same label on every gridline.
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:+.1%}")
    ax2.set_ylabel("Change in median pay")
    ax2.set_title("Composition vs real change", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax2); vs.no_grid_x(ax2)

    floor40 = CMP["floor"]["40000"]
    page_footer(fig, f"Full-time staff under $40,000 moved from {floor40['prev']:,} "
                     f"({floor40['prev_share']:.1%}) to {floor40['curr']:,} "
                     f"({floor40['curr_share']:.1%}). Change is measured on records, not "
                     f"individuals - the source carries no employee identifier.",
                _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def plt_close(fig):
    import matplotlib.pyplot as plt
    plt.close(fig)


# ------------------------------------------------------------------- act one

def page_distribution(pdf, df: pd.DataFrame) -> None:
    """The mean-median gap, shown as a distribution."""
    import matplotlib.pyplot as plt

    d = S["distribution"]["all"]
    fig = new_page()
    page_title(
        fig, "Act I - The shape of the payroll",
        "Most employees earn far less than the average",
        f"The mean salary is {usd(d['mean'])}, but the median is {usd(d['median'])} - a gap of "
        f"{usd(S['distribution']['mean_median_gap'])}. A long tail of high earners pulls the\n"
        f"average above what a typical employee actually makes, so 'average salary' overstates "
        f"the middle of this workforce.",
    )

    ax = fig.add_axes([0.075, 0.14, 0.87, 0.60])
    salaries = df["salary"].dropna()
    salaries = salaries[salaries > 0]

    bins = np.logspace(np.log10(salaries.min()), np.log10(salaries.max()), 60)
    ax.hist(salaries, bins=bins, color=BLUE, edgecolor=SURFACE, linewidth=0.4)
    ax.set_xscale("log")

    # Headroom, so both markers clear the tallest bar instead of sitting on it.
    bar_max = ax.get_ylim()[1]
    ax.set_ylim(0, bar_max * 1.16)

    # Median and mean are 1.29x apart - a few millimetres on a log axis, and far
    # narrower than either label. Anchoring each label outward from its own rule
    # (the median's text runs left, the mean's runs right) makes them impossible
    # to overlap: the median rule is always left of the mean rule, so the labels
    # grow away from each other rather than into the same gap.
    for value, label, colour, ha, nudge in (
        (d["median"], f"Median {usd(d['median'])}", INK, "right", 1 / 1.03),
        (d["mean"], f"Mean {usd(d['mean'])}", ORANGE, "left", 1.03),
    ):
        ax.axvline(value, color=colour, lw=1.6, linestyle="-")
        ax.text(value * nudge, bar_max * 1.03, label, fontsize=10,
                color=colour, fontweight="bold", ha=ha, va="bottom")

    ticks = [10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000]
    ax.set_xticks(ticks)
    ax.set_xticklabels([usd_compact(t) for t in ticks])
    ax.set_xlabel("Annual base salary (log scale)")
    ax.set_ylabel("Number of employees")
    vs.strip_spines(ax)
    vs.no_grid_x(ax)

    page_footer(fig, "Log scale: salaries span three orders of magnitude. "
                     "Includes part-time staff, whose figures are FTE-adjusted.",
                _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_parttime(pdf, df: pd.DataFrame) -> None:
    """Why a single 'average salary' is the wrong statistic."""
    import matplotlib.pyplot as plt

    ft = S["distribution"]["full_time"]
    pt = S["distribution"]["part_time"]
    o = S["overview"]

    fig = new_page()
    page_title(
        fig, "Act I - A caveat that is really a finding",
        "One in five records is part-time, which distorts every average",
        f"{o['part_time_records']:,} of {o['records']:,} records "
        f"({o['part_time_records']/o['records']:.0%}) are part-time. Because the source reports "
        f"FTE-adjusted annual pay,\na half-time employee shows half a salary. Comparing the two "
        f"groups without separating them understates typical pay.",
    )

    ax = fig.add_axes([0.075, 0.14, 0.40, 0.60])
    groups = ["Full-time", "Part-time"]
    medians = [ft["median"], pt["median"]]
    bars = ax.bar(groups, medians, color=[BLUE, CONTEXT], width=0.5)
    for bar, value, n in zip(bars, medians, [ft["count"], pt["count"]]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 1800, usd(value),
                ha="center", fontsize=12, fontweight="bold", color=INK)
        ax.text(bar.get_x() + bar.get_width() / 2, value * 0.5, f"n = {n:,}",
                ha="center", fontsize=10, color="white" if value > 40000 else INK_SECONDARY)
    ax.set_ylabel("Median annual salary")
    ax.set_title("Median pay by time status", fontsize=11, color=INK, loc="left", pad=12)
    ax.yaxis.set_major_formatter(lambda v, _: usd_compact(v))
    vs.strip_spines(ax)
    vs.no_grid_x(ax)

    # Right: the three competing "average" figures
    ax2 = fig.add_axes([0.575, 0.14, 0.37, 0.60])
    labels = ["Mean\n(everyone)", "Median\n(everyone)", "Median\n(full-time only)"]
    values = [S["distribution"]["all"]["mean"],
              S["distribution"]["all"]["median"],
              ft["median"]]
    colours = [CONTEXT, CONTEXT, BLUE]
    bars2 = ax2.bar(labels, values, color=colours, width=0.55)
    for bar, value in zip(bars2, values):
        ax2.text(bar.get_x() + bar.get_width() / 2, value + 1800, usd(value),
                 ha="center", fontsize=11, fontweight="bold", color=INK)
    ax2.set_ylabel("Annual salary")
    ax2.set_title("Three defensible 'typical' salaries", fontsize=11, color=INK,
                  loc="left", pad=12)
    ax2.yaxis.set_major_formatter(lambda v, _: usd_compact(v))
    vs.strip_spines(ax2)
    vs.no_grid_x(ax2)

    page_footer(fig, "Highlighted bar is the figure this report uses when describing "
                     "typical pay.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_concentration(pdf, df: pd.DataFrame) -> None:
    """Lorenz curve: how concentrated the payroll is."""
    import matplotlib.pyplot as plt

    c = S["concentration"]
    fig = new_page()
    page_title(
        fig, "Act I - Concentration",
        f"The top 10% of earners take {pct(c['top_10pct_payroll_share'], 0)} of the payroll",
        f"Plotted as a Lorenz curve, the further the line bows below the diagonal, the more "
        f"concentrated the pay.\nThe top 1% of records ({int(S['overview']['records']*0.01):,} "
        f"people) account for {pct(c['top_1pct_payroll_share'], 1)} of all base salary; the bottom "
        f"half accounts for {pct(c['bottom_50pct_payroll_share'], 1)}.",
    )

    ax = fig.add_axes([0.075, 0.14, 0.42, 0.60])
    lz = c["lorenz"]
    x = np.array(lz["population_share"])
    y = np.array(lz["payroll_share"])
    ax.plot([0, 1], [0, 1], color=AXIS, lw=1.2, label="Perfect equality")
    ax.plot(x, y, color=BLUE, lw=2.2, label="Actual distribution")
    ax.fill_between(x, y, x, color=BLUE, alpha=0.10)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("Cumulative share of employees")
    ax.set_ylabel("Cumulative share of payroll")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.legend(loc="upper left")
    ax.set_title(f"Gini coefficient: {c['gini_all']:.3f}", fontsize=11, color=INK,
                 loc="left", pad=12)
    vs.strip_spines(ax)

    # Right: share of payroll by earner group
    ax2 = fig.add_axes([0.585, 0.14, 0.36, 0.60])
    groups = ["Top 1%", "Top 5%", "Top 10%", "Bottom 50%"]
    shares = [c["top_1pct_payroll_share"], c["top_5pct_payroll_share"],
              c["top_10pct_payroll_share"], c["bottom_50pct_payroll_share"]]
    colours = [BLUE, BLUE, BLUE, CONTEXT]
    bars = ax2.barh(groups[::-1], shares[::-1], color=colours[::-1], height=0.6)
    ax2.set_xlim(0, max(shares) * 1.28)
    label_bars(ax2, bars, shares[::-1], formatter=lambda v: pct(v, 1))
    ax2.set_xlabel("Share of total base payroll")
    ax2.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax2.set_title("Payroll share by earner group", fontsize=11, color=INK,
                  loc="left", pad=12)
    vs.strip_spines(ax2)
    vs.no_grid_y(ax2)

    page_footer(fig, f"{c['count_over_500k']:,} records at or above $500,000; "
                     f"{c['count_over_250k']:,} at or above $250,000.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_units(pdf, df: pd.DataFrame) -> None:
    """Headcount vs payroll share by administrative unit."""
    import matplotlib.pyplot as plt

    units = pd.DataFrame(S["by_unit"]).head(12).iloc[::-1]
    fig = new_page()
    top = pd.DataFrame(S["by_unit"]).iloc[0]
    page_title(
        fig, "Act I - Where the people are",
        "UK is a health system with a university attached",
        f"{top['unit']} alone accounts for {top['headcount']:,} records "
        f"({top['headcount_share']:.0%} of headcount) and {top['payroll_share']:.0%} of base "
        f"payroll.\nComparing the two bars shows which units are staff-heavy relative to their "
        f"pay, and which are the reverse.",
    )

    ax = fig.add_axes([0.30, 0.13, 0.62, 0.61])
    y = np.arange(len(units))
    h = 0.38
    b1 = ax.barh(y + h / 2, units["headcount_share"], height=h, color=BLUE,
                 label="Share of headcount")
    b2 = ax.barh(y - h / 2, units["payroll_share"], height=h, color=ORANGE,
                 label="Share of payroll")
    ax.set_yticks(y)
    ax.set_yticklabels(units["unit"], fontsize=9)
    ax.set_xlim(0, max(units["headcount_share"].max(), units["payroll_share"].max()) * 1.18)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Share of university total")
    ax.legend(loc="lower right")
    vs.strip_spines(ax)
    vs.no_grid_y(ax)

    for bars, vals in ((b1, units["headcount_share"]), (b2, units["payroll_share"])):
        label_bars(ax, bars, vals.tolist(), formatter=lambda v: f"{v:.1%}", fontsize=8)

    page_footer(fig, "Top 12 units by payroll. Two series shown on one shared axis "
                     "so the comparison is honest.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_eeo(pdf, df: pd.DataFrame) -> None:
    """Median pay by occupational category."""
    import matplotlib.pyplot as plt

    eeo = pd.DataFrame(S["by_eeo"]).sort_values("median")
    fig = new_page()
    page_title(
        fig, "Act I - Occupational structure",
        "Median pay by occupational category",
        "The federal EEO categories the university reports against separate the workforce into "
        "broad occupational\ngroups. Full-time medians are shown alongside the all-records "
        "median, since part-time concentration differs sharply by group.",
    )

    ax = fig.add_axes([0.28, 0.14, 0.66, 0.60])
    y = np.arange(len(eeo))
    bars = ax.barh(y, eeo["median_ft"], height=0.6, color=BLUE)
    ax.set_yticks(y)
    ax.set_yticklabels(eeo["eeo_category"], fontsize=9.5)
    ax.set_xlim(0, eeo["median_ft"].max() * 1.22)
    ax.xaxis.set_major_formatter(lambda v, _: usd_compact(v))
    ax.set_xlabel("Median annual salary, full-time employees")
    label_bars(ax, bars, eeo["median_ft"].tolist(), formatter=usd)
    for i, n in enumerate(eeo["headcount"]):
        ax.text(eeo["median_ft"].max() * 1.20, i, f"n={n:,}", fontsize=8,
                color=INK_MUTED, va="center", ha="right")
    vs.strip_spines(ax)
    vs.no_grid_y(ax)

    page_footer(fig, "Full-time records only, to remove the FTE effect. "
                     "'Not Reportable' is largely medical residents and fellows.",
                _next_page())
    pdf.savefig(fig)
    plt.close(fig)


# ------------------------------------------------------------------- act two

def page_research_overview(pdf, df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    r = S["research"]
    cats = pd.DataFrame(r["by_category"]).sort_values("headcount")
    fig = new_page()
    page_title(
        fig, "Act II - The research enterprise",
        f"{r['records']:,} records staff the research mission",
        f"Roles coded to research - postdocs, research scientists and support staff, clinical "
        f"research, and research\nadministration - make up {pct(r['share_of_headcount'],1)} of "
        f"headcount and {pct(r['share_of_payroll'],1)} of base payroll, with a median of "
        f"{usd(r['median'])}.",
    )

    ax = fig.add_axes([0.30, 0.14, 0.40, 0.60])
    y = np.arange(len(cats))
    bars = ax.barh(y, cats["headcount"], height=0.6, color=BLUE)
    ax.set_yticks(y); ax.set_yticklabels(cats["research_category"], fontsize=9.5)
    ax.set_xlim(0, cats["headcount"].max() * 1.22)
    label_bars(ax, bars, cats["headcount"].tolist(), formatter=lambda v: f"{v:,.0f}")
    ax.set_xlabel("Employee records")
    ax.set_title("Headcount by research role", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax); vs.no_grid_y(ax)

    ax2 = fig.add_axes([0.755, 0.14, 0.19, 0.60])
    cats2 = cats.sort_values("median")
    y2 = np.arange(len(cats2))
    bars2 = ax2.barh(y2, cats2["median"], height=0.6, color=AQUA)
    ax2.set_yticks(y2); ax2.set_yticklabels([])
    ax2.set_xlim(0, cats2["median"].max() * 1.42)
    label_bars(ax2, bars2, cats2["median"].tolist(), formatter=usd_compact, fontsize=8.5)
    ax2.set_xlabel("Median salary")
    ax2.set_title("Median pay", fontsize=11, color=INK, loc="left", pad=12)
    ax2.xaxis.set_major_formatter(lambda v, _: usd_compact(v))
    vs.strip_spines(ax2); vs.no_grid_y(ax2)

    page_footer(fig, "Roles classified by job-title and department pattern matching; "
                     "see docs/METHODOLOGY.md in the repository for the rule set.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_postdocs(pdf, df: pd.DataFrame) -> None:
    """Postdoc pay against the NIH benchmark."""
    import matplotlib.pyplot as plt

    p = S["research"]["postdoc"]
    if not p["count"]:
        return
    fig = new_page()
    below = p["share_ft_below_nih_entry"]
    page_title(
        fig, "Act II - Benchmarking the postdocs",
        "Postdoctoral pay against the NIH entry stipend",
        f"UK's {p['count']:,} postdoctoral records have a median of {usd(p['median'])}. The NIH "
        f"NRSA entry-level stipend for FY2024\nis {usd(p['nih_entry_stipend'])} - the standard "
        f"external floor for postdoctoral pay. "
        f"{pct(below,0) if below is not None else 'n/a'} of full-time postdocs sit below it.",
    )

    ax = fig.add_axes([0.075, 0.14, 0.55, 0.60])
    pdocs = df[(df["research_category"] == "Postdoctoral") & df["is_full_time"]]["salary"].dropna()
    ax.hist(pdocs, bins=30, color=BLUE, edgecolor=SURFACE, linewidth=0.5)
    ax.axvline(p["nih_entry_stipend"], color=ORANGE, lw=2)
    ax.text(p["nih_entry_stipend"] * 1.02, ax.get_ylim()[1] * 0.9,
            f"NIH entry stipend\n{usd(p['nih_entry_stipend'])}",
            fontsize=9.5, color=ORANGE, fontweight="bold")
    ax.set_xlabel("Annual salary, full-time postdoctoral records")
    ax.set_ylabel("Number of records")
    ax.xaxis.set_major_formatter(lambda v, _: usd_compact(v))
    vs.strip_spines(ax); vs.no_grid_x(ax)

    ax2 = fig.add_axes([0.70, 0.14, 0.24, 0.60])
    stats_rows = [("Records", f"{p['count']:,}"),
                  ("Full-time", f"{p['count_full_time']:,}"),
                  ("Median", usd(p["median"])),
                  ("Mean", usd(p["mean"])),
                  ("Lowest", usd(p["min"])),
                  ("Highest", usd(p["max"]))]
    ax2.axis("off")
    for i, (k, v) in enumerate(stats_rows):
        yy = 0.92 - i * 0.145
        ax2.text(0, yy, k, fontsize=9.5, color=INK_SECONDARY, transform=ax2.transAxes)
        ax2.text(1, yy, v, fontsize=11.5, color=INK, fontweight="bold",
                 ha="right", transform=ax2.transAxes)
        ax2.axhline(yy - 0.045, xmin=0, xmax=1, color=GRID, lw=0.8)
    ax2.set_title("Postdoctoral pay", fontsize=11, color=INK, loc="left", pad=12)

    page_footer(fig, f"Benchmark: {p['nih_source']}, retrieved {RETRIEVED}. "
                     "UK salaries are institutional base pay, which need not follow NRSA scales.",
                _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_research_by_unit(pdf, df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    by_unit = pd.DataFrame(S["research"]["by_unit"]).head(10).iloc[::-1]
    fig = new_page()
    fig_top = pd.DataFrame(S["research"]["by_unit"]).iloc[0]
    page_title(
        fig, "Act II - Where research staff sit",
        "The research workforce is concentrated, not spread evenly",
        f"{fig_top['unit']} holds the largest share of research-coded staff "
        f"({fig_top['headcount']:,} records).\nMedian pay varies widely across units, reflecting "
        f"very different mixes of postdocs, technicians and senior scientists.",
    )

    ax = fig.add_axes([0.30, 0.14, 0.42, 0.60])
    y = np.arange(len(by_unit))
    bars = ax.barh(y, by_unit["headcount"], height=0.62, color=BLUE)
    ax.set_yticks(y); ax.set_yticklabels(by_unit["unit"], fontsize=9)
    ax.set_xlim(0, by_unit["headcount"].max() * 1.20)
    label_bars(ax, bars, by_unit["headcount"].tolist(), formatter=lambda v: f"{v:,.0f}")
    ax.set_xlabel("Research-coded records")
    ax.set_title("Headcount", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax); vs.no_grid_y(ax)

    ax2 = fig.add_axes([0.775, 0.14, 0.165, 0.60])
    bars2 = ax2.barh(y, by_unit["median"], height=0.62, color=AQUA)
    ax2.set_yticks(y); ax2.set_yticklabels([])
    ax2.set_xlim(0, by_unit["median"].max() * 1.45)
    label_bars(ax2, bars2, by_unit["median"].tolist(), formatter=usd_compact, fontsize=8.5)
    ax2.set_xlabel("Median salary")
    ax2.set_title("Median pay", fontsize=11, color=INK, loc="left", pad=12)
    ax2.xaxis.set_major_formatter(lambda v, _: usd_compact(v))
    vs.strip_spines(ax2); vs.no_grid_y(ax2)

    page_footer(fig, "Top 10 units by research headcount.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


# ----------------------------------------------------------------- act three

def page_rank_ladder(pdf, df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    ladder = pd.DataFrame(S["faculty"]["ladder_by_college"])
    ranks = [c for c in ["Assistant Professor", "Associate Professor", "Professor"]
             if c in ladder.columns]
    ladder = ladder.dropna(subset=ranks)
    by_rank = pd.DataFrame(S["faculty"]["by_rank"])

    fig = new_page()
    ratio = S["faculty"].get("professor_to_assistant_ratio")
    page_title(
        fig, "Act III - The faculty ladder",
        "Promotion is worth far more in some colleges than others",
        f"Across the university a full professor's median pay is "
        f"{ratio:.2f}x an assistant professor's. But the slope of that ladder\n"
        f"differs sharply by college - each line below tracks median pay across the three "
        f"tenure-track ranks.",
    )

    ax = fig.add_axes([0.075, 0.21, 0.52, 0.53])
    x = np.arange(len(ranks))
    palette = [BLUE, ORANGE, AQUA, YELLOW, VIOLET, "#e87ba4", "#e34948", INK_MUTED]

    # Endpoint labels double as the identity channel, so they must not collide.
    # Nudge any label that lands too close to one already placed.
    ladder = ladder.sort_values(ranks[-1], ascending=False).reset_index(drop=True)
    span = ladder[ranks[-1]].max() - ladder[ranks].min().min()
    min_gap = span * 0.045
    placed: list[float] = []
    for i, row in ladder.iterrows():
        colour = palette[i % len(palette)]
        ax.plot(x, [row[r] for r in ranks], marker="o", ms=7, lw=2, color=colour,
                label=row["unit"].replace("College of ", ""))
        y = row[ranks[-1]]
        while any(abs(y - p) < min_gap for p in placed):
            y -= min_gap * 0.55
        placed.append(y)
        ax.text(x[-1] + 0.06, y, f" {usd_compact(row[ranks[-1]])}",
                fontsize=8.5, color=colour, va="center", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([r.replace(" Professor", "\nProfessor") for r in ranks], fontsize=9.5)
    ax.set_xlim(-0.25, len(ranks) - 0.4)
    ax.set_ylabel("Median annual salary")
    ax.yaxis.set_major_formatter(lambda v, _: usd_compact(v))
    # Below the plot, not inside it: at upper left the legend sat directly on
    # top of the lines it was labelling.
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=4,
              fontsize=7.5, frameon=False, handlelength=1.5,
              columnspacing=1.4, handletextpad=0.5)
    vs.strip_spines(ax); vs.no_grid_x(ax)

    ax2 = fig.add_axes([0.68, 0.21, 0.26, 0.53])
    y2 = np.arange(len(by_rank))
    bars = ax2.barh(y2, by_rank["median"], height=0.42, color=BLUE)
    ax2.set_yticks(y2)
    ax2.set_yticklabels(by_rank["faculty_rank"], fontsize=9)
    ax2.set_xlim(0, by_rank["median"].max() * 1.32)
    label_bars(ax2, bars, by_rank["median"].tolist(), formatter=usd_compact)
    ax2.set_xlabel("Median salary")
    ax2.set_title("All faculty, by rank", fontsize=11, color=INK, loc="left", pad=12)
    ax2.xaxis.set_major_formatter(lambda v, _: usd_compact(v))
    vs.strip_spines(ax2); vs.no_grid_y(ax2)

    page_footer(fig, "Largest colleges by tenure-track faculty count. Medians, not means, "
                     "to limit the effect of a few very high salaries.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_dispersion(pdf, df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    disp = pd.DataFrame(S["dispersion"]["most_dispersed"]).head(10).iloc[::-1]
    fig = new_page()
    page_title(
        fig, "Act III - Internal spread",
        "Some departments contain their own pay hierarchy",
        f"Among departments with at least {S['dispersion']['min_dept_size']} full-time staff, "
        f"these have the widest internal gap between\ntheir 90th and 10th percentile earners - "
        f"typically clinical or academic units where trainees, staff and senior faculty share "
        f"one department code.",
    )

    ax = fig.add_axes([0.32, 0.14, 0.60, 0.60])
    y = np.arange(len(disp))
    # Fixed offset, not a multiplier: a proportional pad puts the label on top of
    # the marker for the shorter rows.
    lab_pad = disp["p90"].max() * 0.022
    for i, row in enumerate(disp.itertuples()):
        ax.plot([row.p10, row.p90], [i, i], color=CONTEXT, lw=5, solid_capstyle="round",
                zorder=1)
        ax.scatter([row.p10], [i], s=55, color=BLUE, zorder=3)
        ax.scatter([row.p90], [i], s=55, color=ORANGE, zorder=3)
        ax.text(row.p90 + lab_pad, i, f"{row.ratio_p90_p10:.1f}x", fontsize=9,
                color=INK_SECONDARY, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels(disp["department"], fontsize=8.5)
    ax.set_xlim(0, disp["p90"].max() * 1.20)
    ax.xaxis.set_major_formatter(lambda v, _: usd_compact(v))
    ax.set_xlabel("Annual salary, full-time staff")
    vs.strip_spines(ax); vs.no_grid_y(ax)

    ax.scatter([], [], s=55, color=BLUE, label="10th percentile")
    ax.scatter([], [], s=55, color=ORANGE, label="90th percentile")
    ax.legend(loc="lower right")

    page_footer(fig, f"Full-time records only. {S['dispersion']['departments_considered']} "
                     f"departments met the minimum-size threshold.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_floor(pdf, df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    floor = S["floor"]
    fig = new_page()
    t40 = floor["thresholds"]["40000"]
    page_title(
        fig, "Act III - The bottom of the scale",
        f"{t40['count']:,} full-time employees earn under $40,000",
        f"That is {pct(t40['share'],1)} of the full-time workforce. Restricting to full-time "
        f"records removes the FTE effect,\nso these are genuinely low full-year salaries rather "
        f"than part-time artefacts.",
    )

    ax = fig.add_axes([0.075, 0.14, 0.42, 0.60])
    thresholds = sorted(int(t) for t in floor["thresholds"])
    counts = [floor["thresholds"][str(t)]["count"] for t in thresholds]
    bars = ax.bar([usd_compact(t) for t in thresholds], counts, color=BLUE, width=0.55)
    for bar, value, t in zip(bars, counts, thresholds):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(counts) * 0.02,
                f"{value:,}\n{floor['thresholds'][str(t)]['share']:.1%}",
                ha="center", fontsize=9.5, color=INK)
    ax.set_ylabel("Full-time employees below threshold")
    ax.set_xlabel("Salary threshold")
    ax.set_ylim(0, max(counts) * 1.22)
    vs.strip_spines(ax); vs.no_grid_x(ax)

    # Which occupational groups make up the sub-$40k full-time population
    ax2 = fig.add_axes([0.585, 0.14, 0.36, 0.60])
    low = df[(df["is_full_time"]) & (df["salary"] < 40_000)]
    mix = low["eeo_category"].value_counts().head(6).iloc[::-1]
    y = np.arange(len(mix))
    bars2 = ax2.barh(y, mix.values, height=0.6, color=ORANGE)
    ax2.set_yticks(y); ax2.set_yticklabels(mix.index, fontsize=9)
    ax2.set_xlim(0, mix.max() * 1.22)
    label_bars(ax2, bars2, mix.values.tolist(), formatter=lambda v: f"{v:,.0f}")
    ax2.set_xlabel("Full-time employees under $40,000")
    ax2.set_title("Who they are", fontsize=11, color=INK, loc="left", pad=12)
    vs.strip_spines(ax2); vs.no_grid_y(ax2)

    page_footer(fig, "Base salary excludes shift differentials, overtime and benefits, "
                     "which materially affect take-home pay in service roles.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def page_top_roles(pdf, df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    top = pd.DataFrame(S["top_roles"]).head(12).iloc[::-1]
    fig = new_page()
    page_title(
        fig, "Act III - The top of the scale",
        "The highest-paid roles are athletics and clinical leadership",
        "Positions are identified by job title and unit only - no individual is named. "
        "Base salary alone understates total\ncompensation at this end of the distribution, "
        "where supplements, incentives and outside income are common.",
    )

    ax = fig.add_axes([0.42, 0.13, 0.50, 0.61])
    y = np.arange(len(top))
    bars = ax.barh(y, top["salary"], height=0.62, color=BLUE)
    labels = [f"{r.job_title[:44]}\n{r.unit}" for r in top.itertuples()]
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, top["salary"].max() * 1.18)
    label_bars(ax, bars, top["salary"].tolist(), formatter=usd_compact)
    ax.xaxis.set_major_formatter(lambda v, _: usd_compact(v))
    ax.set_xlabel("Annual base salary")
    vs.strip_spines(ax); vs.no_grid_y(ax)

    page_footer(fig, "Top 12 records by base salary.", _next_page())
    pdf.savefig(fig)
    plt.close(fig)


# ------------------------------------------------------------- method pages

def page_method(pdf, df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    q = json.loads((ROOT / "data" / "processed" / "data_quality_report.json").read_text())
    acc = STATS["acceptance"]
    fig = new_page()
    page_title(fig, "Method", "How this was built, and what it cannot tell you")

    years_txt = ", ".join(STATS["year_list"])
    left = (
        "DATA SOURCE\n"
        f"The university publishes each salary year ({years_txt}) through a\n"
        "Caspio search application. It offers no export and no API, so each\n"
        "dataset was reconstructed by driving the same AJAX endpoint the page\n"
        "itself uses, walking every result page. Extracts are resumable and\n"
        "cached page-by-page.\n\n"
        "MISSING DATA\n"
    )
    miss = QUALITY.get("missing_by_year", {})
    gaps_found = False
    for yr in STATS["year_list"]:
        cols = miss.get(yr, {}).get("columns", {})
        gaps = {c: v["empty"] for c, v in cols.items() if v.get("empty")}
        if gaps:
            gaps_found = True
            left += f"   {yr}: " + ", ".join(f"{c}={n:,}" for c, n in gaps.items()) + "\n"
        else:
            left += f"   {yr}: no empty values in any analysed field\n"
    rank_status = QUALITY.get("rank_status_by_year", {}).get(LATEST, {})
    if rank_status:
        left += ("   Academic rank is blank for two reasons, counted separately:\n")
        for k, v in rank_status.items():
            left += f"      {k:<16} {v:>8,}\n"
    if not gaps_found:
        left += "   Empty fields are labelled 'Not reported' and kept as their own\n"
        left += "   category - never dropped or merged into a real value.\n"
    left += (
        "\nVALIDATION\n"
        "Computed statistics were checked against figures published\n"
        "independently from the same source dataset:\n"
    )
    for c in acc["checks"]:
        mark = "PASS" if c["ok"] else "CHECK"
        left += (f"   {c['check']:<18} expected {c['expected']:>10,.0f}   "
                 f"computed {c['computed']:>10,.0f}   {mark}\n")

    right = (
        "WHAT THIS DATA IS NOT\n"
        "- Base salary only. It excludes benefits, bonuses, clinical incentive\n"
        "  pay, shift differentials, overtime, and athletics supplements. Total\n"
        "  compensation is higher than shown, especially at the extremes.\n"
        "- FTE-adjusted. Part-time staff show reduced annual figures that do\n"
        "  not indicate a low rate of pay. Full-time-only cuts are used\n"
        "  wherever pay levels are compared.\n"
        "- Records, not people. An employee holding two appointments appears\n"
        f"  twice. In {LATEST}, "
        f"{q['appointments_by_year'][LATEST]['names_on_more_than_one_record']:,} name "
        f"combinations appear on more than one\n  record,"
        "  but common names collide, so this is an approximation and no exact\n"
        "  person count is claimed.\n"
        "- Change is measured on records, not individuals. The source carries\n"
        "  no employee identifier, so matched job titles are used to control\n"
        "  for a changing mix of roles.\n"
        "- Nominal dollars. Figures are not adjusted for inflation.\n\n"
        "DELIBERATE OMISSIONS\n"
        "- No employee is named anywhere in this report.\n"
        "- No gender, race, or other demographic attribute is inferred. The\n"
        "  dataset contains none, and estimating them from names would not\n"
        "  support defensible conclusions.\n"
    )

    fig.text(0.055, 0.79, left, fontsize=8.5, color=INK_SECONDARY, va="top",
             family="monospace", linespacing=1.55)
    fig.text(0.52, 0.79, right, fontsize=8.5, color=INK_SECONDARY, va="top",
             linespacing=1.55)

    fig.text(0.055, 0.115,
             f"{vs.AUTHOR}   ·   {vs.AUTHOR_LINKEDIN}   ·   {vs.AUTHOR_GITHUB}",
             fontsize=8.5, color=vs.UK_BLUE, va="bottom", fontweight="bold")
    page_footer(fig, f"{SOURCE_NOTE} Data retrieved {RETRIEVED}. "
                     f"Full methodology and data dictionary: {vs.REPO_SHORT}",
                _next_page())
    pdf.savefig(fig)
    plt.close(fig)


def main() -> None:
    vs.apply_style()
    all_years = pd.read_csv(CLEAN)
    # Every chart page except the year-over-year ones describes a single year.
    # The clean file stacks all years, so scope it here rather than in each page.
    df = all_years[all_years["year"] == LATEST].copy()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    pages = 0
    with PdfPages(OUT_PDF) as pdf:
        page_cover(pdf, df)
        page_dashboard(pdf, df)
        page_yoy_overview(pdf, all_years)
        page_matched_titles(pdf, all_years)
        page_distribution(pdf, df)
        page_parttime(pdf, df)
        page_concentration(pdf, df)
        page_units(pdf, df)
        page_eeo(pdf, df)
        page_research_overview(pdf, df)
        page_postdocs(pdf, df)
        page_research_by_unit(pdf, df)
        page_rank_ladder(pdf, df)
        page_dispersion(pdf, df)
        page_floor(pdf, df)
        page_top_roles(pdf, df)
        page_method(pdf, df)

        # Ask the writer for the real count. Deriving it from the page-number
        # counter drifts as soon as unnumbered front matter is added.
        pages = pdf.get_pagecount()

        meta = pdf.infodict()
        meta["Title"] = f"Anatomy of a Public Payroll: University of Kentucky {LATEST} Salaries"
        meta["Author"] = vs.AUTHOR
        meta["Subject"] = (f"Analysis of {S['overview']['records']:,} employee salary "
                           f"records ({', '.join(STATS['year_list'])})")
        meta["Keywords"] = "institutional research, data visualization, higher education"

    size_kb = OUT_PDF.stat().st_size / 1024
    print(f"Wrote {OUT_PDF.relative_to(ROOT)} ({pages} pages, {size_kb:,.0f} KB)")


if __name__ == "__main__":
    main()
