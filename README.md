# Gen Z Lens

A local data-engineering and Streamlit project exploring U.S. homeownership costs, living costs, inflation, income, first-marriage timing, and young-adult living arrangements across generations.

**Real public data is bundled. No Kaggle account, API key, fabricated sample data, or cloud deployment is needed.** The initial snapshot was downloaded from FRED and Census. The dashboard also works offline after its Python dependencies are installed.

## Start on Windows

Double-click **Start.bat**. It finds Python 3.11+, creates `.venv`, installs the pinned app dependencies, verifies that a snapshot exists, and opens Streamlit locally at **http://localhost:8501**. Keep the console open while using the dashboard. Stop it with Ctrl+C.

If Python is missing, install it from https://www.python.org/downloads/windows/ with the launcher enabled. The first dependency installation requires internet access.

Manual setup:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Dashboard

- **The big picture:** a selectable baseline/comparison year; home-price-to-income ratios; price, income, CPI and earnings indices; mortgage rates; latest individual observations.
- **Housing lab:** adjustable down payment, loan term, gross household income, property taxes, insurance, maintenance and PMI; historical cost breakdown and CSV export.
- **Cost of living:** rebased rent, grocery, energy, overall inflation and hourly-earnings series; nominal versus inflation-adjusted dollars.
- **Marriage & home:** national median age at first marriage and same-age comparisons of living with a spouse, living as a child of the householder, living with a partner, and living alone.
- **Data room:** observation coverage, fetch times, source URLs, hashes, cache/fallback status, cleaning rules, exclusions, quality report and cleaned-data downloads.

The initial common-complete economic window is **1984–2024**. Although individual sources have newer observations, the downloaded 2025 CPI-related series have only 11 valid monthly observations. The pipeline excludes that incomplete annual comparison rather than filling the missing month. Marriage ages extend through **2025**; the preserved age-specific AD-3 tables extend through **2023**. Refreshes can change coverage when providers publish or revise data.

## Refresh and rebuild

Use the sidebar's **Refresh public data**, double-click **Refresh data.bat**, or run:

```powershell
.\.venv\Scripts\python.exe -m genz.pipeline
.\.venv\Scripts\python.exe -m genz.pipeline --strict
.\.venv\Scripts\python.exe -m genz.pipeline --offline
```

Default online mode can fall back to a previously verified raw file if a source fails; this is recorded in the manifest and dashboard. `--strict` refuses fallbacks. `--offline` rebuilds from existing, checksum-verified raw files. No network access occurs merely by opening the dashboard. `--data-dir PATH` supports an independent data directory for pipeline experiments.

## Pipeline structure

```text
genz/sources.py        source URLs, units, frequency and completeness requirements
genz/pipeline.py       extraction, cleaning, validation and snapshot publication
genz/metrics.py        pure inflation and mortgage/scenario calculations
app.py                Streamlit dashboard and Plotly charts
tests/                calculations, cleaning, real-data and dashboard checks
data/raw/objects/     immutable SHA-256-addressed source CSV/XLS files
data/raw/metadata.json download manifest for future refresh/cache reuse
data/processed/runs/  versioned clean tables, provenance manifest and quality report
data/processed/current.json  atomically published active snapshot pointer
```

Old raw objects and processed runs are retained so an analysis remains reproducible. A source HTTP 200 containing an error page is rejected before caching. Network requests use bounded retries/timeouts. The current snapshot pointer is switched only after all transformations and validations succeed, so a failed build leaves the last published dashboard dataset available.

Cleaning parses dates and numbers, removes explicit missing economic observations, rejects duplicate dates/nonpositive values, enforces observation-count completeness, retains actual demographic observation years, and reports alternate Census revision rows discarded. Revised duplicates keep the first publisher-listed row, with original labels preserved. Read the source workbooks' footnotes before asserting fine-grained changes.

## Sources and interpretation

See [METHODOLOGY.md](METHODOLOGY.md) for formulas and limitations. Sources include [FRED](https://fred.stlouisfed.org/), [Census historical marital status](https://www.census.gov/data/tables/time-series/demo/families/marital.html), and [Census adult living arrangements](https://www.census.gov/data/tables/time-series/demo/families/adults.html). Per-series URLs and source attribution are bundled in each manifest.

National economic series cover all ages. They are context for Gen Z, not direct measurements of Gen Z income, purchases, or wealth. The direct young-adult evidence holds age bands constant across survey years. Living with a spouse is not identical to marital status. Mixed birth-year spans are labeled. These comparisons do not establish causal links between cost changes and relationship choices.

Census/BLS government source data and third-party series have their own source notes and reuse terms. In particular, Freddie Mac PMMS is a third-party series distributed through FRED. Check its [series notes](https://fred.stlouisfed.org/series/MORTGAGE30US) before redistribution; source attribution and raw provenance are retained here. No government or provider endorsement is implied.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m genz.pipeline --offline
```

Tests cover mortgage math (including zero interest), inflation/rebasing, missing/duplicate observations, incomplete-year rejection, revision parsing, birth-span labels, real snapshot integrity, population weighting, and Streamlit widget interactions. `requirements-lock.txt` records the full tested development environment; install that file for an exact version set.

Everything is local; no credentials, accounts, telemetry, database service, or GitHub connection is required. No repository is pushed automatically.
