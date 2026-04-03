"""Application configuration and constants."""

from __future__ import annotations

from pathlib import Path

# NYC Open Data — 2015 Street Tree Census (Socrata API)
DATASET_ID = "uvpi-gqnh"
SOCRATA_BASE = "https://data.cityofnewyork.us/resource"
PAGE_SIZE = 50_000
REQUEST_TIMEOUT_S = 120

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
CACHE_FILENAME = "nyc_street_trees_2015.parquet"
METADATA_FILENAME = "nyc_street_trees_2015.meta.json"

# Cache policy: re-download if file older than this many days (when using TTL check)
CACHE_MAX_AGE_DAYS = 14

# Map / viz
NYC_CENTER = {"latitude": 40.7128, "longitude": -73.935242}
DEFAULT_MAP_ZOOM = 9
MAX_SCATTER_POINTS = 60_000
# Heatmap JSON must stay small enough for Streamlit’s pydeck embed (full wide rows × 600k+ points fails)
MAX_HEATMAP_POINTS = 120_000
MAP_DECK_HEIGHT_PX = 620
SPECIES_CHART_TOP_N = 12
RANDOM_SEED = 42

# Health → RGBA for pydeck (0–255)
HEALTH_COLORS: dict[str, tuple[int, int, int, int]] = {
    "Good": (34, 139, 34, 220),
    "Fair": (255, 185, 15, 220),
    "Poor": (220, 20, 60, 220),
}

UNKNOWN_HEALTH_COLOR = (128, 128, 128, 160)
