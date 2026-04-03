"""Pydeck map layers and matplotlib charts for tree analytics."""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

# Consistent, readable charts in Streamlit
plt.rcParams.update(
    {
        "figure.facecolor": "#fafafa",
        "axes.facecolor": "#fafafa",
        "axes.grid": True,
        "grid.alpha": 0.28,
        "grid.linestyle": "--",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
    }
)
import pandas as pd
import pydeck as pdk

from nyc_tree_explorer.config import (
    DEFAULT_MAP_ZOOM,
    HEALTH_COLORS,
    MAX_HEATMAP_POINTS,
    MAX_SCATTER_POINTS,
    NYC_CENTER,
    RANDOM_SEED,
    SPECIES_CHART_TOP_N,
    UNKNOWN_HEALTH_COLOR,
)


def _health_rgba_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    def row_color(h: Any) -> tuple[int, int, int, int]:
        if pd.isna(h) or h is None:
            return UNKNOWN_HEALTH_COLOR
        key = str(h).strip()
        return HEALTH_COLORS.get(key, UNKNOWN_HEALTH_COLOR)

    colors = out["health"].map(row_color) if "health" in out.columns else [
        UNKNOWN_HEALTH_COLOR
    ] * len(out)
    if isinstance(colors, pd.Series):
        rgba = np.array(colors.tolist(), dtype=np.int32)
    else:
        rgba = np.tile(UNKNOWN_HEALTH_COLOR, (len(out), 1))

    out["fill_r"] = rgba[:, 0]
    out["fill_g"] = rgba[:, 1]
    out["fill_b"] = rgba[:, 2]
    out["fill_a"] = rgba[:, 3]
    return out


def prepare_map_data(
    df: pd.DataFrame,
    max_scatter: int = MAX_SCATTER_POINTS,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Sample for scatter performance; heatmap uses full filtered frame upstream."""
    if rng is None:
        rng = np.random.default_rng(RANDOM_SEED)

    base = _health_rgba_columns(df)
    if len(base) <= max_scatter:
        out = base
    else:
        out = base.sample(n=max_scatter, random_state=rng).reset_index(drop=True)
    # Smaller JSON + reliable deck.gl coords
    for col in ("latitude", "longitude"):
        if col in out.columns:
            out[col] = out[col].astype(np.float32)
    return out


def prepare_heatmap_points(
    df: pd.DataFrame,
    max_points: int = MAX_HEATMAP_POINTS,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """
    Only lat/lon for HeatmapLayer, capped and sampled for Streamlit/pydeck payload limits.
    Sending hundreds of thousands of wide rows breaks the browser embed.
    """
    if rng is None:
        rng = np.random.default_rng(RANDOM_SEED)
    if df.empty:
        return df
    pts = df[["latitude", "longitude"]].dropna().copy()
    pts["latitude"] = pts["latitude"].astype(np.float32)
    pts["longitude"] = pts["longitude"].astype(np.float32)
    if len(pts) <= max_points:
        return pts
    return pts.sample(n=max_points, random_state=rng).reset_index(drop=True)


def build_deck(
    df_scatter: pd.DataFrame,
    df_heatmap: pd.DataFrame,
    show_scatter: bool,
    show_heatmap: bool,
    heatmap_radius: int = 28,
) -> pdk.Deck:
    layers: list[pdk.Layer] = []

    if show_heatmap and not df_heatmap.empty:
        heat_pts = prepare_heatmap_points(df_heatmap)
        if not heat_pts.empty:
            layers.append(
                pdk.Layer(
                    "HeatmapLayer",
                    data=heat_pts,
                    get_position="[longitude, latitude]",
                    get_weight=1,
                    radius_pixels=heatmap_radius,
                    intensity=1,
                    threshold=0.03,
                )
            )

    if show_scatter and not df_scatter.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=df_scatter,
                get_position="[longitude, latitude]",
                get_fill_color="[fill_r, fill_g, fill_b, fill_a]",
                get_radius=12,
                radius_min_pixels=2,
                radius_max_pixels=24,
                pickable=True,
                auto_highlight=True,
            )
        )

    view = pdk.ViewState(
        latitude=NYC_CENTER["latitude"],
        longitude=NYC_CENTER["longitude"],
        zoom=DEFAULT_MAP_ZOOM,
        pitch=0,
        bearing=0,
    )

    tooltip = {
        "html": "<b>{spc_common}</b><br/>{boroname}<br/>Health: {health}<br/>",
        "style": {"backgroundColor": "#1e1e1e", "color": "white"},
    }

    # None = let Streamlit choose the basemap (matches app theme; avoids blank embeds
    # when a custom Carto URL fails inside the iframe). See st.pydeck_chart docs.
    return pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style=None,
        tooltip=tooltip if show_scatter else None,
    )


def figure_borough_counts(df: pd.DataFrame, figsize: tuple[float, float] = (6.2, 3.8)):
    """Horizontal bar chart of tree counts by borough."""
    if df.empty or "boroname" not in df.columns:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_axis_off()
        return fig

    counts = df["boroname"].value_counts().sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=figsize)
    counts.plot(kind="barh", ax=ax, color="#2e7d32", edgecolor="white")
    ax.set_xlabel("Tree count")
    ax.set_ylabel("")
    ax.set_title("Trees by borough")
    fig.tight_layout()
    return fig


def figure_species_top(
    df: pd.DataFrame,
    top_n: int = SPECIES_CHART_TOP_N,
    figsize: tuple[float, float] = (6.2, 4.2),
):
    """Bar chart of top species by count."""
    if df.empty or "spc_common" not in df.columns:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_axis_off()
        return fig

    counts = df["spc_common"].value_counts().head(top_n).sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=figsize)
    counts.plot(kind="barh", ax=ax, color="#1565c0", edgecolor="white")
    ax.set_xlabel("Tree count")
    ax.set_ylabel("")
    ax.set_title(f"Top {top_n} species (common name)")
    fig.tight_layout()
    return fig


def compute_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """KPI block for the dashboard."""
    n = len(df)
    if n == 0:
        return {
            "total_trees": 0,
            "pct_good": None,
            "top_species": None,
        }

    health_series = df["health"].dropna()
    rated = len(health_series)
    good = int((health_series == "Good").sum()) if rated else 0
    pct_good = (good / rated * 100.0) if rated else None

    species = df["spc_common"]
    top = species.mode().iloc[0] if not species.empty else None

    return {
        "total_trees": n,
        "pct_good": pct_good,
        "top_species": top,
        "rated_trees": rated,
    }
