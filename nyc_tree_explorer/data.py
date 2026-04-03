"""Download, normalize, and cache NYC Street Tree Census data."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd
import requests

from nyc_tree_explorer.config import (
    BULK_CSV_URL,
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

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


def _bulk_read_timeout_s() -> int:
    """Seconds for streaming the CSV body (env overrides Streamlit secrets if set first)."""
    return int(os.environ.get("NYC_TREE_BULK_TIMEOUT_S", "900"))


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


def data_source_mode() -> str:
    """bulk = single CSV export (default) | api = paginated Socrata JSON."""
    return os.environ.get("NYC_TREE_DATA_SOURCE", "bulk").strip().lower()


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


def download_trees_via_api(
    progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """Paginate through the Socrata JSON API (slow; use for fallback only)."""
    rows: list[dict] = []
    offset = 0

    while True:
        batch = _fetch_page(offset, PAGE_SIZE)
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if progress:
            progress(len(rows), len(rows))

        if len(batch) < PAGE_SIZE:
            break

    df = pd.DataFrame(rows)
    if progress:
        progress(len(df), len(df))

    return _normalize_frame(df)


def download_trees_bulk_csv() -> pd.DataFrame:
    """
    One HTTP download of the official CSV export (fast path for Streamlit Cloud).
    CSV column names differ slightly from the JSON API (e.g. ``borough`` vs ``boroname``).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / f".{DATASET_ID}_download.csv"
    try:
        with requests.get(
            BULK_CSV_URL,
            stream=True,
            timeout=(60, _bulk_read_timeout_s()),
        ) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=4 * 1024 * 1024):
                    if chunk:
                        f.write(chunk)
        df = pd.read_csv(tmp, low_memory=False)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    return _normalize_frame(df)


def _canonical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Align bulk CSV / API column names with what the app expects."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "borough" in df.columns and "boroname" not in df.columns:
        df = df.rename(columns={"borough": "boroname"})
    return df


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce types, drop unusable coordinates, standardize text fields."""
    if df.empty:
        return df

    df = _canonical_columns(df)

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


def save_cache(df: pd.DataFrame, source_url: str | None = None) -> Path:
    path = _cache_parquet_path()
    df.to_parquet(path, index=False, engine="pyarrow")
    src = source_url or f"{SOCRATA_BASE}/{DATASET_ID}.json"
    _write_metadata(len(df), src)
    return path


def load_cached() -> pd.DataFrame:
    path = _cache_parquet_path()
    return pd.read_parquet(path, engine="pyarrow")


def load_or_download(
    force_download: bool = False,
    progress: ProgressCallback | None = None,
) -> pd.DataFrame:
    """
    Return trees from local Parquet cache, or download.

    Default is **bulk CSV** (single stream). Set env ``NYC_TREE_DATA_SOURCE=api``
    to force paginated JSON, or use that as automatic fallback if CSV fails.
    """
    path = _cache_parquet_path()
    if path.is_file() and not force_download:
        return load_cached()

    mode = data_source_mode()
    api_url = f"{SOCRATA_BASE}/{DATASET_ID}.json"

    if mode == "api":
        df = download_trees_via_api(progress=progress)
        save_cache(df, source_url=api_url)
        return df

    try:
        df = download_trees_bulk_csv()
        save_cache(df, source_url=BULK_CSV_URL)
        return df
    except Exception as e:
        logger.warning("Bulk CSV download failed, using JSON API fallback: %s", e)
        df = download_trees_via_api(progress=progress)
        save_cache(df, source_url=api_url)
        return df


def download_trees(progress: ProgressCallback | None = None) -> pd.DataFrame:
    """Public download used by “Re-download” — respects ``NYC_TREE_DATA_SOURCE``."""
    mode = data_source_mode()
    if mode == "api":
        return download_trees_via_api(progress=progress)
    try:
        return download_trees_bulk_csv()
    except Exception as e:
        logger.warning("Bulk CSV failed in manual refresh: %s", e)
        return download_trees_via_api(progress=progress)


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
