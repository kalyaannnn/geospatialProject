"""
Urban Tree Health Explorer (NYC) — Streamlit entrypoint.

Run: streamlit run streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

# Ensure project root is importable when run from any cwd
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nyc_tree_explorer import data as data_mod
from nyc_tree_explorer import viz
from nyc_tree_explorer.config import CACHE_MAX_AGE_DAYS, MAP_DECK_HEIGHT_PX, MAX_SCATTER_POINTS
from nyc_tree_explorer.filters import HEALTH_LABELS, apply_filters, top_species_options

st.set_page_config(
    page_title="Urban Tree Health Explorer (NYC)",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Urban Tree Health Explorer (NYC)")
st.caption(
    "2015 NYC Street Tree Census — data from "
    "[NYC Open Data](https://data.cityofnewyork.us/Environment/"
    "2015-Street-Tree-Census-Tree-Data/uvpi-gqnh) (auto-cached locally)."
)


@st.cache_data(show_spinner=False)
def get_trees(force_download: bool = False):
    return data_mod.load_or_download(force_download=force_download)


# --- Sidebar: data refresh ---
with st.sidebar:
    st.header("Data")
    cache_age = data_mod.cache_age_days()
    if cache_age is not None:
        st.caption(f"Local cache age: **{cache_age:.1f}** days")
        if data_mod.cache_is_stale(CACHE_MAX_AGE_DAYS):
            st.warning(
                f"Cache is older than {CACHE_MAX_AGE_DAYS} days. "
                "Consider refreshing for the latest snapshot."
            )
    if st.button("Re-download from API", type="secondary"):
        with st.spinner("Downloading full census from NYC Open Data…"):
            df_new = data_mod.download_trees()
            data_mod.save_cache(df_new)
        get_trees.clear()
        st.success("Cache updated.")
        st.rerun()

if not data_mod.cache_exists():
    with st.spinner("Loading tree census (first run downloads from the API)…"):
        df_full = get_trees(force_download=False)
else:
    df_full = get_trees(force_download=False)

# --- Sidebar: filters ---
with st.sidebar:
    st.header("Filters")
    boroughs_all = sorted(df_full["boroname"].dropna().unique())
    borough_pick = st.multiselect(
        "Borough",
        options=boroughs_all,
        default=boroughs_all,
    )
    health_pick = st.multiselect(
        "Health",
        options=list(HEALTH_LABELS),
        default=list(HEALTH_LABELS),
    )
    top_opts = top_species_options(df_full, n=60)
    species_pick = st.multiselect(
        "Species (common name, top 60 by volume)",
        options=top_opts,
        default=top_opts,
        help=(
            "Options are the 60 most common species citywide. "
            "With all selected, no species filter is applied (entire filtered borough/health set)."
        ),
    )

    st.subheader("Map layers")
    show_scatter = st.toggle("Scatter layer (health colors)", value=True)
    show_heat = st.toggle("Heatmap (density)", value=True)
    heat_radius = st.slider("Heatmap radius (px)", 10, 60, 28)

    st.subheader("Scatter sample")
    max_pts = st.number_input(
        "Max scatter points",
        min_value=5_000,
        max_value=120_000,
        value=min(MAX_SCATTER_POINTS, 60_000),
        step=5_000,
        help="Random sample for performance; heatmap uses all filtered rows.",
    )

# Resolve filters: “all selected” → no narrowing on that axis
borough_filter = borough_pick if len(borough_pick) < len(boroughs_all) else None
if borough_filter is not None and len(borough_filter) == 0:
    st.error("Select at least one borough.")
    st.stop()

health_filter = health_pick if len(health_pick) < len(HEALTH_LABELS) else None
if health_filter is not None and len(health_filter) == 0:
    st.error("Select at least one health category.")
    st.stop()

species_filter = species_pick if len(species_pick) < len(top_opts) else None
if species_filter is not None and len(species_filter) == 0:
    st.error("Select at least one species, or restore the full list to clear the filter.")
    st.stop()

df = apply_filters(
    df_full,
    boroughs=borough_filter,
    health_selection=health_filter,
    species_selection=species_filter,
)

# KPIs
kpis = viz.compute_kpis(df)
c1, c2, c3 = st.columns(3)
c1.metric("Total trees (filtered)", f"{kpis['total_trees']:,}")
if kpis["pct_good"] is not None:
    c2.metric(
        'Share rated "Good"',
        f"{kpis['pct_good']:.1f}%",
        help="Among trees with a health rating (Good / Fair / Poor).",
    )
else:
    c2.metric('Share rated "Good"', "—")
c3.metric(
    "Most common species",
    kpis["top_species"] or "—",
)

st.divider()

# Map + charts
left, right = st.columns((1.55, 1.0), gap="large")

with left:
    st.subheader("Map")
    if df.empty:
        st.info("No trees match the current filters.")
    elif not show_scatter and not show_heat:
        st.warning("Enable at least one map layer in the sidebar.")
    else:
        df_heat = df
        df_scatter = viz.prepare_map_data(df, max_scatter=int(max_pts))
        deck = viz.build_deck(
            df_scatter,
            df_heat,
            show_scatter=show_scatter,
            show_heatmap=show_heat,
            heatmap_radius=int(heat_radius),
        )
        st.pydeck_chart(
            deck,
            width="stretch",
            height=MAP_DECK_HEIGHT_PX,
        )
        st.caption(
            "Green = Good · Amber = Fair · Red = Poor · Gray = not rated / other. "
            "Heatmap uses up to 120k points so the map stays responsive."
        )

with right:
    st.subheader("Distribution")
    if not df.empty:
        fig_b = viz.figure_borough_counts(df)
        st.pyplot(fig_b, use_container_width=True)
        plt.close(fig_b)

        fig_s = viz.figure_species_top(df)
        st.pyplot(fig_s, use_container_width=True)
        plt.close(fig_s)

summary = data_mod.get_data_summary(df_full)
st.divider()
st.caption(
    f"Full dataset rows: **{summary['rows']:,}** · "
    f"Cache: `{summary['cached_path']}` · "
    f"Downloaded (UTC): **{summary.get('downloaded_at_utc') or 'unknown'}**"
)
