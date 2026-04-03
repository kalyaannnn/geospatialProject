"""Filter helpers for the tree census DataFrame."""

from __future__ import annotations

import pandas as pd

HEALTH_LABELS = ("Good", "Fair", "Poor", "Not rated")


def health_to_display(series: pd.Series) -> pd.Series:
    return series.where(series.notna(), "Not rated")


def apply_filters(
    df: pd.DataFrame,
    boroughs: list[str] | None,
    health_selection: list[str] | None,
    species_selection: list[str] | None,
    *,
    top_species_limit: int = 60,
) -> pd.DataFrame:
    """
    Apply sidebar selections. Empty list for a dimension means **no filter**
    (all values). ``species_selection`` is matched against ``spc_common``;
    pass ``None`` to skip species filter.
    """
    out = df
    if boroughs is not None and len(boroughs) > 0:
        out = out[out["boroname"].isin(boroughs)]

    if health_selection is not None and len(health_selection) > 0:
        disp = health_to_display(out["health"]) if "health" in out.columns else None
        if disp is not None:
            mask = disp.isin(health_selection)
            out = out.loc[mask]

    if species_selection is not None and len(species_selection) > 0:
        out = out[out["spc_common"].isin(species_selection)]

    return out


def top_species_options(df: pd.DataFrame, n: int = 60) -> list[str]:
    """Common names of the top *n* species by frequency (for multiselect)."""
    if df.empty or "spc_common" not in df.columns:
        return []
    return df["spc_common"].value_counts().head(n).index.tolist()
