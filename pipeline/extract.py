"""Ottawa Global Benchmark Engine — extractor.

Reads pipeline/indicators.yaml, pulls every `status: confirmed` (city, indicator)
cell from its live source, harmonizes into one long/tidy table, validates, and
writes dashboard/public/data/global_cities.parquet.

Run: python pipeline/extract.py
"""

import io
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "pipeline" / "indicators.yaml"
OUTPUT_PATH = ROOT / "dashboard" / "public" / "data" / "global_cities.parquet"

STATCAN_WDS_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
ABS_DATA_URL = "https://data.api.abs.gov.au/rest/data"
PXWEB_BASE_URL = "https://pxdata.stat.fi/PXWeb/api/v1/en"

RETRIEVED_AT = datetime.now(timezone.utc).isoformat()


# ── Fetchers ──────────────────────────────────────────────────────────────
# Each returns a DataFrame with columns: ref_date (date), value (float)

def fetch_statcan_wds(vector_id: str, latest_n: int = 240) -> pd.DataFrame:
    numeric_id = int(vector_id.lstrip("vV"))
    resp = requests.post(
        STATCAN_WDS_URL,
        json=[{"vectorId": numeric_id, "latestN": latest_n}],
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()[0]
    if payload.get("status") != "SUCCESS":
        raise RuntimeError(f"StatCan WDS error for {vector_id}: {payload}")
    points = payload["object"]["vectorDataPoint"]
    return pd.DataFrame(
        {
            "ref_date": [pd.to_datetime(p["refPer"]) for p in points],
            "value": [p["value"] for p in points],
        }
    )


def fetch_fred(series_id: str) -> pd.DataFrame:
    resp = requests.get(FRED_CSV_URL, params={"id": series_id}, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    value_col = series_id
    df = df.rename(columns={"observation_date": "ref_date", value_col: "value"})
    df["ref_date"] = pd.to_datetime(df["ref_date"], format="%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"])[["ref_date", "value"]]


def fetch_abs_sdmx(series_id: str) -> pd.DataFrame:
    dataflow, key = series_id.split("/", 1)
    url = f"{ABS_DATA_URL}/{dataflow}/{key}"
    resp = requests.get(url, params={"format": "csv", "startPeriod": "2010"}, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    if df.empty:
        raise RuntimeError(f"ABS SDMX returned no rows for {series_id}")
    df = df.rename(columns={"TIME_PERIOD": "ref_date", "OBS_VALUE": "value"})
    df["ref_date"] = pd.to_datetime(df["ref_date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"])[["ref_date", "value"]].sort_values("ref_date")


def fetch_pxweb(series_id: str) -> pd.DataFrame:
    table_path, _, query_str = series_id.partition("?")
    params = dict(p.split("=") for p in query_str.split("&") if p)
    meta_url = f"{PXWEB_BASE_URL}/{table_path}"
    meta = requests.get(meta_url, timeout=30).json()

    time_code = next(v["code"] for v in meta["variables"] if v.get("time"))
    region_code = next(v["code"] for v in meta["variables"] if "alue" in v["code"])
    content_code = "contentscode"
    other_codes = [
        v["code"] for v in meta["variables"]
        if v["code"] not in (time_code, region_code, content_code)
    ]

    query = {
        "query": [
            {"code": time_code, "selection": {"filter": "all", "values": ["*"]}},
            {"code": region_code, "selection": {"filter": "item", "values": [params["region"]]}},
            {"code": content_code, "selection": {"filter": "item", "values": [params["content"]]}},
            # Any other dimension (e.g. sex) — select the "total" aggregate, PxWeb convention "SSS".
            *[{"code": c, "selection": {"filter": "item", "values": ["SSS"]}} for c in other_codes],
        ],
        "response": {"format": "json-stat2"},
    }
    resp = requests.post(meta_url, json=query, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    time_dim = data["dimension"][time_code]["category"]["index"]
    values = data["value"]
    rows = sorted(time_dim.items(), key=lambda kv: kv[1])
    ref_dates, vals = [], []
    for label, idx in rows:
        ref_dates.append(_parse_pxweb_period(label))
        vals.append(values[idx])
    df = pd.DataFrame({"ref_date": ref_dates, "value": vals})
    return df.dropna(subset=["value"])


def _parse_pxweb_period(label: str) -> pd.Timestamp:
    if "M" in label:
        return pd.to_datetime(label.replace("M", "-") + "-01")
    if "Q" in label:
        year, q = label.split("Q")
        return pd.Timestamp(int(year), (int(q) - 1) * 3 + 1, 1)
    return pd.to_datetime(f"{label}-01-01")


FETCHERS = {
    "statcan_wds": fetch_statcan_wds,
    "fred": fetch_fred,
    "abs_sdmx": fetch_abs_sdmx,
    "pxweb": fetch_pxweb,
}


# ── Extraction ────────────────────────────────────────────────────────────

def resolve_cell(city: str, indicator_id: str, cell: dict) -> pd.DataFrame:
    fetcher = FETCHERS[cell["source"]]
    if cell.get("derived"):
        num = fetcher(cell["derived_from"]["numerator_series_id"])
        den = fetcher(cell["derived_from"]["denominator_series_id"])
        merged = num.merge(den, on="ref_date", suffixes=("_num", "_den"))
        merged["value"] = merged["value_num"] / merged["value_den"] * 100
        df = merged[["ref_date", "value"]]
    else:
        df = fetcher(cell["source_series_id"])

    df = df.copy()
    df["city"] = city
    df["indicator"] = indicator_id
    df["unit"] = cell.get("unit")
    df["source"] = cell["source"]
    df["source_series_id"] = str(cell.get("source_series_id"))
    df["geo_note"] = cell.get("geo_note", "")
    df["retrieved_at"] = RETRIEVED_AT
    return df


def run_extraction(manifest: dict) -> pd.DataFrame:
    frames = []
    skipped = []
    for indicator in manifest["indicators"]:
        indicator_id = indicator["id"]
        unit = indicator.get("unit")
        for city, cell in indicator.get("cities", {}).items():
            cell = {**cell, "unit": cell.get("unit", unit)}
            if cell.get("status") != "confirmed":
                skipped.append(f"{city}/{indicator_id} (status={cell.get('status')})")
                continue
            try:
                frames.append(resolve_cell(city, indicator_id, cell))
                print(f"  ok    {city}/{indicator_id}")
            except Exception as exc:  # noqa: BLE001 — one bad cell shouldn't kill the run
                print(f"  FAILED {city}/{indicator_id}: {exc}")
                skipped.append(f"{city}/{indicator_id} (fetch error: {exc})")

    if skipped:
        print(f"\nSkipped {len(skipped)} cell(s):")
        for s in skipped:
            print(f"  - {s}")

    if not frames:
        raise RuntimeError("No data extracted — every cell failed or was skipped.")

    return pd.concat(frames, ignore_index=True)


def validate(df: pd.DataFrame) -> None:
    if df.empty:
        raise RuntimeError("Validation failed: extracted dataframe is empty.")

    counts = df.groupby(["city", "indicator"]).size()
    if (counts == 0).any():
        raise RuntimeError(f"Validation failed: empty (city, indicator) group(s):\n{counts[counts == 0]}")

    percent_rows = df[df["unit"] == "percent"]
    out_of_range = percent_rows[(percent_rows["value"] < 0) | (percent_rows["value"] > 100)]
    if not out_of_range.empty:
        raise RuntimeError(f"Validation failed: percent values out of [0, 100]:\n{out_of_range}")

    if df["ref_date"].isna().any():
        raise RuntimeError("Validation failed: null ref_date values present.")

    print(f"\nValidation passed: {len(df)} rows across {len(counts)} (city, indicator) pairs.")


def main() -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))

    print("Extracting...")
    df = run_extraction(manifest)
    df["ref_date"] = pd.to_datetime(df["ref_date"]).dt.date
    df = df.sort_values(["city", "indicator", "ref_date"]).reset_index(drop=True)

    validate(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    old_bytes = OUTPUT_PATH.read_bytes() if OUTPUT_PATH.exists() else None

    con = duckdb.connect()
    con.register("df", df)
    con.execute(f"COPY df TO '{OUTPUT_PATH.as_posix()}' (FORMAT PARQUET, COMPRESSION SNAPPY)")

    new_bytes = OUTPUT_PATH.read_bytes()
    if old_bytes == new_bytes:
        print(f"\n{OUTPUT_PATH} unchanged (byte-identical) — nothing new to commit.")
    else:
        size_kb = len(new_bytes) / 1024
        print(f"\nWrote {OUTPUT_PATH} ({size_kb:.1f} KB).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
