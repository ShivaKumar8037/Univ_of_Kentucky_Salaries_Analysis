"""
Clean and enrich the raw UK salary extracts (all published years).

Reads  : data/raw/uk_salaries_<year>.csv
Writes : data/processed/uk_salaries_clean.csv   (all years, stacked)
         data/processed/data_quality_report.json

Three things this module is deliberate about:

*   Names are dropped.* The source is public record and does carry employee
    names, but no downstream chart or table identifies an individual. Names are
    used here only to estimate how many records represent second appointments
    rather than distinct people, then discarded.

*   Missing data is labelled, never silently blanked.* The source leaves fields
    empty for two very different reasons, and the distinction matters:
        "Not applicable"  - the field cannot apply (academic rank for a
                            custodian; the source is correct to leave it blank)
        "Not reported"    - the field should have a value but the source is
                            empty (a genuine gap in the published data)
    Both are counted per column per year and carried into the outputs, so a
    reader can see the difference rather than guessing.

*   No demographic inference.* The dataset contains no gender, race or age
    fields, and guessing them from names would be unsound. Not attempted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CLEAN_CSV = ROOT / "data" / "processed" / "uk_salaries_clean.csv"
QUALITY_JSON = ROOT / "data" / "processed" / "data_quality_report.json"

YEARS = ["2024-25", "2025-26"]

NOT_APPLICABLE = "Not applicable"
NOT_REPORTED = "Not reported"

BAND_EDGES = [0, 25_000, 40_000, 60_000, 80_000, 100_000, 150_000, 250_000, 500_000, np.inf]
BAND_LABELS = [
    "Under $25k", "$25-40k", "$40-60k", "$60-80k", "$80-100k",
    "$100-150k", "$150-250k", "$250-500k", "$500k+",
]

# Medical residents and fellows are coded "I/R/F <specialty> PGY<n>" (Intern /
# Resident / Fellow, Post-Graduate Year) -- trainees on a flat scale.
RESIDENT_PATTERN = re.compile(r"\bI/R/F\b|\bPGY\s*-?\s*\d", re.IGNORECASE)

# Research roles, most-specific first; first match wins.
RESEARCH_ROLE_PATTERNS: list[tuple[str, str]] = [
    ("Postdoctoral", r"post[\s-]?doc"),
    ("Research Faculty/Scientist", r"research scientist|scientist\b|research professor"),
    ("Research Support Staff", r"research (associate|assistant|technician|technologist|specialist)"),
    ("Research Support Staff", r"(laboratory|lab) (technician|technologist|manager|supervisor|assistant)"),
    ("Clinical Research", r"clinical research|research nurse|study coordinator|research coordinator"),
    ("Research Administration", r"research admin|sponsored (projects|programs)|grants? (admin|manager|specialist|officer)|research compliance|proposal (development|specialist)|research (analyst|facilitator|integrity)"),
    ("Research Support Staff", r"\bresearch\b"),
]

# Ranks that form the tenure-track ladder, in order.
LADDER = ["Instructor", "Assistant Professor", "Associate Professor", "Professor"]

TEXT_COLS = [
    "LastName", "FirstName", "AdministrativeUnitOrCollege", "Department",
    "JobTitle", "Position", "EEO", "Rank", "FullOrPartTime",
]


def parse_salary(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(r"[$,]", "", regex=True).str.strip(),
        errors="coerce",
    )


def squash(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()


def classify_research_role(title: str, unit: str, department: str) -> str | None:
    haystack = f"{title} {department}".lower()
    for label, pattern in RESEARCH_ROLE_PATTERNS:
        if re.search(pattern, haystack):
            return label
    if "research administration" in unit.lower():
        return "Research Administration"
    return None


def load_year(year: str) -> pd.DataFrame | None:
    path = RAW_DIR / f"uk_salaries_{year.replace('-', '_')}.csv"
    if not path.exists():
        print(f"  {year}: no extract at {path.name} - skipping")
        return None
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df["year"] = year
    print(f"  {year}: {len(df):,} raw records")
    return df


def main() -> None:
    print("Loading raw extracts:")
    frames = [f for f in (load_year(y) for y in YEARS) if f is not None]
    if not frames:
        raise SystemExit("No raw extracts found. Run src/scrape_caspio.py first.")

    df = pd.concat(frames, ignore_index=True)
    for col in TEXT_COLS:
        df[col] = squash(df[col])

    df["salary"] = parse_salary(df["SalaryTrueAnnual"])

    # --- missingness, measured before anything is filled --------------------
    missing: dict[str, dict] = {}
    for year, grp in df.groupby("year"):
        per_col = {}
        for col in TEXT_COLS + ["salary"]:
            if col in ("LastName", "FirstName"):
                continue
            if col == "salary":
                n = int(grp["salary"].isna().sum())
            else:
                n = int((grp[col] == "").sum())
            per_col[col] = {"empty": n, "share": round(n / len(grp), 6)}
        missing[year] = {"records": int(len(grp)), "columns": per_col}

    # --- multiple appointments (approximate; names collide) ------------------
    appointments = {}
    for year, grp in df.groupby("year"):
        key = (grp["LastName"] + "|" + grp["FirstName"]).str.lower()
        counts = key.value_counts()
        appointments[year] = {
            "records": int(len(grp)),
            "distinct_name_combinations": int(counts.size),
            "names_on_more_than_one_record": int((counts > 1).sum()),
        }
    key_all = (df["LastName"] + "|" + df["FirstName"]).str.lower()
    df["appointment_count_for_name"] = (
        df.groupby("year")["LastName"].transform("size").astype(int) * 0
        + key_all.groupby(df["year"]).transform(lambda s: s.map(s.value_counts()))
    ).astype(int)

    # --- derived flags -------------------------------------------------------
    df["is_full_time"] = df["FullOrPartTime"].str.lower().eq("full time")
    df["is_faculty"] = df["EEO"].str.lower().eq("faculty")
    df["is_resident"] = (
        df["JobTitle"].str.contains(RESIDENT_PATTERN)
        | df["Position"].str.contains(RESIDENT_PATTERN)
    )
    df["research_category"] = [
        classify_research_role(t, u, d)
        for t, u, d in zip(df["JobTitle"], df["AdministrativeUnitOrCollege"], df["Department"])
    ]
    df.loc[df["is_resident"], "research_category"] = None
    df["is_research"] = df["research_category"].notna()
    df["salary_band"] = pd.cut(df["salary"], bins=BAND_EDGES, labels=BAND_LABELS, right=False)

    # --- explicit missing-data labelling ------------------------------------
    # Academic rank is blank for two different reasons. Non-faculty have no rank
    # (structurally not applicable); a faculty member with no rank is a real gap.
    rank_blank = df["Rank"] == ""
    df["faculty_rank"] = df["Rank"].where(
        ~rank_blank,
        np.where(df["is_faculty"], NOT_REPORTED, NOT_APPLICABLE),
    )
    df["rank_status"] = np.select(
        [~rank_blank, rank_blank & df["is_faculty"]],
        ["Reported", NOT_REPORTED],
        default=NOT_APPLICABLE,
    )

    # Every other categorical: an empty string is a genuine gap.
    for src, dest in [
        ("AdministrativeUnitOrCollege", "unit"),
        ("Department", "department"),
        ("JobTitle", "job_title"),
        ("Position", "position"),
        ("EEO", "eeo_category"),
        ("FullOrPartTime", "time_status"),
    ]:
        df[dest] = df[src].replace("", NOT_REPORTED)

    df["has_complete_record"] = (
        (df["unit"] != NOT_REPORTED)
        & (df["department"] != NOT_REPORTED)
        & (df["job_title"] != NOT_REPORTED)
        & (df["eeo_category"] != NOT_REPORTED)
        & (df["time_status"] != NOT_REPORTED)
        & df["salary"].notna()
    )

    # --- drop names ----------------------------------------------------------
    df = df.drop(columns=["LastName", "FirstName", "SalaryTrueAnnual", "Rank",
                          "AdministrativeUnitOrCollege", "Department", "JobTitle",
                          "Position", "EEO", "FullOrPartTime"])

    ordered = [
        "year", "unit", "department", "job_title", "position", "eeo_category",
        "faculty_rank", "rank_status", "time_status", "salary", "salary_band",
        "is_full_time", "is_faculty", "is_resident", "is_research",
        "research_category", "has_complete_record", "appointment_count_for_name",
    ]
    df = df[ordered]

    CLEAN_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_CSV, index=False)
    print(f"\nWrote {len(df):,} records ({df['year'].nunique()} years) "
          f"-> {CLEAN_CSV.relative_to(ROOT)}")

    # --- quality report ------------------------------------------------------
    report = {
        "years": sorted(df["year"].unique().tolist()),
        "records_by_year": df["year"].value_counts().sort_index().to_dict(),
        "missing_by_year": missing,
        "missing_note": (
            "'empty' counts source fields published as an empty string. Academic "
            "rank is reported separately via rank_status, which distinguishes "
            f"'{NOT_APPLICABLE}' (the field cannot apply to this role) from "
            f"'{NOT_REPORTED}' (a faculty record with no rank published)."
        ),
        "rank_status_by_year": {
            y: g["rank_status"].value_counts().to_dict()
            for y, g in df.groupby("year")
        },
        "incomplete_records_by_year": {
            y: int((~g["has_complete_record"]).sum()) for y, g in df.groupby("year")
        },
        "salary_range_by_year": {
            y: {"min": float(g["salary"].min()), "max": float(g["salary"].max())}
            for y, g in df.groupby("year")
        },
        "cardinality_by_year": {
            y: {c: int(g[c].nunique()) for c in
                ["unit", "department", "job_title", "eeo_category", "faculty_rank"]}
            for y, g in df.groupby("year")
        },
        "eeo_values": sorted(df["eeo_category"].unique().tolist()),
        "faculty_rank_values": sorted(
            r for r in df["faculty_rank"].unique() if r not in (NOT_APPLICABLE, NOT_REPORTED)
        ),
        "appointments_by_year": appointments,
        "appointments_caveat": (
            "Distinct-name counts approximate headcount. Two different employees "
            "sharing a name are indistinguishable in this source, so this is a "
            "lower bound on people and is never reported as an exact person count."
        ),
        "research_by_year": {
            y: {"records": int(g["is_research"].sum()),
                "by_category": g["research_category"].value_counts().to_dict()}
            for y, g in df.groupby("year")
        },
        "residents_by_year": {y: int(g["is_resident"].sum()) for y, g in df.groupby("year")},
    }
    QUALITY_JSON.write_text(json.dumps(report, indent=2, default=str))
    print(f"Wrote data quality report -> {QUALITY_JSON.relative_to(ROOT)}")

    print("\nMissing / empty source fields:")
    any_missing = False
    for year, blk in missing.items():
        gaps = {c: v["empty"] for c, v in blk["columns"].items() if v["empty"]}
        if gaps:
            any_missing = True
            print(f"  {year}: " + ", ".join(f"{c}={n:,}" for c, n in gaps.items()))
        else:
            print(f"  {year}: no empty values in any analysed column")
    if any_missing:
        print("  (Rank blanks are expected for non-faculty - see rank_status.)")

    for year, counts in report["rank_status_by_year"].items():
        print(f"  {year} rank status: {counts}")


if __name__ == "__main__":
    main()
