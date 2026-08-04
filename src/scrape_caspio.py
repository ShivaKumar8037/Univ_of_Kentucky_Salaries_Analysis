"""
Scrape the University of Kentucky 2024-25 salary database.

The data is published as a Caspio "Search and Report" datapage:
    https://c0ezh160.caspio.com/dp/be542000f51b67c67dbd45399571

Caspio does not expose a public API for this datapage, so the scraper drives the
same AJAX endpoints the page's own JavaScript uses. Three mechanics matter:

1.  The public URL returns a 419-byte wrapper containing only a <script> tag.
    Real content is served only when a request carries a `cbqe=` parameter (a
    base64-encoded bundle of embed settings) or a `?rnd=<ms>` cache-buster.

2.  Pagination returns JSON, not HTML. A multipart POST with
    `AjaxAction=GetData` yields an envelope with `totalRecords`,
    `totalPageCount` and `responseText` -- the last holding the <tr> markup for
    one page of results.

3.  `appSession` rotates on every response. Each reply issues a fresh token that
    must be carried into the next request; reusing the original token breaks the
    walk partway through.

Blank search criteria return the full result set (26,430 records). Caspio locks
the page size at 25 server-side -- larger values are accepted and silently
ignored -- so a complete extract requires 1,058 sequential requests.

Usage:
    python src/scrape_caspio.py

The run is resumable: each page is cached to data/raw/pages/page_NNNN.json and
already-cached pages are skipped, so an interrupted run resumes where it left
off rather than restarting.
"""

from __future__ import annotations

import base64
import json
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# --- Source configuration ----------------------------------------------------

HOST = "https://c0ezh160.caspio.com"

# The university publishes one datapage per salary year, all on the same Caspio
# account and all sharing the same ten-column schema.
DATASETS = {
    "2024-25": "be542000f51b67c67dbd45399571",
    "2025-26": "be542000f9ee31dd817a4a8c9f2e",
}
DEFAULT_YEAR = "2025-26"

# Set by configure(); module-level so the scraper reads like a single-target
# script while still supporting several years.
APP_KEY = DATASETS[DEFAULT_YEAR]
BASE = f"{HOST}/dp/{APP_KEY}"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# The datapage's six search fields, with the comparison operator each one uses.
# These are submitted with empty values to match every record.
SEARCH_FIELDS = [
    ("1", "LastName", "LIKE"),
    ("2", "FirstName", "="),
    ("3", "AdministrativeUnitOrCollege", "="),
    ("4", "Department", "LIKE"),
    ("5", "JobTitle", "LIKE"),
    ("6", "SalaryTrueAnnual", "LIKE"),
]

# Column order as rendered by the datapage.
COLUMNS = [
    "LastName",
    "FirstName",
    "AdministrativeUnitOrCollege",
    "Department",
    "JobTitle",
    "Position",
    "EEO",
    "Rank",
    "FullOrPartTime",
    "SalaryTrueAnnual",
]

# Record counts confirmed against each datapage's own reported total.
EXPECTED_RECORDS = {"2024-25": 26_430, "2025-26": 27_004}
PAGE_SIZE = 25

# --- Paths -------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
YEAR = DEFAULT_YEAR
PAGE_CACHE = ROOT / "data" / "raw" / f"pages_{YEAR.replace('-', '_')}"
RAW_CSV = ROOT / "data" / "raw" / f"uk_salaries_{YEAR.replace('-', '_')}.csv"


def configure(year: str) -> None:
    """Point the module at one of the published salary years."""
    global APP_KEY, BASE, YEAR, PAGE_CACHE, RAW_CSV
    if year not in DATASETS:
        raise SystemExit(f"Unknown year {year!r}. Options: {', '.join(DATASETS)}")
    YEAR = year
    APP_KEY = DATASETS[year]
    BASE = f"{HOST}/dp/{APP_KEY}"
    slug = year.replace("-", "_")
    PAGE_CACHE = ROOT / "data" / "raw" / f"pages_{slug}"
    RAW_CSV = ROOT / "data" / "raw" / f"uk_salaries_{slug}.csv"

# --- Politeness --------------------------------------------------------------

MIN_DELAY = 0.30
MAX_DELAY = 0.55
MAX_RETRIES = 4


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _now_ms() -> int:
    return int(time.time() * 1000)


class CaspioScraper:
    """Drives the Caspio datapage's AJAX endpoints to walk the full result set."""

    def __init__(self) -> None:
        self.session: requests.Session | None = None
        self.results_uid: str | None = None
        self.app_session: str | None = None
        self.total_records: int | None = None
        self.total_pages: int | None = None

    # -- session bootstrap ----------------------------------------------------

    def bootstrap(self) -> None:
        """Establish a datapage session and run the initial blank search.

        Populates `results_uid` (the unique id of the results section) and
        `app_session` (the rotating token), which together authorise the
        subsequent GetData calls.
        """
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Referer": BASE})

        # 1. Prime cookies (AWSALB load-balancer affinity + cookie-consent flags).
        s.get(BASE, timeout=30).raise_for_status()

        # 2. Request the datapage payload. The `cbqe` bundle is what makes the
        #    server return the real datapage instead of the wrapper shell.
        params = [
            f"AppKey={APP_KEY}",
            "js=true",
            "cbEmbDeployWith=new_async_embedjs",
            "cbDatapageAnchorId=dp_anchor_id_12345",
            f"pathname={BASE}",
            "cbScreenWidth=1280",
            "cbEmbQueryStr=",
            "cbParamList=",
        ]
        cbqe = base64.b64encode("&".join(params).encode()).decode()
        payload = s.get(
            f"{BASE}?cbqe={urllib.parse.quote(cbqe)}&cbEmbedTimeStamp={_now_ms()}",
            timeout=30,
        ).text

        # The payload embeds two 14-hex-digit section ids: the search form's and
        # the results section's, in that order.
        ids = list(dict.fromkeys(re.findall(r"_[0-9a-f]{14}", payload)))
        if len(ids) < 2:
            raise RuntimeError(
                f"Could not locate datapage section ids (found {len(ids)}). "
                "The datapage markup may have changed."
            )
        search_uid, results_uid = ids[0], ids[1]

        # 3. Submit the search with every criterion blank -> matches all records.
        form: dict[str, str] = {"cbUniqueFormId": search_uid}
        for idx, field, comparison in SEARCH_FIELDS:
            form.update(
                {
                    f"FieldName{idx}": field,
                    f"Operator{idx}": "OR",
                    f"NumCriteriaDetails{idx}": "1",
                    f"ComparisonType{idx}_1": comparison,
                    f"MatchNull{idx}_1": "N",
                    f"Value{idx}_1": "",
                }
            )
        form.update(
            {
                "AppKey": APP_KEY,
                "PrevPageID": "1",
                "cbPageType": "Search",
                "ClientQueryString": "",
                "pathname": BASE,
                "PageID": "2",
                "GlobalOperator": "AND",
                "NumCriteria": "6",
                "Search": "1",
                "cbSpaInitialSearch": "True",
                "cbSearchResultsUniqueId": results_uid,
                "AjaxAction": "SearchForm",
                "GridMode": "False",
                "js": "true",
                "AjaxActionHostName": HOST,
                "cbAjaxReferrer": BASE,
                "cbParamList": "",
            }
        )

        envelope = self._post(s, form)
        app_session = envelope.get("appSession")
        if not app_session:
            raise RuntimeError("Search response carried no appSession token.")

        self.session = s
        self.results_uid = results_uid
        self.app_session = app_session
        log(f"Session established (results section {results_uid}).")

    # -- transport ------------------------------------------------------------

    @staticmethod
    def _post(session: requests.Session, fields: dict[str, str]) -> dict:
        """POST `fields` as multipart/form-data and return the JSON envelope.

        Caspio requires multipart encoding here; form-urlencoded bodies are
        rejected with the wrapper shell. requests builds the multipart body when
        given `files`, and a (None, value) tuple emits a plain field rather than
        a file part.
        """
        multipart = {k: (None, v) for k, v in fields.items()}
        response = session.post(
            f"{BASE}?rnd={_now_ms()}",
            files=multipart,
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    # -- page retrieval -------------------------------------------------------

    def fetch_page(self, page: int) -> list[list[str]]:
        """Fetch one page of results, carrying the rotating session token forward."""
        fields = {
            "ClientQueryString": "",
            "appSession": self.app_session or "",
            "siblingDataPageAppSessions": "{}",
            "AjaxAction": "GetData",
            "GridMode": "False",
            "cbUniqueFormId": self.results_uid or "",
            "js": "true",
            "cbCurrentPageSize": str(PAGE_SIZE),
            "CPIPage": str(page),
            "CPIOrderBy": "",
            "CPISortType": "",
            "PageID": "2",
            "AjaxActionHostName": HOST,
            "cbAjaxReferrer": BASE,
            "cbParamList": "",
        }
        assert self.session is not None
        envelope = self._post(self.session, fields)

        # Carry the freshly-issued token into the next request.
        if envelope.get("appSession"):
            self.app_session = envelope["appSession"]

        if envelope.get("totalRecords") is not None:
            self.total_records = envelope["totalRecords"]
            self.total_pages = envelope["totalPageCount"]

        markup = envelope.get("responseText")
        if not markup:
            raise SessionExpired(f"Page {page} returned no responseText.")

        return parse_rows(markup)

    def fetch_page_resilient(self, page: int) -> list[list[str]]:
        """fetch_page with retries, backoff, and session re-bootstrap on expiry."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self.fetch_page(page)
            except SessionExpired:
                log(f"  page {page}: session expired, re-establishing...")
                self.bootstrap()
            except (requests.RequestException, ValueError) as exc:
                backoff = 2**attempt
                log(f"  page {page}: {type(exc).__name__} ({exc}); retry in {backoff}s")
                time.sleep(backoff)
                if attempt >= 2:
                    self.bootstrap()
        raise RuntimeError(f"Page {page} failed after {MAX_RETRIES} attempts.")


class SessionExpired(RuntimeError):
    """Raised when a response comes back without result markup."""


def parse_rows(markup: str) -> list[list[str]]:
    """Extract data rows from a page's result-table markup.

    Each cell embeds a responsive label that must be removed first:
        <td><span class="cbResultSetLabel">Last Name:</span>Aaron</td>
    Stripping tags naively would yield "Last Name:Aaron", so the label span is
    decomposed before the cell text is read.
    """
    soup = BeautifulSoup(markup, "lxml")
    rows: list[list[str]] = []

    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < len(COLUMNS):
            continue  # header / navigation rows
        values = []
        for td in cells[: len(COLUMNS)]:
            for label in td.select("span.cbResultSetLabel"):
                label.decompose()
            values.append(td.get_text(strip=True))
        rows.append(values)

    return rows


def page_cache_path(page: int) -> Path:
    return PAGE_CACHE / f"page_{page:04d}.json"


def scrape() -> None:
    PAGE_CACHE.mkdir(parents=True, exist_ok=True)

    scraper = CaspioScraper()
    scraper.bootstrap()

    # Page 1 also tells us the true total, which drives the loop bound.
    first_rows = scraper.fetch_page(1)
    page_cache_path(1).write_text(json.dumps(first_rows))

    expected = EXPECTED_RECORDS.get(YEAR)
    total_records = scraper.total_records or expected or 0
    total_pages = scraper.total_pages or 1
    log(f"{YEAR}: {total_records:,} records across {total_pages:,} pages.")
    if expected and total_records != expected:
        log(
            f"NOTE: expected {expected:,} records but the source reports "
            f"{total_records:,}. The upstream dataset may have been updated."
        )

    fetched = cached = 0
    for page in range(2, total_pages + 1):
        cache_file = page_cache_path(page)
        if cache_file.exists():
            cached += 1
            continue

        rows = scraper.fetch_page_resilient(page)
        cache_file.write_text(json.dumps(rows))
        fetched += 1

        if page % 25 == 0:
            pct = 100 * page / total_pages
            log(f"  page {page:>4}/{total_pages} ({pct:5.1f}%)")

        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    log(f"Pages fetched this run: {fetched:,} (skipped {cached:,} already cached).")
    write_csv(total_pages, total_records)


def write_csv(total_pages: int, total_records: int) -> None:
    """Concatenate cached pages into the raw CSV, in page order."""
    import csv

    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    written = 0

    with RAW_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for page in range(1, total_pages + 1):
            cache_file = page_cache_path(page)
            if not cache_file.exists():
                log(f"WARNING: page {page} missing from cache; skipping.")
                continue
            for row in json.loads(cache_file.read_text()):
                writer.writerow(row)
                written += 1

    log(f"Wrote {written:,} rows -> {RAW_CSV.relative_to(ROOT)}")

    if written != total_records:
        log(
            f"WARNING: wrote {written:,} rows but the source reported "
            f"{total_records:,}. Delete data/raw/pages and re-run to repair."
        )
        sys.exit(1)
    log("Row count matches the source total.")


if __name__ == "__main__":
    # Usage: python src/scrape_caspio.py [year|all]
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_YEAR
    years = list(DATASETS) if arg == "all" else [arg]
    start = time.time()
    for y in years:
        configure(y)
        log(f"=== {y} (app key {APP_KEY}) ===")
        scrape()
    log(f"Done in {time.time() - start:.0f}s.")
