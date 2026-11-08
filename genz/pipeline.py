"""Download -> immutable raw bytes -> clean -> validate -> versioned dashboard tables.

CLI: python -m genz.pipeline [--offline] [--strict] [--data-dir PATH]
Refresh failures can reuse a verified raw cache; every such fallback is reported.
Processed tables become visible only after a complete build and atomic pointer switch.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import uuid

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xlrd

from .sources import SOURCES, Source

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data"


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_write(path: Path, payload: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def validate_payload(source: Source, payload: bytes):
    """Reject error/HTML responses before they can replace a good cached dataset."""
    if source.filename.endswith(".csv"):
        frame = pd.read_csv(BytesIO(payload))
        if frame.shape[1] != 2 or "observation_date" not in frame or len(frame) < 20:
            raise ValueError(f"Unexpected FRED schema: {source.key}")
        if frame.iloc[:, 1].name != source.filename.removesuffix(".csv"):
            raise ValueError(f"Wrong series returned for {source.key}")
    else:
        workbook = xlrd.open_workbook(file_contents=payload)
        if workbook.sheet_by_index(0).nrows < 20:
            raise ValueError(f"Incomplete Census workbook: {source.key}")


def fetch_source(source, raw_dir, previous, offline=False, strict=False):
    path = raw_dir / source.filename
    warning = None
    if not offline:
        try:
            session = requests.Session()
            retry = Retry(total=1, backoff_factor=.5, status_forcelist=(429, 500, 502, 503, 504))
            session.mount("https://", HTTPAdapter(max_retries=retry))
            response = session.get(source.url, timeout=(8, 25))
            response.raise_for_status()
            validate_payload(source, response.content)
            # Raw files are content-addressed; a later refresh never overwrites a
            # snapshot's source bytes, so every published run stays reproducible.
            sha = digest(response.content)
            raw_path = raw_dir / "objects" / f"{sha}{path.suffix}"
            if not raw_path.exists():
                atomic_write(raw_path, response.content)
            metadata = {**asdict(source), "sha256": sha, "bytes": len(response.content),
                        "raw_path": str(raw_path.relative_to(raw_dir.parent)).replace("\\", "/"),
                        "fetched_at": datetime.now(timezone.utc).isoformat(), "status": "downloaded"}
            return metadata, None
        except (requests.RequestException, ValueError, xlrd.XLRDError) as error:
            if strict:
                raise RuntimeError(f"{source.key}: download failed: {error}") from error
            warning = f"{source.key}: refresh failed; verified cached source used ({type(error).__name__})."
    if not previous:
        raise RuntimeError(f"{source.key}: no verified cache; run the pipeline online first.")
    cached_path = raw_dir.parent / previous["raw_path"]
    payload = cached_path.read_bytes()
    if digest(payload) != previous["sha256"]:
        raise ValueError(f"Raw cache checksum mismatch: {source.key}")
    validate_payload(source, payload)
    return {**previous, "status": "offline cache" if offline else "refresh fallback"}, warning


def clean_fred(payload: bytes, key: str):
    raw = pd.read_csv(BytesIO(payload), na_values=[".", "", "NA"])
    result = pd.DataFrame({"date": pd.to_datetime(raw.iloc[:, 0], errors="coerce"),
                           "value": pd.to_numeric(raw.iloc[:, 1], errors="coerce")})
    missing = int(result.isna().any(axis=1).sum())
    result = result.dropna().sort_values("date")
    duplicate_count = int(result.duplicated("date").sum())
    if duplicate_count:
        raise ValueError(f"Duplicate observation dates in {key}")
    if result.empty or not result.value.gt(0).all():
        raise ValueError(f"Nonpositive or empty economic series: {key}")
    result["series"] = key
    return result[["series", "date", "value"]], {"missing_rows_removed": missing, "duplicate_dates": duplicate_count}


def workbook_rows(payload):
    sheet = xlrd.open_workbook(file_contents=payload).sheet_by_index(0)
    return [sheet.row_values(index) for index in range(sheet.nrows)]


def parse_year(value):
    match = re.fullmatch(r"\.*\s*((?:18|19|20)\d{2})(?:\.0)?[a-z]?\s*", str(value), re.I)
    return int(match[1]) if match else None


def numeric(value):
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return float("nan")


def clean_marriage(payload):
    rows = workbook_rows(payload)
    if not any("Men's median age" in str(row) for row in rows[:12]):
        raise ValueError("MS-2 column heading changed; review parser before publishing.")
    records = []
    for row in rows:
        year = parse_year(row[0])
        if year is not None:
            for sex, column in (("Men", 1), ("Women", 2)):
                records.append({"year": year, "sex": sex, "median_age": numeric(row[column]), "source_row": str(row[0])})
    frame = pd.DataFrame(records)
    duplicates = int(frame.duplicated(["year", "sex"]).sum())
    # Publisher lists revised/control-adjusted alternatives first. Keep its first
    # row, retain the original row label, and report discarded alternatives.
    frame = frame.drop_duplicates(["year", "sex"], keep="first").sort_values(["year", "sex"])
    if len(frame) < 100 or not frame.median_age.between(15, 50).all():
        raise ValueError("Invalid MS-2 ages or insufficient historical coverage.")
    return frame, {"alternate_rows_removed": duplicates, "selection": "first publisher row per year and sex"}


def clean_living(payload, age_group):
    rows = workbook_rows(payload)
    headings = " ".join(str(row) for row in rows[:10])
    if not all(text in headings for text in ("Living with spouse", "Child of householder", "Living with partner")):
        raise ValueError("AD-3 headings changed; parser needs review.")
    metrics = {"living_alone_pct": 5, "living_with_spouse_pct": 7,
               "child_of_householder_pct": 9, "living_with_partner_pct": 11}
    records = []
    for row in rows:
        year = parse_year(row[0])
        if year is None:
            continue
        for offset, sex in ((0, "Men"), (1, "Women")):
            records.append({"year": year, "age_group": age_group, "sex": sex,
                            "population_thousands": numeric(row[1 + offset]), "source_row": str(row[0]),
                            **{metric: numeric(row[column + offset]) for metric, column in metrics.items()}})
    frame = pd.DataFrame(records)
    duplicates = int(frame.duplicated(["year", "sex"]).sum())
    frame = frame.drop_duplicates(["year", "sex"], keep="first")
    for column in metrics:
        # A few older partner observations are unavailable. Preserve those as
        # missing, never as zero. Observed percentages must be in [0,100].
        if not frame[column].dropna().between(0, 100).all():
            raise ValueError(f"Invalid AD-3 percentage: {column}")
    if not frame.population_thousands.gt(0).all():
        raise ValueError("Invalid age-group populations.")
    combined = []
    for year, subset in frame.groupby("year"):
        weights = subset.population_thousands
        values = {metric: (subset[metric] * weights).sum() / weights.sum()
                  if subset[metric].notna().all() else float("nan") for metric in metrics}
        combined.append({"year": year, "age_group": age_group, "sex": "All (weighted)",
                         "population_thousands": weights.sum(), "source_row": "population-weighted Men + Women", **values})
    return pd.concat([frame, pd.DataFrame(combined)], ignore_index=True).sort_values(["year", "sex"]), {"alternate_rows_removed": duplicates}


def annualize(observations, source, cutoff_year):
    selected = observations.loc[observations.series == source.key].copy()
    selected["year"] = selected.date.dt.year
    summary = selected.groupby("year").value.agg(["mean", "count"])
    complete = (summary["count"] >= source.minimum_observations) & (summary.index <= cutoff_year)
    return summary.loc[complete, "mean"].rename(source.key), summary.loc[~complete].reset_index().to_dict("records")


def run_pipeline(data_dir=DEFAULT_DATA, offline=False, strict=False):
    data_dir = Path(data_dir)
    raw_dir = data_dir / "raw"
    previous = read_json(raw_dir / "metadata.json", {})
    metadata, warnings = {}, []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch_source, source, raw_dir, previous.get(source.key), offline, strict): source for source in SOURCES}
        for future in as_completed(futures):
            source = futures[future]
            result, warning = future.result()
            metadata[source.key] = result
            if warning:
                warnings.append(warning)
            print(f"{source.key}: {result['status']}", flush=True)
    atomic_write(raw_dir / "metadata.json", json.dumps(metadata, indent=2).encode())
    observations, quality, living = [], {"warnings": sorted(warnings), "sources": {}}, []
    marriage = None
    for source in SOURCES:
        payload = (data_dir / metadata[source.key]["raw_path"]).read_bytes()
        if source.frequency in ("quarterly", "annual", "monthly", "weekly"):
            cleaned, report = clean_fred(payload, source.key)
            observations.append(cleaned)
            metadata[source.key]["coverage"] = {"first": str(cleaned.date.min().date()), "last": str(cleaned.date.max().date()), "rows": len(cleaned)}
        elif source.key == "marriage_age":
            marriage, report = clean_marriage(payload)
            metadata[source.key]["coverage"] = {"first": int(marriage.year.min()), "last": int(marriage.year.max()), "rows": len(marriage)}
        else:
            cleaned, report = clean_living(payload, source.key.removeprefix("living_"))
            living.append(cleaned)
            metadata[source.key]["coverage"] = {"first": int(cleaned.year.min()), "last": int(cleaned.year.max()), "rows": len(cleaned)}
        quality["sources"][source.key] = report
    observations = pd.concat(observations, ignore_index=True)
    cutoff = datetime.now(timezone.utc).year - 1
    columns = []
    for source in SOURCES:
        if source.key in observations.series.unique():
            annual, excluded = annualize(observations, source, cutoff)
            quality["sources"][source.key]["incomplete_or_current_years_excluded"] = excluded
            columns.append(annual)
    # Inner/common-complete years avoid comparing an annual income from one year
    # with a partial-year home price, rate or CPI from a different year.
    wide = pd.concat(columns, axis=1).dropna().reset_index()
    if len(wide) < 20 or wide.year.duplicated().any():
        raise ValueError("Insufficient unique common complete years.")
    wide["price_to_income"] = wide.home_price / wide.income
    living_frame = pd.concat(living, ignore_index=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    run_dir = data_dir / "processed" / "runs" / run_id
    run_dir.mkdir(parents=True)
    for name, frame in {"annual.csv": wide, "observations.csv": observations,
                        "marriage.csv": marriage, "living.csv": living_frame}.items():
        frame.to_csv(run_dir / name, index=False)
    manifest = {"schema_version": 1, "run_id": run_id, "built_at": datetime.now(timezone.utc).isoformat(),
                "geography": "United States", "common_years": [int(wide.year.min()), int(wide.year.max())],
                "marriage_latest": int(marriage.year.max()), "living_latest": int(living_frame.year.max()),
                "offline_build": offline, "sources": metadata,
                "artifacts": {p.name: digest(p.read_bytes()) for p in run_dir.glob("*.csv")}}
    (run_dir / "quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    atomic_write(data_dir / "processed" / "current.json", json.dumps({"run_id": run_id}).encode())
    return manifest


def load_snapshot(data_dir=DEFAULT_DATA):
    data_dir = Path(data_dir)
    pointer = read_json(data_dir / "processed" / "current.json")
    if not pointer or not re.fullmatch(r"[A-Za-z0-9-]+", pointer.get("run_id", "")):
        raise FileNotFoundError("No published snapshot. Run python -m genz.pipeline first.")
    folder = data_dir / "processed" / "runs" / pointer["run_id"]
    manifest = read_json(folder / "manifest.json")
    for name, expected in manifest["artifacts"].items():
        if digest((folder / name).read_bytes()) != expected:
            raise ValueError(f"Processed artifact checksum mismatch: {name}")
    return {"annual": pd.read_csv(folder / "annual.csv"), "marriage": pd.read_csv(folder / "marriage.csv"),
            "living": pd.read_csv(folder / "living.csv"), "observations": pd.read_csv(folder / "observations.csv"),
            "manifest": manifest, "quality": read_json(folder / "quality.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Rebuild from verified cached raw data only.")
    parser.add_argument("--strict", action="store_true", help="Fail rather than fall back to cached downloads.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    manifest = run_pipeline(args.data_dir, args.offline, args.strict)
    print(f"Published {manifest['run_id']}; common complete years {manifest['common_years']}")
