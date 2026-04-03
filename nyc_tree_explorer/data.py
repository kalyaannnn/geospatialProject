"""Download, normalize, and cache NYC Street Tree Census data."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

from nyc_tree_explorer.config import (
    CACHE_DIR,
    CACHE_FILENAME,
    CACHE_MAX_AGE_DAYS,
    DATASET_ID,
    METADATA_FILENAME,
    PAGE_SIZE,
    PROJECT_ROOT,
    REQUEST_TIMEOUT_S,
    SOCRATA_BASE,
)

ProgressCallback = Callable[[int, int], None]


def _cache_parquet_path() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / CACHE_FILENAME


def _metadata_path() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / METADATA_FILENAME


def _write_metadata(row_count: int, source_url: str) -> None:
    meta = {
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": row_count,
        "dataset_id": DATASET_ID,
        "source": source_url,
    }
    _metadata_path().write_text(json.dumps(meta, indent=2), encoding="utf-8")


def cache_exists() -> bool:
    return _cache_parquet_path().is_file()


def cache_age_days() -> float | None:
    if not cache_exists():
        return None
    age_s = time.time() - _cache_parquet_path().stat().st_mtime
    return age_s / 86400.0


def cache_is_stale(max_age_days: float = CACHE_MAX_AGE_DAYS) -> bool:
    age = cache_age_days()
    if age is None:
        return True
    return age > max_age_days


def _fetch_page(offset: int, limit: int) -> list[dict]:
    url = f"{SOCRATA_BASE}/{DATASET_ID}.json"
    params = {"$limit": limit, "$offset": offset, "$order": "tree_id"}
    resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


def download_trees(
    progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """
    Paginate through the Socrata API and return the full census as a DataFrame.
    """
    rows: list[dict] = []
    offset = 0
    source_url = f"{SOCRATA_BASE}/{DATASET_ID}.json"

    while True:
        batch = _fetch_page(offset, PAGE_SIZE)
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if progress:
            progress(len(rows), len(rows))  # total unknown until done; update below

        if len(batch) < PAGE_SIZE:
            break

    df = pd.DataFrame(rows)
    if progress:
        progress(len(df), len(df))

    return _normalize_frame(df)


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce types, drop unusable coordinates, standardize text fields."""
    if df.empty:
        return df

    for col in ("latitude", "longitude"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["boroname"] = df["boroname"].fillna("Unknown").astype(str).str.strip()
    df["spc_common"] = (
        df["spc_common"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "(unspecified)")
    )

    # Valid map points only
    valid = df["latitude"].notna() & df["longitude"].notna()
    df = df.loc[valid].copy()

    return df


def save_cache(df: pd.DataFrame) -> Path:
    path = _cache_parquet_path()
    df.to_parquet(path, index=False, engine="pyarrow")
    _write_metadata(len(df), f"{SOCRATA_BASE}/{DATASET_ID}.json")
    return path


def load_cached() -> pd.DataFrame:
    path = _cache_parquet_path()
    return pd.read_parquet(path, engine="pyarrow")


def load_or_download(
    force_download: bool = False,
    progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """
    Return trees from local Parquet cache, or download from the API if missing
    or if ``force_download`` is True.
    """
    path = _cache_parquet_path()
    if path.is_file() and not force_download:
        return load_cached()

    df = download_trees(progress=progress)
    save_cache(df)
    return df


def get_data_summary(df: pd.DataFrame) -> dict:
    """Lightweight stats for UI footer / debugging."""
    meta_path = _metadata_path()
    downloaded = None
    if meta_path.is_file():
        try:
            downloaded = json.loads(meta_path.read_text(encoding="utf-8")).get(
                "downloaded_at_utc"
            )
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "rows": len(df),
        "cached_path": str(_cache_parquet_path()),
        "downloaded_at_utc": downloaded,
        "project_root": str(PROJECT_ROOT),
    }
