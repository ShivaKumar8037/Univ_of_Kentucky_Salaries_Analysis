"""
Build the self-contained interactive dashboard (V2).

Reads  : data/processed/uk_salaries_clean.csv, summary_stats.json,
         data_quality_report.json
Writes : docs/index.html

Everything (plotly.js, data, styles) is inlined, so the file opens offline from
disk with no server and no network.

Structure:
  1. Explorer  - filters + KPI tiles + five charts, recomputed client-side.
  2. Story     - a guided narrative in six chapters, each with its own charts,
                 so a reader who does not want to operate filters still gets
                 the findings.
  3. Data notes- missing / empty fields stated explicitly rather than hidden.

Full-time and part-time carry fixed colours with a legend wherever they appear.
No individual is named.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly

import viz_style as vs

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
CLEAN = PROC / "uk_salaries_clean.csv"
STATS = json.loads((PROC / "summary_stats.json").read_text())
QUALITY = json.loads((PROC / "data_quality_report.json").read_text())
OUT = ROOT / "docs" / "index.html"

PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"

NOT_REPORTED = "Not reported"


def build_payload(df: pd.DataFrame) -> dict:
    """Dictionary-encode the record-level data the Explorer filters over."""
    years = sorted(df["year"].unique())
    units = sorted(df["unit"].dropna().unique())
    eeos = sorted(df["eeo_category"].dropna().unique())
    rescats = sorted(df["research_category"].dropna().unique())
    titles = sorted(df["job_title"].dropna().unique())

    uidx = {v: i for i, v in enumerate(units)}
    eidx = {v: i for i, v in enumerate(eeos)}
    ridx = {v: i for i, v in enumerate(rescats)}
    tidx = {v: i for i, v in enumerate(titles)}

    return {
        "years": years,
        "units": units, "eeos": eeos, "rescats": rescats, "titles": titles,
        "yr": [years.index(v) for v in df["year"]],
        "unit": [uidx[v] for v in df["unit"]],
        "eeo": [eidx[v] for v in df["eeo_category"]],
        "ft": [1 if v else 0 for v in df["is_full_time"]],
        "res": [ridx[v] if isinstance(v, str) else -1 for v in df["research_category"]],
        "title": [tidx[v] for v in df["job_title"]],
        "sal": [int(round(v)) for v in df["salary"]],
    }


def build_story(latest: str) -> dict:
    """Precomputed series for the narrative charts.

    These do not respond to the Explorer filters -- the story is a fixed
    argument, and its charts must keep saying the same thing.
    """
    cur = STATS["years"][latest]
    cmp_ = STATS.get("comparison")

    story: dict = {
        "latest": latest,
        "years": STATS["year_list"],
        "overview": cur["overview"],
        "distribution": cur["distribution"],
        "concentration": cur["concentration"],
        "bands_ft": cur["bands_by_time_status"],
        "by_unit": cur["by_unit"][:12],
        "by_eeo": cur["by_eeo"],
        "research": cur["research"],
        "faculty": cur["faculty"],
        "dispersion": cur["dispersion"]["most_dispersed"][:10],
        "floor": cur["floor"],
        "top_roles": cur["top_roles"][:10],
        "residents": cur["residents"],
        "per_year": {
            y: {
                "records": STATS["years"][y]["overview"]["records"],
                "payroll": STATS["years"][y]["overview"]["total_payroll"],
                "median": STATS["years"][y]["distribution"]["all"]["median"],
                "mean": STATS["years"][y]["distribution"]["all"]["mean"],
                "median_ft": STATS["years"][y]["distribution"]["full_time"]["median"],
                "part_time": STATS["years"][y]["overview"]["part_time_records"],
                "full_time": STATS["years"][y]["overview"]["full_time_records"],
                "research": STATS["years"][y]["research"]["records"],
                "postdoc_median": STATS["years"][y]["research"]["postdoc"]["median"],
                "postdoc_below_nih": STATS["years"][y]["research"]["postdoc"]["share_ft_below_nih_entry"],
            }
            for y in STATS["year_list"]
        },
    }
    if cmp_:
        story["comparison"] = {
            "prev": cmp_["prev"], "curr": cmp_["curr"],
            "headline": cmp_["headline"],
            "by_unit": cmp_["by_unit"][:12],
            "matched_titles": {
                k: cmp_["matched_titles"][k]
                for k in ("min_per_year", "titles_compared", "median_of_median_pct",
                          "share_with_increase", "share_flat_or_down",
                          "biggest_gains", "biggest_losses")
            },
            "research": cmp_["research"],
            "postdoc": cmp_["postdoc"],
            "floor": cmp_["floor"],
        }
    return story


def build_quality() -> dict:
    """Missing-data facts, stated plainly."""
    return {
        "missing_by_year": QUALITY.get("missing_by_year", {}),
        "rank_status_by_year": QUALITY.get("rank_status_by_year", {}),
        "incomplete_by_year": QUALITY.get("incomplete_records_by_year", {}),
        "appointments": QUALITY.get("appointments_by_year", {}),
        "note": QUALITY.get("missing_note", ""),
        "caveat": QUALITY.get("appointments_caveat", ""),
    }


def main() -> None:
    df = pd.read_csv(CLEAN)
    latest = STATS["latest"]

    html = TEMPLATE
    html = html.replace("__PLOTLY__", PLOTLY_JS.read_text())
    html = html.replace("__DATA__", json.dumps(build_payload(df), separators=(",", ":")))
    html = html.replace("__STORY__", json.dumps(build_story(latest), separators=(",", ":"),
                                                default=str))
    html = html.replace("__QUALITY__", json.dumps(build_quality(), separators=(",", ":"),
                                                  default=str))
    html = html.replace("__AUTHOR__", vs.AUTHOR)
    html = html.replace("__LINKEDIN__", vs.AUTHOR_LINKEDIN)
    html = html.replace("__GITHUB__", vs.AUTHOR_GITHUB)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024/1024:.1f} MB)")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UK Salaries - Anatomy of a Public Payroll</title>
<script>__PLOTLY__</script>
<style>
:root{
  --uk-blue:#0033A0; --uk-blue-dark:#00256f; --uk-tint:#e8eefb;
  --surface:#fcfcfb; --page:#f4f4f1; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7;
  --blue:#1b52c4; --orange:#eb6834; --aqua:#1baf7a; --prev:#b0aea6; --missing:#c9c7bf;
  --border:rgba(11,11,11,.12);
  --sans:"Avenir Next",Avenir,"Nunito Sans","Segoe UI",system-ui,sans-serif;
  --serif:"Mercury Display",Georgia,"Times New Roman",serif;
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:var(--sans);
  font-size:15.5px;line-height:1.6;-webkit-font-smoothing:antialiased}
h1,h2,h3,.serif{font-family:var(--serif);font-weight:700;letter-spacing:-.01em}

/* ---- masthead ---- */
header{background:var(--uk-blue);color:#fff;padding:34px 32px 30px}
.hwrap{max-width:1280px;margin:0 auto}
header .eyebrow{font-size:11px;letter-spacing:.18em;text-transform:uppercase;
  color:#a9c0ee;font-weight:700;margin-bottom:10px;font-family:var(--sans)}
header h1{margin:0 0 10px;font-size:38px;line-height:1.12}
header p{margin:0;color:#cfdcf6;font-size:15.5px;max-width:74ch}
header .by{margin-top:18px;font-size:13.5px;color:#cfdcf6;font-family:var(--sans)}
header .by a{color:#fff;text-decoration:none;border-bottom:1px solid rgba(255,255,255,.45)}
header .by a:hover{border-bottom-color:#fff}

nav.jump{background:var(--uk-blue-dark);padding:0 32px}
nav.jump ul{max-width:1280px;margin:0 auto;padding:0;list-style:none;display:flex;
  flex-wrap:wrap;gap:2px}
nav.jump a{display:block;padding:11px 15px;color:#cfdcf6;text-decoration:none;
  font-size:13.5px;font-weight:600}
nav.jump a:hover{background:rgba(255,255,255,.10);color:#fff}

.wrap{max-width:1280px;margin:0 auto;padding:30px 32px 40px}
section{scroll-margin-top:12px}
.sec-head{margin:44px 0 6px}
.sec-head .kicker{font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--uk-blue);font-weight:800}
.sec-head h2{margin:6px 0 8px;font-size:27px}
.sec-head p.lede{margin:0;font-size:16.5px;color:var(--ink2);max-width:78ch}

/* ---- tiles ---- */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:14px;margin:20px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:15px 17px}
.tile .v{font-size:25px;font-weight:700;color:var(--uk-blue);line-height:1.15;
  font-family:var(--serif)}
.tile .l{font-size:12.5px;color:var(--ink2);margin-top:4px}
.tile .d{font-size:12px;margin-top:5px;font-weight:600}
.up{color:#0a7d32}.down{color:#c0392b}.flat{color:var(--muted)}

/* ---- filters ---- */
.filters{display:flex;flex-wrap:wrap;gap:13px;align-items:flex-end;background:var(--surface);
  border:1px solid var(--border);border-radius:10px;padding:16px 18px;margin-bottom:20px}
.filters label{display:block;font-size:11px;color:var(--ink2);margin-bottom:5px;
  text-transform:uppercase;letter-spacing:.06em;font-weight:700}
select,button{font:inherit;font-size:14px;padding:8px 11px;border:1px solid var(--axis);
  border-radius:7px;background:#fff;color:var(--ink)}
button{cursor:pointer;background:var(--uk-blue);color:#fff;border-color:var(--uk-blue);font-weight:700}
button.ghost{background:#fff;color:var(--ink2);border-color:var(--axis);font-weight:600}
button:hover{opacity:.9}
.count{font-size:13px;color:var(--ink2);margin-left:auto;text-align:right}

/* ---- cards & legend ---- */
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:18px 20px;margin-bottom:18px}
.card h3{margin:0 0 3px;font-size:17px}
.card p.sub{margin:0 0 10px;font-size:13.5px;color:var(--ink2)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px}
@media(max-width:980px){.grid2,.grid3{grid-template-columns:1fr}}
.plot{width:100%;height:330px}
.plot.tall{height:390px}

.legend{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin:2px 0 10px;
  font-size:13px;color:var(--ink2)}
.legend .item{display:flex;align-items:center;gap:7px}
.swatch{width:13px;height:13px;border-radius:3px;flex:none;
  box-shadow:0 0 0 2px var(--surface)}
.sw-ft{background:var(--blue)}.sw-pt{background:var(--orange)}
.sw-prev{background:var(--prev)}.sw-curr{background:var(--blue)}
.sw-missing{background:var(--missing)}

/* ---- story ---- */
.story .chapter{background:var(--surface);border:1px solid var(--border);border-radius:12px;
  padding:26px 28px;margin-bottom:22px}
.story .chapter .num{font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--uk-blue);font-weight:800}
.story .chapter h3{margin:7px 0 10px;font-size:24px;line-height:1.22}
.story .chapter p{margin:0 0 13px;max-width:80ch;color:var(--ink2)}
.story .chapter p strong{color:var(--ink)}
.pull{border-left:4px solid var(--uk-blue);background:var(--uk-tint);padding:14px 18px;
  border-radius:0 8px 8px 0;margin:16px 0;font-size:16px;color:var(--ink);max-width:80ch}
.pull b{font-family:var(--serif);font-size:19px}

/* ---- data notes ---- */
table.dq{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:6px}
table.dq th,table.dq td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--grid)}
table.dq th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink2)}
table.dq td.num{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:#0a7d32;font-weight:600}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11.5px;
  font-weight:700;background:var(--uk-tint);color:var(--uk-blue)}

footer{background:var(--uk-blue);color:#cfdcf6;padding:34px 32px 40px;margin-top:40px}
footer .fwrap{max-width:1280px;margin:0 auto}
footer h4{margin:0 0 8px;color:#fff;font-family:var(--serif);font-size:19px}
footer p{margin:0 0 10px;font-size:13.5px;max-width:82ch}
footer a{color:#fff;text-decoration:none;border-bottom:1px solid rgba(255,255,255,.45)}
footer a:hover{border-bottom-color:#fff}
.links{display:flex;gap:22px;flex-wrap:wrap;margin:16px 0 6px;font-size:14.5px;font-weight:600}

@media print{
  body{background:#fff;font-size:11pt}
  header{background:#fff;color:var(--ink);border-bottom:3px solid var(--uk-blue);padding:0 0 10px}
  header h1{font-size:24pt}header p,header .by{color:var(--ink2)}
  header .by a,footer a{color:var(--ink2)}
  nav.jump{display:none}.filters{display:none}button{display:none}
  .wrap{max-width:none;padding:0}
  .card,.story .chapter{break-inside:avoid;page-break-inside:avoid;border:1px solid var(--grid)}
  footer{background:#fff;color:var(--ink2);border-top:2px solid var(--uk-blue)}
  footer h4{color:var(--ink)}
  @page{size:landscape;margin:12mm}
}
</style></head><body>

<header><div class="hwrap">
  <div class="eyebrow">University of Kentucky &middot; Salary Data Analysis</div>
  <h1>Anatomy of a Public Payroll</h1>
  <p>Every employee salary record the University of Kentucky publishes, for
     <span id="yrRange"></span> &mdash; extracted, verified, and made explorable.
     Base salary only. No individual is named anywhere in this analysis.</p>
  <div class="by">Built by <strong>__AUTHOR__</strong> &middot;
    <a href="__LINKEDIN__" target="_blank" rel="noopener">LinkedIn</a> &middot;
    <a href="__GITHUB__" target="_blank" rel="noopener">GitHub</a></div>
</div></header>

<nav class="jump"><ul>
  <li><a href="#explore">Explore the data</a></li>
  <li><a href="#story">The story</a></li>
  <li><a href="#c1">1. A payroll that grew</a></li>
  <li><a href="#c2">2. Average vs typical</a></li>
  <li><a href="#c3">3. A health system</a></li>
  <li><a href="#c4">4. The research mission</a></li>
  <li><a href="#c5">5. Ladder and floor</a></li>
  <li><a href="#c6">6. What actually changed</a></li>
  <li><a href="#notes">Data notes</a></li>
</ul></nav>

<div class="wrap">

<!-- ============================ EXPLORER ============================ -->
<section id="explore">
  <div class="sec-head">
    <div class="kicker">Part one</div>
    <h2>Explore the data</h2>
    <p class="lede">Filter the full record set. Every chart below responds to these
      controls, and full-time and part-time staff keep the same two colours throughout.</p>
  </div>

  <div class="tiles" id="tiles"></div>

  <div class="filters">
    <div><label for="fYear">Salary year</label><select id="fYear"></select></div>
    <div><label for="fUnit">Administrative unit</label><select id="fUnit"></select></div>
    <div><label for="fEeo">Occupational category</label><select id="fEeo"></select></div>
    <div><label for="fTime">Time status</label><select id="fTime">
      <option value="-1">All</option><option value="1">Full-time</option>
      <option value="0">Part-time</option></select></div>
    <div><label for="fRes">Research workforce</label><select id="fRes"></select></div>
    <button class="ghost" id="reset">Reset</button>
    <button id="pdf">Download as PDF</button>
    <span class="count" id="count"></span>
  </div>

  <div class="legend">
    <span class="item"><span class="swatch sw-ft"></span> Full-time</span>
    <span class="item"><span class="swatch sw-pt"></span> Part-time</span>
    <span style="color:var(--muted);font-size:12.5px">
      Salaries are FTE-adjusted, so part-time staff show reduced annual figures.</span>
  </div>

  <div class="card">
    <h3>Salary distribution</h3>
    <p class="sub">Log scale. Full-time and part-time are stacked so the part-time
      block at the low end is visible rather than hidden inside one total.</p>
    <div id="pDist" class="plot tall"></div>
  </div>

  <div class="grid2">
    <div class="card"><h3>Headcount by unit</h3>
      <p class="sub">Top 12 units in the current selection, split by time status.</p>
      <div id="pUnit" class="plot tall"></div></div>
    <div class="card"><h3>Median pay by occupational category</h3>
      <p class="sub">Full-time and part-time medians shown separately &mdash; pooling
        them would understate typical pay.</p>
      <div id="pEeo" class="plot tall"></div></div>
  </div>

  <div class="grid2">
    <div class="card"><h3>Salary bands</h3>
      <p class="sub">How the selection spreads across pay ranges.</p>
      <div id="pBand" class="plot"></div></div>
    <div class="card"><h3>Highest-paid roles</h3>
      <p class="sub">Job title and unit only &mdash; individuals are never identified.</p>
      <div id="pTop" class="plot"></div></div>
  </div>
</section>

<!-- ============================= STORY ============================= -->
<section id="story" class="story">
  <div class="sec-head">
    <div class="kicker">Part two</div>
    <h2>The story in the numbers</h2>
    <p class="lede">You do not have to dig for it. Six chapters, each with the charts
      that make the case. All figures are computed from the same extract you can
      filter above.</p>
  </div>

  <div class="chapter" id="c1">
    <div class="num">Chapter one</div>
    <h3 id="c1h"></h3>
    <div id="c1body"></div>
    <div class="legend" id="c1legend"></div>
    <div class="grid2">
      <div><div id="pYoYTotals" class="plot"></div></div>
      <div><div id="pYoYUnit" class="plot"></div></div>
    </div>
  </div>

  <div class="chapter" id="c2">
    <div class="num">Chapter two</div>
    <h3 id="c2h"></h3>
    <div id="c2body"></div>
    <div class="legend">
      <span class="item"><span class="swatch sw-ft"></span> Full-time</span>
      <span class="item"><span class="swatch sw-pt"></span> Part-time</span>
    </div>
    <div class="grid2">
      <div><div id="pAvg" class="plot"></div></div>
      <div><div id="pLorenz" class="plot"></div></div>
    </div>
  </div>

  <div class="chapter" id="c3">
    <div class="num">Chapter three</div>
    <h3 id="c3h"></h3>
    <div id="c3body"></div>
    <div class="grid2">
      <div><div id="pUnitShare" class="plot tall"></div></div>
      <div><div id="pUnitPT" class="plot tall"></div></div>
    </div>
  </div>

  <div class="chapter" id="c4">
    <div class="num">Chapter four</div>
    <h3 id="c4h"></h3>
    <div id="c4body"></div>
    <div class="grid2">
      <div><div id="pResCat" class="plot"></div></div>
      <div><div id="pPostdoc" class="plot"></div></div>
    </div>
  </div>

  <div class="chapter" id="c5">
    <div class="num">Chapter five</div>
    <h3 id="c5h"></h3>
    <div id="c5body"></div>
    <div class="grid2">
      <div><div id="pLadder" class="plot tall"></div></div>
      <div><div id="pDisp" class="plot tall"></div></div>
    </div>
  </div>

  <div class="chapter" id="c6">
    <div class="num">Chapter six</div>
    <h3 id="c6h"></h3>
    <div id="c6body"></div>
    <div class="grid2">
      <div><div id="pTitleGain" class="plot tall"></div></div>
      <div><div id="pFloor" class="plot"></div></div>
    </div>
  </div>
</section>

<!-- =========================== DATA NOTES =========================== -->
<section id="notes">
  <div class="sec-head">
    <div class="kicker">Part three</div>
    <h2>Data notes &mdash; what is missing, and what this cannot tell you</h2>
    <p class="lede">Gaps are stated rather than quietly filled. Where the source
      publishes an empty field, it is labelled and counted here.</p>
  </div>
  <div class="grid2">
    <div class="card"><h3>Empty and missing fields</h3>
      <p class="sub">Counted per year, straight from the source extract.</p>
      <div id="dqMissing"></div></div>
    <div class="card"><h3>Academic rank</h3>
      <p class="sub">Blank rank means two different things, so the two are separated.</p>
      <div id="dqRank"></div>
      <div class="legend" style="margin-top:12px">
        <span class="item"><span class="swatch sw-missing"></span>
          <span style="font-size:12.5px">"Not reported" appears as its own category in every chart &mdash;
          never dropped, never merged into a real value.</span></span>
      </div></div>
  </div>
  <div class="card">
    <h3>Limitations</h3>
    <div id="dqLimits"></div>
  </div>
</section>

</div>

<footer><div class="fwrap">
  <h4>About this project</h4>
  <p>The University of Kentucky publishes its salary data through a search box that
     returns 25 rows at a time, with no export and no API. This project reconstructs
     the complete dataset for every published year, validates it against
     independently reported figures, and turns it into something you can actually read.</p>
  <p>Source: University of Kentucky salary database (public record, released under the
     Kentucky Open Records Act). <strong>Base salary only</strong> &mdash; excludes benefits,
     bonuses, clinical incentive pay, shift differentials, overtime and athletics
     supplements. Figures are FTE-adjusted. Records, not people: an employee holding
     two appointments appears twice.</p>
  <div class="links">
    <a href="__LINKEDIN__" target="_blank" rel="noopener">LinkedIn &rarr;</a>
    <a href="__GITHUB__" target="_blank" rel="noopener">GitHub &rarr;</a>
  </div>
  <p style="margin-top:10px">Built by <strong>__AUTHOR__</strong>.
     Analysis and visualisation in Python (pandas, matplotlib, Plotly).</p>
</div></footer>

<script>
const D=__DATA__, ST=__STORY__, Q=__QUALITY__;
const N=D.sal.length;
const C={uk:'#0033A0',blue:'#1b52c4',orange:'#eb6834',aqua:'#1baf7a',prev:'#b0aea6',
  missing:'#c9c7bf',ink:'#0b0b0b',ink2:'#52514e',grid:'#e1e0d9',axis:'#c3c2b7',
  surface:'#fcfcfb'};
const FONT='"Avenir Next",Avenir,"Nunito Sans","Segoe UI",system-ui,sans-serif';
const BANDS=[[0,25e3,'Under $25k'],[25e3,4e4,'$25-40k'],[4e4,6e4,'$40-60k'],
  [6e4,8e4,'$60-80k'],[8e4,1e5,'$80-100k'],[1e5,15e4,'$100-150k'],
  [15e4,25e4,'$150-250k'],[25e4,5e5,'$250-500k'],[5e5,Infinity,'$500k+']];

const usd=v=>'$'+Math.round(v).toLocaleString();
const usdC=v=>Math.abs(v)>=1e9?'$'+(v/1e9).toFixed(2)+'B':Math.abs(v)>=1e6?'$'+(v/1e6).toFixed(1)+'M':
  Math.abs(v)>=1e3?'$'+Math.round(v/1e3)+'k':'$'+Math.round(v);
const pc=(v,d=1)=>(v*100).toFixed(d)+'%';
const sgn=(v,d=1)=>(v>=0?'+':'')+(v*100).toFixed(d)+'%';
const med=a=>{if(!a.length)return 0;const s=Float64Array.from(a).sort(),m=s.length>>1;
  return s.length%2?s[m]:(s[m-1]+s[m])/2;};
const num=v=>Number(v).toLocaleString();

const LAY={paper_bgcolor:C.surface,plot_bgcolor:C.surface,
  font:{family:FONT,size:12,color:C.ink2},
  margin:{l:60,r:20,t:34,b:45},
  xaxis:{gridcolor:C.grid,zeroline:false,linecolor:C.axis},
  yaxis:{gridcolor:C.grid,zeroline:false,linecolor:C.axis},
  showlegend:false,hoverlabel:{bgcolor:'#fff',bordercolor:C.axis,font:{family:FONT,color:C.ink}}};
const CFG={displayModeBar:true,displaylogo:false,responsive:true,
  modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']};
const L=o=>{const b=JSON.parse(JSON.stringify(LAY));return Object.assign(b,o);};
const TITLE=t=>({text:t,font:{family:FONT,size:13,color:C.ink},x:0,xanchor:'left'});

/* ---------------- Explorer ---------------- */
const sel=(id,opts,all)=>{const e=document.getElementById(id);
  e.innerHTML=`<option value="-1">${all}</option>`+
    opts.map((o,i)=>`<option value="${i}">${o}</option>`).join('');};
sel('fUnit',D.units,'All units');
sel('fEeo',D.eeos,'All categories');
sel('fRes',D.rescats,'All employees');
document.getElementById('fRes').insertAdjacentHTML('beforeend',
  '<option value="-2">Any research role</option>');
const fy=document.getElementById('fYear');
fy.innerHTML=D.years.map((y,i)=>`<option value="${i}">${y}</option>`).join('');
fy.value=D.years.length-1;
document.getElementById('yrRange').textContent=
  D.years.length>1?`${D.years[0]} and ${D.years[D.years.length-1]}`:D.years[0];

function filtered(){
  const y=+fYear.value,u=+fUnit.value,e=+fEeo.value,t=+fTime.value,r=+fRes.value;
  const out=[];
  for(let i=0;i<N;i++){
    if(D.yr[i]!==y)continue;
    if(u>=0&&D.unit[i]!==u)continue;
    if(e>=0&&D.eeo[i]!==e)continue;
    if(t>=0&&D.ft[i]!==t)continue;
    if(r===-2&&D.res[i]<0)continue;
    if(r>=0&&D.res[i]!==r)continue;
    out.push(i);
  }
  return out;
}

function tiles(idx){
  const sal=idx.map(i=>D.sal[i]);
  const tot=sal.reduce((a,b)=>a+b,0);
  const ftN=idx.filter(i=>D.ft[i]===1).length;
  const yName=D.years[+fYear.value];
  const prevYr=D.years[+fYear.value-1];
  let deltaHTML='';
  if(prevYr&&ST.per_year&&ST.per_year[prevYr]&&fUnit.value=='-1'&&fEeo.value=='-1'
     &&fTime.value=='-1'&&fRes.value=='-1'){
    const p=ST.per_year[prevYr],c=ST.per_year[yName];
    const dr=c.records/p.records-1, dm=c.median/p.median-1;
    deltaHTML=[dr,dm];
  }
  const cells=[
    [num(sal.length),'employee records',deltaHTML?sgn(deltaHTML[0]):null],
    [usdC(tot),'base payroll',null],
    [usd(med(sal)),'median salary',deltaHTML?sgn(deltaHTML[1]):null],
    [usd(sal.length?tot/sal.length:0),'mean salary',null],
    [pc(sal.length?ftN/sal.length:0,0),'full-time',null]
  ];
  document.getElementById('tiles').innerHTML=cells.map(([v,l,d])=>
    `<div class="tile"><div class="v">${v}</div><div class="l">${l}</div>`+
    (d?`<div class="d ${d.startsWith('+')?'up':d.startsWith('-')?'down':'flat'}">${d} vs ${prevYr}</div>`:'')+
    `</div>`).join('');
  document.getElementById('count').textContent=
    `${num(sal.length)} records · ${D.years[+fYear.value]}`;
}

function logBins(sal){
  const lo=Math.log10(Math.max(1000,Math.min(...sal))),hi=Math.log10(Math.max(...sal));
  const nb=42,w=(hi-lo)/nb;
  return {lo,hi,nb,w,ctr:[...Array(nb)].map((_,i)=>lo+w*(i+0.5))};
}
function binCounts(sal,b){
  const c=new Array(b.nb).fill(0);
  sal.forEach(v=>{let k=Math.floor((Math.log10(v)-b.lo)/b.w);
    if(k>=b.nb)k=b.nb-1; if(k<0)k=0; c[k]++;});
  return c;
}

function draw(idx){
  const salAll=idx.map(i=>D.sal[i]).filter(v=>v>0);
  if(!salAll.length){['pDist','pUnit','pEeo','pBand','pTop'].forEach(id=>
    document.getElementById(id).innerHTML=
      '<p style="padding:40px;text-align:center;color:#898781">No records match these filters.</p>');
    return;}
  const ftSal=idx.filter(i=>D.ft[i]===1).map(i=>D.sal[i]).filter(v=>v>0);
  const ptSal=idx.filter(i=>D.ft[i]===0).map(i=>D.sal[i]).filter(v=>v>0);
  const m=med(salAll), mn=salAll.reduce((a,b)=>a+b,0)/salAll.length;

  // Distribution, stacked by time status
  const b=logBins(salAll);
  const TV=[1e3,5e3,1e4,25e3,5e4,1e5,25e4,5e5,1e6,2e6]
    .filter(v=>Math.log10(v)>=b.lo&&Math.log10(v)<=b.hi);
  Plotly.react('pDist',[
    {type:'bar',name:'Full-time',x:b.ctr,y:binCounts(ftSal,b),width:b.w*0.94,
     marker:{color:C.blue},customdata:b.ctr.map(v=>Math.pow(10,v)),
     hovertemplate:'Full-time<br>%{y:,} near %{customdata:$,.0f}<extra></extra>'},
    {type:'bar',name:'Part-time',x:b.ctr,y:binCounts(ptSal,b),width:b.w*0.94,
     marker:{color:C.orange},customdata:b.ctr.map(v=>Math.pow(10,v)),
     hovertemplate:'Part-time<br>%{y:,} near %{customdata:$,.0f}<extra></extra>'}],
    L({barmode:'stack',bargap:0,showlegend:true,
      legend:{orientation:'h',y:1.12,x:0,font:{family:FONT,size:12}},
      xaxis:{gridcolor:C.grid,linecolor:C.axis,range:[b.lo-b.w,b.hi+b.w],
        tickvals:TV.map(v=>Math.log10(v)),ticktext:TV.map(usdC),
        title:'Annual base salary (log scale)'},
      yaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Employees'},
      shapes:[m,mn].map((v,i)=>({type:'line',x0:Math.log10(v),x1:Math.log10(v),
        yref:'paper',y0:0,y1:1,line:{color:i?C.ink:C.ink,width:2,dash:'dash'}})),
      annotations:[
        {x:Math.log10(m),y:1.0,yref:'paper',text:'Median '+usd(m),showarrow:false,
         yanchor:'bottom',xanchor:'right',font:{family:FONT,color:C.ink,size:11.5}},
        {x:Math.log10(mn),y:1.0,yref:'paper',text:'Mean '+usd(mn),showarrow:false,
         yanchor:'bottom',xanchor:'left',font:{family:FONT,color:C.ink2,size:11.5}}]}),CFG);

  // Headcount by unit, split FT/PT
  const uc={};
  idx.forEach(i=>{const k=D.units[D.unit[i]];(uc[k]=uc[k]||[0,0])[D.ft[i]?0:1]++;});
  const us=Object.entries(uc).sort((a,b2)=>(b2[1][0]+b2[1][1])-(a[1][0]+a[1][1]))
    .slice(0,12).reverse();
  Plotly.react('pUnit',[
    {type:'bar',orientation:'h',name:'Full-time',y:us.map(x=>x[0]),x:us.map(x=>x[1][0]),
     marker:{color:C.blue},hovertemplate:'%{y}<br>Full-time %{x:,}<extra></extra>'},
    {type:'bar',orientation:'h',name:'Part-time',y:us.map(x=>x[0]),x:us.map(x=>x[1][1]),
     marker:{color:C.orange},hovertemplate:'%{y}<br>Part-time %{x:,}<extra></extra>'}],
    L({barmode:'stack',showlegend:true,
      legend:{orientation:'h',y:1.10,x:0,font:{family:FONT,size:12}},
      margin:{l:200,r:40,t:40,b:42},
      xaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Employee records'},
      yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);

  // Median by EEO, FT vs PT side by side
  const eg={};
  idx.forEach(i=>{const k=D.eeos[D.eeo[i]];(eg[k]=eg[k]||{f:[],p:[]})[D.ft[i]?'f':'p'].push(D.sal[i]);});
  const ek=Object.keys(eg).sort((a,b2)=>med(eg[a].f.length?eg[a].f:eg[a].p)
    -med(eg[b2].f.length?eg[b2].f:eg[b2].p));
  Plotly.react('pEeo',[
    {type:'bar',orientation:'h',name:'Full-time',y:ek,x:ek.map(k=>eg[k].f.length?med(eg[k].f):null),
     marker:{color:C.blue},hovertemplate:'%{y}<br>Full-time median %{x:$,.0f}<extra></extra>'},
    {type:'bar',orientation:'h',name:'Part-time',y:ek,x:ek.map(k=>eg[k].p.length?med(eg[k].p):null),
     marker:{color:C.orange},hovertemplate:'%{y}<br>Part-time median %{x:$,.0f}<extra></extra>'}],
    L({barmode:'group',bargap:.28,bargroupgap:.06,showlegend:true,
      legend:{orientation:'h',y:1.10,x:0,font:{family:FONT,size:12}},
      margin:{l:195,r:40,t:40,b:42},
      xaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Median annual salary'},
      yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);

  // Bands, stacked FT/PT
  const bf=BANDS.map(([lo,hi])=>ftSal.filter(v=>v>=lo&&v<hi).length);
  const bp=BANDS.map(([lo,hi])=>ptSal.filter(v=>v>=lo&&v<hi).length);
  Plotly.react('pBand',[
    {type:'bar',name:'Full-time',x:BANDS.map(x=>x[2]),y:bf,marker:{color:C.blue},
     hovertemplate:'%{x}<br>Full-time %{y:,}<extra></extra>'},
    {type:'bar',name:'Part-time',x:BANDS.map(x=>x[2]),y:bp,marker:{color:C.orange},
     hovertemplate:'%{x}<br>Part-time %{y:,}<extra></extra>'}],
    L({barmode:'stack',showlegend:true,
      legend:{orientation:'h',y:1.14,x:0,font:{family:FONT,size:12}},
      margin:{l:60,r:20,t:44,b:72},
      xaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,tickangle:-40},
      yaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Employee records'}}),CFG);

  // Top roles
  const top=[...idx].sort((a,b2)=>D.sal[b2]-D.sal[a]).slice(0,10).reverse();
  Plotly.react('pTop',[{type:'bar',orientation:'h',
    y:top.map(i=>{const t=D.titles[D.title[i]];return t.length>40?t.slice(0,40)+'…':t;}),
    x:top.map(i=>D.sal[i]),marker:{color:top.map(i=>D.ft[i]?C.blue:C.orange)},
    text:top.map(i=>usdC(D.sal[i])),textposition:'outside',
    textfont:{family:FONT,color:C.ink2,size:11},cliponaxis:false,
    customdata:top.map(i=>D.units[D.unit[i]]),
    hovertemplate:'%{y}<br>%{customdata}<br>%{x:$,.0f}<extra></extra>'}],
    L({margin:{l:235,r:70,t:20,b:42},
      xaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Annual base salary'},
      yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);
}

function update(){const idx=filtered();tiles(idx);draw(idx);}
['fYear','fUnit','fEeo','fTime','fRes'].forEach(id=>
  document.getElementById(id).addEventListener('change',update));
document.getElementById('reset').addEventListener('click',()=>{
  fYear.value=D.years.length-1;fUnit.value=-1;fEeo.value=-1;fTime.value=-1;fRes.value=-1;update();});
document.getElementById('pdf').addEventListener('click',()=>window.print());

/* ---------------- Story ---------------- */
const H=(id,s)=>document.getElementById(id).innerHTML=s;
const cmp=ST.comparison;
const cur=ST.per_year[ST.latest];

// Chapter 1 -- growth
if(cmp){
  const h=cmp.headline;
  H('c1h',`The payroll grew by ${usdC(h.payroll.delta)} in a single year`);
  H('c1body',`
   <p>Between <strong>${cmp.prev}</strong> and <strong>${cmp.curr}</strong> the university
      added <strong>${num(h.records.delta)}</strong> employee records
      (${sgn(h.records.pct)}) and <strong>${usdC(h.payroll.delta)}</strong> of base salary
      (${sgn(h.payroll.pct)}). Payroll grew faster than headcount, which means the
      average record also got more expensive &mdash; not just that there are more of them.</p>
   <div class="pull"><b>${usdC(ST.per_year[cmp.curr].payroll)}</b> in total base salary across
      ${num(ST.per_year[cmp.curr].records)} records &mdash; up from
      ${usdC(ST.per_year[cmp.prev].payroll)}.</div>
   <p>The median salary moved ${sgn(h.median.pct)} and the full-time median
      ${sgn(h.median_ft.pct)}. Chapter six separates how much of that is real pay
      movement and how much is simply a changing mix of jobs.</p>`);
  H('c1legend',`<span class="item"><span class="swatch sw-prev"></span> ${cmp.prev}</span>
    <span class="item"><span class="swatch sw-curr"></span> ${cmp.curr}</span>`);

  const yrs=ST.years;
  Plotly.react('pYoYTotals',[
    {type:'bar',name:'Records',x:yrs,y:yrs.map(y=>ST.per_year[y].records),
     marker:{color:yrs.map(y=>y===cmp.curr?C.blue:C.prev)},
     text:yrs.map(y=>num(ST.per_year[y].records)),textposition:'outside',
     textfont:{family:FONT,size:12,color:C.ink2},cliponaxis:false,
     hovertemplate:'%{x}<br>%{y:,} records<extra></extra>'}],
    L({title:TITLE('Employee records by year'),margin:{l:70,r:20,t:44,b:42},
      yaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Records',
        range:[0,Math.max(...yrs.map(y=>ST.per_year[y].records))*1.16]},
      xaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis}}),CFG);

  const bu=cmp.by_unit.slice(0,10).sort((a,b2)=>a.n_delta-b2.n_delta);
  Plotly.react('pYoYUnit',[{type:'bar',orientation:'h',y:bu.map(r=>r.unit),
    x:bu.map(r=>r.n_delta),
    marker:{color:bu.map(r=>r.n_delta>=0?C.blue:C.orange)},
    text:bu.map(r=>(r.n_delta>=0?'+':'')+num(r.n_delta)),textposition:'outside',
    textfont:{family:FONT,size:11,color:C.ink2},cliponaxis:false,
    hovertemplate:'%{y}<br>change %{x:+,}<extra></extra>'}],
    L({title:TITLE('Headcount change by unit'),margin:{l:200,r:60,t:44,b:42},
      xaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Change in records',zeroline:true,
        zerolinecolor:C.axis,zerolinewidth:1.5},
      yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);
} else {
  H('c1h','A single year of data');
  H('c1body','<p>Only one salary year has been extracted, so no year-over-year comparison is available.</p>');
}

// Chapter 2 -- average vs typical
const dist=ST.distribution, ov=ST.overview;
H('c2h','The average salary describes almost nobody');
H('c2body',`
  <p>The mean salary is <strong>${usd(dist.all.mean)}</strong>. The median &mdash; the
     actual middle of the workforce &mdash; is <strong>${usd(dist.all.median)}</strong>.
     The ${usd(dist.mean_median_gap)} gap exists because a small number of very large
     salaries pull the average upward.</p>
  <p>There is a second distortion underneath it.
     <strong>${num(ov.part_time_records)}</strong> records
     (${pc(ov.part_time_share,0)}) are part-time, and because the source reports
     FTE-adjusted pay, a half-time employee shows half a salary. Pooling them with
     full-time staff drags every average down. Separating the two gives a full-time
     median of <strong>${usd(dist.full_time.median)}</strong>.</p>
  <div class="pull">Three defensible answers to "what does a UK employee earn":
     <b>${usd(dist.all.mean)}</b>, <b>${usd(dist.all.median)}</b>, or
     <b>${usd(dist.full_time.median)}</b>. Only the last one describes a typical
     full-time job.</div>`);

Plotly.react('pAvg',[{type:'bar',
  x:['Mean<br>(everyone)','Median<br>(everyone)','Median<br>(full-time)','Median<br>(part-time)'],
  y:[dist.all.mean,dist.all.median,dist.full_time.median,dist.part_time.median],
  marker:{color:[C.prev,C.prev,C.blue,C.orange]},
  text:[dist.all.mean,dist.all.median,dist.full_time.median,dist.part_time.median].map(usd),
  textposition:'outside',textfont:{family:FONT,size:12,color:C.ink},cliponaxis:false,
  hovertemplate:'%{x}<br>%{y:$,.0f}<extra></extra>'}],
  L({title:TITLE('Four ways to say "typical"'),margin:{l:70,r:20,t:44,b:56},
    yaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Annual salary',
      range:[0,dist.all.mean*1.30]},
    xaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis}}),CFG);

const lz=ST.concentration.lorenz;
Plotly.react('pLorenz',[
  {type:'scatter',mode:'lines',x:[0,1],y:[0,1],line:{color:C.axis,width:1.4},
   name:'Perfect equality',hoverinfo:'skip'},
  {type:'scatter',mode:'lines',x:lz.population_share,y:lz.payroll_share,
   line:{color:C.blue,width:2.4},fill:'tonexty',fillcolor:'rgba(27,82,196,.10)',
   name:'Actual',hovertemplate:'Lowest-paid %{x:.0%} of staff<br>hold %{y:.1%} of payroll<extra></extra>'}],
  L({title:TITLE(`Payroll concentration · Gini ${ST.concentration.gini_all.toFixed(3)}`),
    margin:{l:66,r:20,t:44,b:46},
    xaxis:{gridcolor:C.grid,linecolor:C.axis,tickformat:'.0%',title:'Share of employees'},
    yaxis:{gridcolor:C.grid,linecolor:C.axis,tickformat:'.0%',title:'Share of payroll'}}),CFG);

// Chapter 3 -- the health system
const u0=ST.by_unit[0];
H('c3h','This is a health system with a university attached');
H('c3body',`
  <p><strong>${u0.unit}</strong> alone accounts for <strong>${num(u0.headcount)}</strong>
     records &mdash; ${pc(u0.headcount_share,0)} of everyone on the payroll &mdash; and
     ${pc(u0.payroll_share,0)} of base salary. Add the College of Medicine and the
     clinical enterprise and the academic colleges become a minority of the institution
     by headcount.</p>
  <p>The gap between the two bars on the left is the interesting part: a unit whose
     payroll share sits below its headcount share employs a lot of people at
     comparatively modest salaries. Where payroll share runs ahead, the reverse is true.</p>
  <p>Part-time concentration varies enormously between units, which is why the
     chart on the right matters before comparing any two of them on pay.</p>`);

const bu2=ST.by_unit.slice(0,12).slice().reverse();
Plotly.react('pUnitShare',[
  {type:'bar',orientation:'h',name:'Share of headcount',y:bu2.map(r=>r.unit),
   x:bu2.map(r=>r.headcount_share),marker:{color:C.blue},
   hovertemplate:'%{y}<br>headcount %{x:.1%}<extra></extra>'},
  {type:'bar',orientation:'h',name:'Share of payroll',y:bu2.map(r=>r.unit),
   x:bu2.map(r=>r.payroll_share),marker:{color:C.aqua},
   hovertemplate:'%{y}<br>payroll %{x:.1%}<extra></extra>'}],
  L({barmode:'group',bargap:.3,showlegend:true,
    legend:{orientation:'h',y:1.09,x:0,font:{family:FONT,size:12}},
    title:TITLE('Headcount share vs payroll share'),margin:{l:200,r:40,t:62,b:42},
    xaxis:{gridcolor:C.grid,linecolor:C.axis,tickformat:'.0%',title:'Share of university total'},
    yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);

const bpt=ST.by_unit.slice(0,12).slice().sort((a,b2)=>a.part_time_share-b2.part_time_share);
Plotly.react('pUnitPT',[{type:'bar',orientation:'h',y:bpt.map(r=>r.unit),
  x:bpt.map(r=>r.part_time_share),marker:{color:C.orange},
  text:bpt.map(r=>pc(r.part_time_share,0)),textposition:'outside',
  textfont:{family:FONT,size:11,color:C.ink2},cliponaxis:false,
  hovertemplate:'%{y}<br>part-time %{x:.1%}<extra></extra>'}],
  L({title:TITLE('Part-time share of each unit'),margin:{l:200,r:60,t:44,b:42},
    xaxis:{gridcolor:C.grid,linecolor:C.axis,tickformat:'.0%',title:'Part-time share',
      range:[0,Math.max(...bpt.map(r=>r.part_time_share))*1.22]},
    yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);

// Chapter 4 -- research
const R=ST.research, P=R.postdoc;
H('c4h','The research mission runs on the lowest-paid scientists on campus');
H('c4body',`
  <p>Roles coded to research &mdash; postdocs, research scientists and support staff,
     clinical research, and research administration &mdash; account for
     <strong>${num(R.records)}</strong> records, ${pc(R.share_of_headcount,1)} of headcount
     and ${pc(R.share_of_payroll,1)} of payroll, with a median of
     <strong>${usd(R.median)}</strong>.</p>
  <p>Postdoctoral researchers are the sharpest case. There are
     <strong>${num(P.count)}</strong> of them, with a median of
     <strong>${usd(P.median)}</strong>. The NIH sets an entry-level stipend of
     <strong>${usd(P.nih_entry_stipend)}</strong> as the standard external floor for
     postdoctoral pay.</p>
  <div class="pull"><b>${pc(P.share_ft_below_nih_entry,0)}</b> of full-time postdocs at UK
     &mdash; ${num(P.count_ft_below_nih_entry)} people &mdash; earn less than the NIH
     entry-level stipend.</div>
  <p>These are the people who run the experiments the research enterprise is measured on.
     Base salary excludes fellowships and supplements, so some of this gap is closed by
     income the database does not record &mdash; but the base figure is what the
     institution itself commits to.</p>`);

const rc=R.by_category.slice().sort((a,b2)=>a.headcount-b2.headcount);
Plotly.react('pResCat',[{type:'bar',orientation:'h',y:rc.map(r=>r.research_category),
  x:rc.map(r=>r.headcount),marker:{color:C.blue},
  text:rc.map(r=>num(r.headcount)+'  ·  med '+usdC(r.median)),textposition:'outside',
  textfont:{family:FONT,size:11,color:C.ink2},cliponaxis:false,
  customdata:rc.map(r=>r.median),
  hovertemplate:'%{y}<br>%{x:,} records<br>median %{customdata:$,.0f}<extra></extra>'}],
  L({title:TITLE('Research workforce by role'),margin:{l:175,r:130,t:44,b:42},
    xaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Employee records',
      range:[0,Math.max(...rc.map(r=>r.headcount))*1.5]},
    yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);

const pdYears=ST.years.filter(y=>ST.per_year[y].postdoc_median);
Plotly.react('pPostdoc',[
  {type:'bar',x:pdYears,y:pdYears.map(y=>ST.per_year[y].postdoc_median),
   marker:{color:pdYears.map(y=>y===ST.latest?C.blue:C.prev)},width:.5,
   text:pdYears.map(y=>usd(ST.per_year[y].postdoc_median)),textposition:'outside',
   textfont:{family:FONT,size:12,color:C.ink},cliponaxis:false,
   name:'UK postdoc median',hovertemplate:'%{x}<br>median %{y:$,.0f}<extra></extra>'}],
  L({title:TITLE('UK postdoc median vs NIH entry stipend'),margin:{l:70,r:20,t:44,b:42},
    yaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Annual salary',
      range:[0,P.nih_entry_stipend*1.42]},
    xaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis},
    shapes:[{type:'line',xref:'paper',x0:0,x1:1,y0:P.nih_entry_stipend,y1:P.nih_entry_stipend,
      line:{color:C.orange,width:2.4,dash:'dash'}}],
    annotations:[{xref:'paper',x:1,y:P.nih_entry_stipend,text:'NIH entry stipend '+usd(P.nih_entry_stipend),
      showarrow:false,yanchor:'bottom',xanchor:'right',
      font:{family:FONT,color:C.orange,size:11.5}}]}),CFG);

// Chapter 5 -- ladder and floor
const F=ST.faculty, fl=ST.floor;
const t40=fl.thresholds['40000'];
H('c5h','A steep ladder at the top, a wide floor at the bottom');
H('c5body',`
  <p>Among full-time faculty, a full professor's median is
     <strong>${(F.professor_to_assistant_ratio||0).toFixed(2)}x</strong> an assistant
     professor's. But that single number hides how differently the ladder is built in
     each college &mdash; the lines on the left rarely run parallel.</p>
  <p>At the other end, <strong>${num(t40.count)}</strong> full-time employees
     (${pc(t40.share,1)} of the full-time workforce) earn under $40,000. These are
     full-year, full-time salaries, so the FTE effect does not explain them.</p>
  <p>The chart on the right shows departments where the 90th percentile earner makes
     many times the 10th &mdash; usually clinical or academic units where trainees,
     support staff and senior faculty all share one department code.</p>`);

const ranks=['Assistant Professor','Associate Professor','Professor'];
const palette=[C.blue,C.orange,C.aqua,'#eda100','#4a3aa7','#e87ba4','#e34948','#898781'];
Plotly.react('pLadder',F.ladder_by_college.map((r,i)=>({
  type:'scatter',mode:'lines+markers',name:r.unit,
  x:ranks,y:ranks.map(k=>r[k]),line:{color:palette[i%palette.length],width:2.2},
  marker:{size:8},hovertemplate:'%{fullData.name}<br>%{x}<br>median %{y:$,.0f}<extra></extra>'})),
  L({title:TITLE('Median pay across the tenure-track ladder'),showlegend:true,
    legend:{orientation:'h',y:-0.24,x:0,font:{family:FONT,size:10.5}},
    margin:{l:70,r:26,t:44,b:96},
    yaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Median salary'},
    xaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis}}),CFG);

const dsp=ST.dispersion.slice().reverse();
Plotly.react('pDisp',[
  {type:'scatter',mode:'markers',name:'10th percentile',y:dsp.map(r=>r.department),
   x:dsp.map(r=>r.p10),marker:{color:C.blue,size:11},
   hovertemplate:'%{y}<br>p10 %{x:$,.0f}<extra></extra>'},
  {type:'scatter',mode:'markers',name:'90th percentile',y:dsp.map(r=>r.department),
   x:dsp.map(r=>r.p90),marker:{color:C.orange,size:11},
   hovertemplate:'%{y}<br>p90 %{x:$,.0f}<extra></extra>'}],
  L({title:TITLE('Widest internal pay range, full-time staff'),showlegend:true,
    legend:{orientation:'h',y:1.09,x:0,font:{family:FONT,size:11.5}},
    margin:{l:210,r:40,t:62,b:42},
    xaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Annual salary'},
    yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true},
    shapes:dsp.map((r,i)=>({type:'line',y0:i,y1:i,x0:r.p10,x1:r.p90,layer:'below',
      line:{color:'#d8d7d0',width:5}}))}),CFG);

// Chapter 6 -- what actually changed
if(cmp){
  const mt=cmp.matched_titles;
  H('c6h','Most of the pay rise is real — but not all of it');
  H('c6body',`
    <p>A rising median does not prove anyone got a raise: it also rises when the
       university hires more well-paid roles and fewer low-paid ones. To separate the
       two, this compares <strong>the same job title in both years</strong> &mdash;
       ${num(mt.titles_compared)} titles with at least ${mt.min_per_year} people in each
       year.</p>
    <p>Across those matched titles the median change was
       <strong>${sgn(mt.median_of_median_pct)}</strong>, and
       <strong>${pc(mt.share_with_increase,0)}</strong> of them rose. That is genuine pay
       movement rather than a composition effect &mdash; though
       ${pc(mt.share_flat_or_down,0)} of titles were flat or down.</p>
    <div class="pull">Headline median moved <b>${sgn(cmp.headline.median.pct)}</b>.
       Like-for-like across matched job titles: <b>${sgn(mt.median_of_median_pct)}</b>.</div>
    <p>The low-pay floor moved too: full-time staff under $40,000 went from
       ${num(cmp.floor['40000'].prev)} to <strong>${num(cmp.floor['40000'].curr)}</strong>
       (${pc(cmp.floor['40000'].prev_share,1)} &rarr; ${pc(cmp.floor['40000'].curr_share,1)}
       of the full-time workforce).</p>`);

  const gains=mt.biggest_gains.slice(0,10).slice().reverse();
  Plotly.react('pTitleGain',[{type:'bar',orientation:'h',
    y:gains.map(r=>{const t=r.job_title;return t.length>36?t.slice(0,36)+'…':t;}),
    x:gains.map(r=>r.med_pct),marker:{color:C.blue},
    text:gains.map(r=>sgn(r.med_pct,1)),textposition:'outside',
    textfont:{family:FONT,size:11,color:C.ink2},cliponaxis:false,
    customdata:gains.map(r=>[r.n_curr,r.med_prev,r.med_curr]),
    hovertemplate:'%{y}<br>%{customdata[0]:,} people<br>'+
      '%{customdata[1]:$,.0f} → %{customdata[2]:$,.0f}<extra></extra>'}],
    L({title:TITLE(`Largest median gains, matched job titles (${cmp.prev} → ${cmp.curr})`),
      margin:{l:215,r:66,t:44,b:44},
      xaxis:{gridcolor:C.grid,linecolor:C.axis,tickformat:'+.0%',title:'Change in median pay',
        range:[0,Math.max(...gains.map(r=>r.med_pct))*1.22]},
      yaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis,automargin:true}}),CFG);

  const th=['40000','50000'];
  Plotly.react('pFloor',[
    {type:'bar',name:cmp.prev,x:th.map(t=>'Under $'+(+t/1000)+'k'),
     y:th.map(t=>cmp.floor[t].prev),marker:{color:C.prev},
     text:th.map(t=>num(cmp.floor[t].prev)),textposition:'outside',
     textfont:{family:FONT,size:11,color:C.ink2},cliponaxis:false,
     hovertemplate:cmp.prev+'<br>%{x}<br>%{y:,} full-time<extra></extra>'},
    {type:'bar',name:cmp.curr,x:th.map(t=>'Under $'+(+t/1000)+'k'),
     y:th.map(t=>cmp.floor[t].curr),marker:{color:C.blue},
     text:th.map(t=>num(cmp.floor[t].curr)),textposition:'outside',
     textfont:{family:FONT,size:11,color:C.ink},cliponaxis:false,
     hovertemplate:cmp.curr+'<br>%{x}<br>%{y:,} full-time<extra></extra>'}],
    L({barmode:'group',showlegend:true,
      legend:{orientation:'h',y:1.12,x:0,font:{family:FONT,size:12}},
      title:TITLE('Full-time employees below a pay threshold'),
      margin:{l:70,r:20,t:62,b:44},
      yaxis:{gridcolor:C.grid,linecolor:C.axis,title:'Full-time employees',
        range:[0,Math.max(...th.map(t=>Math.max(cmp.floor[t].prev,cmp.floor[t].curr)))*1.2]},
      xaxis:{gridcolor:'rgba(0,0,0,0)',linecolor:C.axis}}),CFG);
} else {
  H('c6h','Year-over-year comparison unavailable');
  H('c6body','<p>Only one salary year has been extracted.</p>');
}

/* ---------------- Data notes ---------------- */
(function(){
  const yrs=Object.keys(Q.missing_by_year||{}).sort();
  const cols=new Set();
  yrs.forEach(y=>Object.keys(Q.missing_by_year[y].columns).forEach(c=>cols.add(c)));
  const rows=[...cols].map(c=>{
    const cells=yrs.map(y=>{
      const v=Q.missing_by_year[y].columns[c];
      return v&&v.empty ? `<td class="num">${num(v.empty)}</td>`
                        : `<td class="num ok">none</td>`;});
    return `<tr><td>${c}</td>${cells.join('')}</tr>`;});
  const anyMissing=[...cols].some(c=>yrs.some(y=>{
    const v=Q.missing_by_year[y].columns[c];return v&&v.empty;}));
  H('dqMissing',
    `<table class="dq"><thead><tr><th>Field</th>${yrs.map(y=>`<th style="text-align:right">${y}</th>`).join('')}</tr></thead>`+
    `<tbody>${rows.join('')}</tbody></table>`+
    (anyMissing
      ? `<p style="font-size:13px;color:#52514e;margin-top:12px">Counts are records
           published with an empty value. Where a field is empty it is labelled
           <span class="badge">Not reported</span> in the data and shown as its own
           category &mdash; never silently dropped.</p>`
      : `<p style="font-size:13px;color:#52514e;margin-top:12px">
           <span class="ok">Every analysed field is populated in every record, in both years.</span>
           Academic rank is the one field the source leaves blank, and it does so by
           design &mdash; see the panel to the right.</p>`));

  const rs=Q.rank_status_by_year||{};
  const keys=new Set();Object.values(rs).forEach(o=>Object.keys(o).forEach(k=>keys.add(k)));
  H('dqRank',
    `<table class="dq"><thead><tr><th>Rank status</th>${yrs.map(y=>`<th style="text-align:right">${y}</th>`).join('')}</tr></thead><tbody>`+
    [...keys].map(k=>`<tr><td>${k}</td>${yrs.map(y=>`<td class="num">${num((rs[y]||{})[k]||0)}</td>`).join('')}</tr>`).join('')+
    `</tbody></table>
     <p style="font-size:13px;color:#52514e;margin-top:12px">
       <strong>Not applicable</strong> &mdash; the role has no academic rank (a nurse, a
       custodian, an analyst). The source is correct to leave it blank.<br>
       <strong>Not reported</strong> &mdash; a faculty record with no rank published.
       That is a genuine gap.</p>`);

  const ap=Q.appointments||{};
  const latest=yrs[yrs.length-1];
  const a=ap[latest]||{};
  H('dqLimits',`
    <ul style="margin:6px 0 0;padding-left:20px;color:#52514e">
      <li><strong>Base salary only.</strong> Excludes benefits, bonuses, clinical
          incentive pay, shift differentials, overtime and athletics supplements.
          Total compensation is higher, materially so at the top.</li>
      <li><strong>FTE-adjusted.</strong> Part-time figures reflect appointment fraction,
          not rate of pay. Every pay comparison here separates the two.</li>
      <li><strong>Records, not people.</strong> In ${latest},
          ${num(a.names_on_more_than_one_record||0)} name combinations appear on more than
          one record out of ${num(a.distinct_name_combinations||0)} distinct combinations.
          Common names collide, so this is an approximation and no exact person count is
          claimed.</li>
      <li><strong>No demographic data.</strong> The source contains no gender, race or age
          fields, and none are inferred from names &mdash; that would not support
          defensible conclusions.</li>
      <li><strong>Research roles are classified heuristically</strong> from job titles and
          departments. UK publishes no research-workforce flag.</li>
      <li><strong>Year-over-year change is measured on records, not individuals.</strong>
          There is no employee identifier, so matched job titles are used as the
          composition control.</li>
    </ul>`);
})();

update();
</script></body></html>
"""


if __name__ == "__main__":
    main()
