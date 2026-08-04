# Anatomy of a Public Payroll

**Where the University of Kentucky's $2.15 billion salary bill goes** — every
salary record the university publishes, for 2024-25 and 2025-26, extracted,
verified, and made readable.

By **Shiva Kumar P** · [LinkedIn](https://www.linkedin.com/in/shivakumar-p-/)

The university publishes this data through a search box that shows 25 rows at a
time, with no export and no API. This project reconstructs the complete dataset
for both published years, checks it against independently reported figures, and
turns it into a report and an interactive dashboard.

## Read it

| | |
|---|---|
| **[Interactive dashboard](https://shivakumar8037.github.io/uk-salaries/)** | Filterable explorer, six-chapter story, data notes. Self-contained, opens offline |
| **[16-page report](https://shivakumar8037.github.io/uk-salaries/UK_Salary_Analysis.pdf)** | The primary artifact |
| **[Methodology](docs/METHODOLOGY.md)** | Data flow, dictionary, missing-data handling, decision log, limitations |

## What it shows (2025-26)

- **$2.15 billion** across **27,004 records**, 34 units, 765 departments.
- Payroll grew **$87.1M (+4.2%)** in a year while headcount grew 2.2%.
- Mean **$79,549**, median **$61,465** — a long tail pulls the average $18,000
  above what a typical employee earns.
- **27% of records are part-time.** Salaries are FTE-adjusted, so pooling them
  drags every average down; the full-time median is **$69,804**.
- The top 10% of earners hold **32.5%** of the payroll (Gini 0.407).
- **59%** of full-time postdocs earn less than the $61,008 NIH entry stipend —
  down from 71%, as their median rose from $56,484 to $60,000.
- Across 160 job titles present in both years, the median change was **+1.2%**,
  so the headline rise is genuine pay movement, not a changing mix of jobs.

Base salary only — excludes benefits, bonuses, incentive pay and supplements.

## Privacy

**No individual is named anywhere in this repository.** The source database
publishes names; this project drops them in `src/clean.py` before any analysis
runs, and the name-bearing extracts under `data/raw/` are withheld from the
release. Roles at the top of the scale are identified by job title and unit
only. No demographic attribute is inferred — the dataset contains none.

## Running it

```bash
pip install -r requirements.txt
python src/scrape_caspio.py all    # ~22 min, resumable, rebuilds data/raw/
python src/clean.py                # drops names, writes the analysis dataset
python src/analysis.py             # prints the acceptance table
python src/build_report.py         # -> docs/UK_Salary_Analysis.pdf
python src/build_dashboard.py      # -> docs/index.html
```

`data/processed/` is committed, so the last three steps run without scraping.

## Verification

The extract is checked against figures published independently from the same
source. Record count, mean and median match exactly:

```
check                    expected     computed     delta
record_count               26,430       26,430   +0.00%  OK
mean_salary                77,981       77,981   +0.00%  OK
median_salary              60,779       60,779   +0.00%  OK
count_over_500k               130          128   -1.54%  OK
```

## Licence

Code MIT ([LICENSE](LICENSE)). The underlying salary data is a public record
released by the University of Kentucky under the Kentucky Open Records Act;
retrieved 2026-08-04.
