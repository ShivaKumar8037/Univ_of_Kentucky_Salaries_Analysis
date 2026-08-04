"""
Compute every statistic the report and dashboard present, for every published year.

Reads  : data/processed/uk_salaries_clean.csv
Writes : data/processed/summary_stats.json
         data/processed/agg_*.csv

Design rule: no figure is ever hardcoded in a plotting script. Everything is
computed here and read back from summary_stats.json, so the narrative cannot
drift away from the data.

Output shape:
    {
      "years":      {"2024-25": {...}, "2025-26": {...}},   # full stats per year
      "latest":     "2025-26",
      "comparison": {...},                                   # year-over-year
      "quality":    {...},                                   # missing-data summary
      "acceptance": {...}                                    # integrity checks
    }
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CLEAN_CSV = ROOT / "data" / "processed" / "uk_salaries_clean.csv"
QUALITY_JSON = ROOT / "data" / "processed" / "data_quality_report.json"
PROCESSED = ROOT / "data" / "processed"
STATS_JSON = PROCESSED / "summary_stats.json"

NOT_APPLICABLE = "Not applicable"
NOT_REPORTED = "Not reported"

# FY2024 NIH NRSA entry-level postdoctoral stipend (0 years experience).
# Source: NIH Guide NOT-OD-24-104. Retrieved 2026-08-04.
NIH_POSTDOC_ENTRY_STIPEND = 61_008
NIH_STIPEND_SOURCE = "NIH NOT-OD-24-104 (FY2024 NRSA stipend levels)"

MIN_DEPT_SIZE = 30       # below this, one outlier dominates a dispersion ratio
MIN_TITLE_SIZE = 20      # minimum per-year count for a matched-title comparison

LADDER = ["Instructor", "Assistant Professor", "Associate Professor", "Professor"]

# Independently published figures for the 2024-25 dataset. The $500k+ count was
# reported as "nearly 130", so it carries a wider tolerance than the exact stats.
ACCEPTANCE = {
    "record_count": (26_430, 0.001),
    "mean_salary": (77_981, 0.001),
    "median_salary": (60_779, 0.001),
    "count_over_500k": (130, 0.05),
}
ACCEPTANCE_YEAR = "2024-25"


def gini(values: np.ndarray) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    v = v[v >= 0]
    n = v.size
    if n == 0 or v.sum() == 0:
        return float("nan")
    idx = np.arange(1, n + 1)
    return float((2 * (idx * v).sum()) / (n * v.sum()) - (n + 1) / n)


def lorenz_points(values: np.ndarray, n_points: int = 101) -> dict[str, list[float]]:
    v = np.sort(np.asarray(values, dtype=float))
    cum = np.cumsum(v) / np.cumsum(v)[-1]
    pop = np.arange(1, v.size + 1) / v.size
    grid = np.linspace(0, 1, n_points)
    return {"population_share": grid.tolist(),
            "payroll_share": np.interp(grid, pop, cum, left=0.0).tolist()}


def describe(series: pd.Series) -> dict:
    s = series.dropna()
    if s.empty:
        return {"count": 0}
    return {
        "count": int(s.size), "total": float(s.sum()), "mean": float(s.mean()),
        "median": float(s.median()), "std": float(s.std()), "min": float(s.min()),
        "max": float(s.max()), "p10": float(s.quantile(.10)), "p25": float(s.quantile(.25)),
        "p75": float(s.quantile(.75)), "p90": float(s.quantile(.90)),
        "p95": float(s.quantile(.95)), "p99": float(s.quantile(.99)),
    }


def top_share(values: np.ndarray, pctile: float) -> float:
    v = np.sort(np.asarray(values, dtype=float))[::-1]
    k = max(1, int(round(v.size * pctile / 100)))
    return float(v[:k].sum() / v.sum())


def compute_year(df: pd.DataFrame) -> dict:
    """Full statistics block for a single salary year."""
    salary = df["salary"]
    ft = df[df["is_full_time"]]
    out: dict = {}

    out["overview"] = {
        "records": int(len(df)),
        "units": int(df["unit"].nunique()),
        "departments": int(df["department"].nunique()),
        "job_titles": int(df["job_title"].nunique()),
        "total_payroll": float(salary.sum()),
        "full_time_records": int(df["is_full_time"].sum()),
        "part_time_records": int((~df["is_full_time"]).sum()),
        "part_time_share": float((~df["is_full_time"]).mean()),
    }

    out["distribution"] = {
        "all": describe(salary),
        "full_time": describe(ft["salary"]),
        "part_time": describe(df[~df["is_full_time"]]["salary"]),
    }
    out["distribution"]["mean_median_gap"] = (
        out["distribution"]["all"]["mean"] - out["distribution"]["all"]["median"]
    )

    out["concentration"] = {
        "gini_all": gini(salary.values),
        "gini_full_time": gini(ft["salary"].values),
        "top_1pct_payroll_share": top_share(salary.values, 1),
        "top_5pct_payroll_share": top_share(salary.values, 5),
        "top_10pct_payroll_share": top_share(salary.values, 10),
        "bottom_50pct_payroll_share": 1 - top_share(salary.values, 50),
        "lorenz": lorenz_points(salary.values),
        "count_over_250k": int((salary >= 250_000).sum()),
        "count_over_500k": int((salary >= 500_000).sum()),
        "count_over_1m": int((salary >= 1_000_000).sum()),
    }

    # Full-time / part-time split by salary band -- the dashboard legend series.
    band_ft = (
        df.pivot_table(index="salary_band", columns="is_full_time", values="salary",
                       aggfunc="size", observed=False)
        .rename(columns={True: "full_time", False: "part_time"})
        .fillna(0).astype(int)
    )
    for col in ("full_time", "part_time"):
        if col not in band_ft:
            band_ft[col] = 0
    out["bands_by_time_status"] = band_ft.reset_index().astype({"salary_band": str}).to_dict("records")

    unit_agg = (
        df.groupby("unit")
        .agg(headcount=("salary", "size"), payroll=("salary", "sum"),
             median=("salary", "median"), mean=("salary", "mean"),
             full_time=("is_full_time", "sum"))
        .sort_values("payroll", ascending=False)
    )
    unit_agg["part_time"] = unit_agg["headcount"] - unit_agg["full_time"]
    unit_agg["headcount_share"] = unit_agg["headcount"] / unit_agg["headcount"].sum()
    unit_agg["payroll_share"] = unit_agg["payroll"] / unit_agg["payroll"].sum()
    unit_agg["part_time_share"] = unit_agg["part_time"] / unit_agg["headcount"]
    out["by_unit"] = unit_agg.reset_index().to_dict("records")

    eeo_agg = (
        df.groupby("eeo_category")
        .agg(headcount=("salary", "size"), payroll=("salary", "sum"),
             median=("salary", "median"), full_time=("is_full_time", "sum"))
        .sort_values("median", ascending=False)
    )
    eeo_agg["part_time"] = eeo_agg["headcount"] - eeo_agg["full_time"]
    eeo_agg["median_ft"] = (
        ft.groupby("eeo_category")["salary"].median().reindex(eeo_agg.index)
    )
    out["by_eeo"] = eeo_agg.reset_index().to_dict("records")

    # --- research enterprise -------------------------------------------------
    research = df[df["is_research"]]
    res_agg = (
        research.groupby("research_category")
        .agg(headcount=("salary", "size"), payroll=("salary", "sum"),
             median=("salary", "median"), mean=("salary", "mean"),
             p25=("salary", lambda s: s.quantile(.25)),
             p75=("salary", lambda s: s.quantile(.75)))
        .sort_values("headcount", ascending=False)
    )
    postdocs = research[research["research_category"] == "Postdoctoral"]
    postdoc_ft = postdocs[postdocs["is_full_time"]]
    research_by_unit = (
        research.groupby("unit")
        .agg(headcount=("salary", "size"), median=("salary", "median"))
        .sort_values("headcount", ascending=False)
    )
    out["research"] = {
        "records": int(len(research)),
        "share_of_headcount": float(len(research) / len(df)),
        "payroll": float(research["salary"].sum()),
        "share_of_payroll": float(research["salary"].sum() / salary.sum()),
        "median": float(research["salary"].median()),
        "by_category": res_agg.reset_index().to_dict("records"),
        "by_unit": research_by_unit.reset_index().head(15).to_dict("records"),
        "postdoc": {
            "count": int(len(postdocs)),
            "count_full_time": int(len(postdoc_ft)),
            "median": float(postdocs["salary"].median()) if len(postdocs) else None,
            "mean": float(postdocs["salary"].mean()) if len(postdocs) else None,
            "min": float(postdocs["salary"].min()) if len(postdocs) else None,
            "max": float(postdocs["salary"].max()) if len(postdocs) else None,
            "nih_entry_stipend": NIH_POSTDOC_ENTRY_STIPEND,
            "nih_source": NIH_STIPEND_SOURCE,
            "share_ft_below_nih_entry": (
                float((postdoc_ft["salary"] < NIH_POSTDOC_ENTRY_STIPEND).mean())
                if len(postdoc_ft) else None),
            "count_ft_below_nih_entry": int(
                (postdoc_ft["salary"] < NIH_POSTDOC_ENTRY_STIPEND).sum()),
        },
    }

    # --- faculty ladder (full-time only) ------------------------------------
    faculty = df[df["is_faculty"] & df["faculty_rank"].isin(LADDER) & df["is_full_time"]]
    rank_agg = (
        faculty.groupby("faculty_rank")
        .agg(headcount=("salary", "size"), median=("salary", "median"),
             mean=("salary", "mean"))
        .reindex([r for r in LADDER if r in set(faculty["faculty_rank"])])
        .dropna(how="all")
    )
    tenure = [r for r in LADDER if r != "Instructor"]
    big = (faculty[faculty["faculty_rank"].isin(tenure)]
           .groupby("unit").size().sort_values(ascending=False).head(8).index.tolist())
    ladder_by_college = (
        faculty[faculty["unit"].isin(big) & faculty["faculty_rank"].isin(tenure)]
        .pivot_table(index="unit", columns="faculty_rank", values="salary", aggfunc="median")
        .reindex(columns=tenure)
    )
    out["faculty"] = {
        "records": int(len(faculty)),
        "by_rank": rank_agg.reset_index().to_dict("records"),
        "ladder_by_college": ladder_by_college.reset_index().to_dict("records"),
    }
    if {"Assistant Professor", "Professor"}.issubset(set(rank_agg.index)):
        out["faculty"]["professor_to_assistant_ratio"] = float(
            rank_agg.loc["Professor", "median"] / rank_agg.loc["Assistant Professor", "median"])

    # --- dispersion ----------------------------------------------------------
    dept = (
        ft.groupby("department")["salary"]
        .agg(headcount="size", median="median",
             p10=lambda s: s.quantile(.10), p90=lambda s: s.quantile(.90))
    )
    dept = dept[dept["headcount"] >= MIN_DEPT_SIZE].copy()
    dept["ratio_p90_p10"] = dept["p90"] / dept["p10"]
    dept = dept.sort_values("ratio_p90_p10", ascending=False)
    out["dispersion"] = {
        "min_dept_size": MIN_DEPT_SIZE,
        "departments_considered": int(len(dept)),
        "most_dispersed": dept.head(12).reset_index().to_dict("records"),
    }

    residents = df[df["is_resident"]]
    out["residents"] = {"count": int(len(residents))}
    if len(residents):
        out["residents"].update({
            "median": float(residents["salary"].median()),
            "p10": float(residents["salary"].quantile(.10)),
            "p90": float(residents["salary"].quantile(.90)),
            "iqr": float(residents["salary"].quantile(.75) - residents["salary"].quantile(.25)),
            "full_time_iqr": float(ft["salary"].quantile(.75) - ft["salary"].quantile(.25)),
        })

    out["floor"] = {
        "thresholds": {str(t): {"count": int((ft["salary"] < t).sum()),
                                "share": float((ft["salary"] < t).mean())}
                       for t in (35_000, 40_000, 45_000, 50_000)},
        "full_time_p10": float(ft["salary"].quantile(.10)),
    }

    out["top_roles"] = (
        df.nlargest(15, "salary")[["job_title", "unit", "department", "salary"]]
        .reset_index(drop=True).to_dict("records")
    )
    return out


def compare_years(df: pd.DataFrame, prev: str, curr: str) -> dict:
    """Year-over-year change, with a composition-controlled view."""
    a, b = df[df["year"] == prev], df[df["year"] == curr]
    cmp: dict = {"prev": prev, "curr": curr}

    cmp["headline"] = {
        "records": {"prev": int(len(a)), "curr": int(len(b)),
                    "delta": int(len(b) - len(a)),
                    "pct": float(len(b) / len(a) - 1)},
        "payroll": {"prev": float(a["salary"].sum()), "curr": float(b["salary"].sum()),
                    "delta": float(b["salary"].sum() - a["salary"].sum()),
                    "pct": float(b["salary"].sum() / a["salary"].sum() - 1)},
        "median": {"prev": float(a["salary"].median()), "curr": float(b["salary"].median()),
                   "pct": float(b["salary"].median() / a["salary"].median() - 1)},
        "mean": {"prev": float(a["salary"].mean()), "curr": float(b["salary"].mean()),
                 "pct": float(b["salary"].mean() / a["salary"].mean() - 1)},
        "median_ft": {
            "prev": float(a[a["is_full_time"]]["salary"].median()),
            "curr": float(b[b["is_full_time"]]["salary"].median()),
            "pct": float(b[b["is_full_time"]]["salary"].median()
                         / a[a["is_full_time"]]["salary"].median() - 1)},
    }

    def side_by_side(col: str, min_n: int = 1) -> pd.DataFrame:
        ga = a.groupby(col)["salary"].agg(n_prev="size", med_prev="median", pay_prev="sum")
        gb = b.groupby(col)["salary"].agg(n_curr="size", med_curr="median", pay_curr="sum")
        m = ga.join(gb, how="inner")
        m = m[(m["n_prev"] >= min_n) & (m["n_curr"] >= min_n)]
        m["n_delta"] = m["n_curr"] - m["n_prev"]
        m["med_pct"] = m["med_curr"] / m["med_prev"] - 1
        m["pay_pct"] = m["pay_curr"] / m["pay_prev"] - 1
        return m

    unit_cmp = side_by_side("unit", 10).sort_values("n_delta", ascending=False)
    unit_cmp.to_csv(PROCESSED / "agg_yoy_by_unit.csv")
    cmp["by_unit"] = unit_cmp.reset_index().to_dict("records")

    eeo_cmp = side_by_side("eeo_category", 1).sort_values("med_pct", ascending=False)
    cmp["by_eeo"] = eeo_cmp.reset_index().to_dict("records")

    # Matched job titles: the same title in both years. This controls for
    # workforce composition far better than the headline median, which moves
    # when the mix of roles changes rather than when anyone gets a raise.
    title_cmp = side_by_side("job_title", MIN_TITLE_SIZE).sort_values("med_pct", ascending=False)
    title_cmp.to_csv(PROCESSED / "agg_yoy_by_title.csv")
    cmp["matched_titles"] = {
        "min_per_year": MIN_TITLE_SIZE,
        "titles_compared": int(len(title_cmp)),
        "records_covered_curr": int(title_cmp["n_curr"].sum()),
        "median_of_median_pct": float(title_cmp["med_pct"].median()),
        "share_with_increase": float((title_cmp["med_pct"] > 0).mean()),
        "share_flat_or_down": float((title_cmp["med_pct"] <= 0).mean()),
        "biggest_gains": title_cmp.head(10).reset_index().to_dict("records"),
        "biggest_losses": title_cmp.tail(10).reset_index().to_dict("records"),
    }

    # Research workforce trajectory
    ra, rb = a[a["is_research"]], b[b["is_research"]]
    cmp["research"] = {
        "records": {"prev": int(len(ra)), "curr": int(len(rb)),
                    "delta": int(len(rb) - len(ra)),
                    "pct": float(len(rb) / len(ra) - 1) if len(ra) else None},
        "median": {"prev": float(ra["salary"].median()), "curr": float(rb["salary"].median()),
                   "pct": float(rb["salary"].median() / ra["salary"].median() - 1)},
        "share_of_headcount": {"prev": float(len(ra) / len(a)), "curr": float(len(rb) / len(b))},
        "by_category": side_by_side_research(ra, rb),
    }

    pa = ra[ra["research_category"] == "Postdoctoral"]
    pb = rb[rb["research_category"] == "Postdoctoral"]
    cmp["postdoc"] = {
        "count": {"prev": int(len(pa)), "curr": int(len(pb))},
        "median": {"prev": float(pa["salary"].median()) if len(pa) else None,
                   "curr": float(pb["salary"].median()) if len(pb) else None},
        "below_nih": {
            "prev": float((pa[pa["is_full_time"]]["salary"] < NIH_POSTDOC_ENTRY_STIPEND).mean())
            if len(pa[pa["is_full_time"]]) else None,
            "curr": float((pb[pb["is_full_time"]]["salary"] < NIH_POSTDOC_ENTRY_STIPEND).mean())
            if len(pb[pb["is_full_time"]]) else None},
    }

    # Low-pay floor movement
    fa, fb = a[a["is_full_time"]], b[b["is_full_time"]]
    cmp["floor"] = {
        str(t): {"prev": int((fa["salary"] < t).sum()), "curr": int((fb["salary"] < t).sum()),
                 "prev_share": float((fa["salary"] < t).mean()),
                 "curr_share": float((fb["salary"] < t).mean())}
        for t in (40_000, 50_000)
    }
    return cmp


def side_by_side_research(ra: pd.DataFrame, rb: pd.DataFrame) -> list[dict]:
    ga = ra.groupby("research_category")["salary"].agg(n_prev="size", med_prev="median")
    gb = rb.groupby("research_category")["salary"].agg(n_curr="size", med_curr="median")
    m = ga.join(gb, how="outer").fillna(0)
    m["n_delta"] = m["n_curr"] - m["n_prev"]
    m["med_pct"] = np.where(m["med_prev"] > 0, m["med_curr"] / m["med_prev"] - 1, np.nan)
    return m.reset_index().to_dict("records")


def main() -> None:
    if not CLEAN_CSV.exists():
        raise SystemExit(f"Missing {CLEAN_CSV}. Run src/clean.py first.")
    df = pd.read_csv(CLEAN_CSV)
    years = sorted(df["year"].unique())
    print(f"Years present: {', '.join(years)}")

    stats: dict = {"years": {}, "latest": years[-1], "year_list": years}
    for y in years:
        stats["years"][y] = compute_year(df[df["year"] == y].copy())
        o = stats["years"][y]["overview"]
        print(f"  {y}: {o['records']:,} records, "
              f"${o['total_payroll']/1e9:.2f}B payroll, "
              f"median ${stats['years'][y]['distribution']['all']['median']:,.0f}")

    if len(years) >= 2:
        stats["comparison"] = compare_years(df, years[-2], years[-1])
        h = stats["comparison"]["headline"]
        print(f"\nYear over year ({years[-2]} -> {years[-1]}):")
        print(f"  headcount {h['records']['delta']:+,} ({h['records']['pct']:+.1%})")
        print(f"  payroll   {h['payroll']['delta']/1e6:+,.0f}M ({h['payroll']['pct']:+.1%})")
        print(f"  median    {h['median']['pct']:+.1%}   full-time median {h['median_ft']['pct']:+.1%}")
        mt = stats["comparison"]["matched_titles"]
        print(f"  matched titles: {mt['titles_compared']} compared, "
              f"median change {mt['median_of_median_pct']:+.1%}, "
              f"{mt['share_with_increase']:.0%} rose")

    # Missing-data summary, surfaced into the outputs rather than left in a file.
    if QUALITY_JSON.exists():
        q = json.loads(QUALITY_JSON.read_text())
        stats["quality"] = {
            "missing_by_year": q.get("missing_by_year", {}),
            "rank_status_by_year": q.get("rank_status_by_year", {}),
            "incomplete_records_by_year": q.get("incomplete_records_by_year", {}),
            "appointments_by_year": q.get("appointments_by_year", {}),
            "note": q.get("missing_note", ""),
        }

    # --- acceptance ----------------------------------------------------------
    checks = []
    if ACCEPTANCE_YEAR in stats["years"]:
        s = stats["years"][ACCEPTANCE_YEAR]
        computed = {
            "record_count": s["overview"]["records"],
            "mean_salary": s["distribution"]["all"]["mean"],
            "median_salary": s["distribution"]["all"]["median"],
            "count_over_500k": s["concentration"]["count_over_500k"],
        }
        print(f"\nAcceptance checks ({ACCEPTANCE_YEAR}, vs independently published):")
        print(f"  {'check':<20} {'expected':>12} {'computed':>12}  {'delta':>8}")
        ok_all = True
        for key, (expected, tol) in ACCEPTANCE.items():
            got = computed[key]
            delta = (got - expected) / expected if expected else 0.0
            ok = abs(delta) <= tol
            ok_all &= ok
            checks.append({"check": key, "expected": expected, "computed": got, "ok": ok})
            print(f"  {key:<20} {expected:>12,.0f} {got:>12,.0f}  {delta:>+7.2%}  "
                  f"{'OK' if ok else 'FAIL'}")
        stats["acceptance"] = {"year": ACCEPTANCE_YEAR, "checks": checks,
                               "all_passed": bool(ok_all)}
        if not ok_all:
            print("\n  WARNING: extract deviates from published figures.")

    STATS_JSON.write_text(json.dumps(stats, indent=2, default=str))
    print(f"\nWrote {STATS_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
