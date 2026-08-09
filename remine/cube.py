"""Stage 3 — cube metadata and bulk data.

Per-vector fetching is not viable at this scale (the LFS cube alone is ~8,000
series), so the full-table CSV download is the access path. Downloads are cached
by (pid, release_time) so re-runs against an unchanged release cost nothing.
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

WDS = "https://www150.statcan.gc.ca/t1/wds/rest"
META_URL = f"{WDS}/getCubeMetadata"
CSV_URL = f"{WDS}/getFullTableDownloadCSV/{{pid}}/en"


@dataclass(frozen=True)
class Dimension:
    name: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class CubeMeta:
    pid: int
    title: str
    release_time: str
    frequency_code: int
    dimensions: tuple[Dimension, ...]

    def member_names(self) -> dict[str, tuple[str, ...]]:
        return {d.name: d.members for d in self.dimensions}


def parse_meta(payload: list[dict]) -> CubeMeta:
    entry = payload[0]
    if entry.get("status") != "SUCCESS":
        raise RuntimeError(f"WDS getCubeMetadata failed: {entry}")
    obj = entry["object"]
    dims = tuple(
        Dimension(
            name=d["dimensionNameEn"],
            members=tuple(m["memberNameEn"] for m in d["member"]),
        )
        for d in obj["dimension"]
    )
    return CubeMeta(
        pid=int(obj["productId"]),
        title=obj["cubeTitleEn"],
        release_time=obj.get("releaseTime", ""),
        frequency_code=int(obj.get("frequencyCode", 0)),
        dimensions=dims,
    )


def fetch_meta(pid: int) -> CubeMeta:
    resp = requests.post(META_URL, json=[{"productId": int(pid)}], timeout=30)
    resp.raise_for_status()
    return parse_meta(resp.json())


def download_cube(pid: int, release_time: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    stamp = release_time.replace(":", "").replace("-", "").replace("T", "")
    dest = cache_dir / f"{pid}-{stamp}.zip"
    if dest.exists():
        return dest
    envelope_resp = requests.get(CSV_URL.format(pid=pid), timeout=60)
    envelope_resp.raise_for_status()
    envelope = envelope_resp.json()
    if envelope.get("status") != "SUCCESS":
        raise RuntimeError(f"WDS full-table download failed for {pid}: {envelope}")
    with requests.get(envelope["object"], stream=True, timeout=600) as resp:
        resp.raise_for_status()
        tmp = dest.with_suffix(".part")
        with tmp.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        tmp.replace(dest)
    return dest


def load_cube(zip_path: Path, pid: int) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(f"{pid}.csv") as fh:
            df = pd.read_csv(fh, encoding="utf-8-sig", dtype=str, low_memory=False)
    df.columns = [c.lstrip("﻿") for c in df.columns]
    df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce")
    df["DECIMALS"] = pd.to_numeric(df["DECIMALS"], errors="coerce").fillna(0).astype(int)
    return df
