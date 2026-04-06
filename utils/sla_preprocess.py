# ─────────────────────────────────────────────────────────────────────────────
# sla_preprocess.py — CESNET hourly prep (same idea as sub548weeks40 notebook)
#
# Training: data.merge(times_df, on="id_time"), then datetime from merged time column.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import pandas as pd


def df_has_resolvable_clock(df: pd.DataFrame) -> bool:
    """True if API/engineering can get a real clock without times merge."""
    for c in ("datetime", "timestamp", "time"):
        if c not in df.columns:
            continue
        parsed = pd.to_datetime(df[c], errors="coerce")
        if parsed.notna().any():
            return True
    return False


def merge_cesnet_times_1h(data: pd.DataFrame, times_df: pd.DataFrame) -> pd.DataFrame:
    """
    Mirror notebook: merge subnet hourly rows with times_1_hour.csv on id_time,
    then build datetime from the first merged column whose name contains 'time'
    (excluding id_time).
    """
    if "id_time" not in data.columns:
        raise ValueError("Subnet data must include `id_time` to merge with `times_1_hour.csv`.")
    if "id_time" not in times_df.columns:
        raise ValueError("Times table must include `id_time`.")

    merged = data.merge(times_df, on="id_time", how="left", suffixes=("", "_times"))
    time_cols = [c for c in merged.columns if "time" in c.lower() and c != "id_time"]
    if not time_cols:
        raise ValueError(
            "After merge, no clock column found. Expected a column containing 'time' in its name "
            "(from the times export), besides `id_time`."
        )
    time_col = time_cols[0]
    merged["datetime"] = pd.to_datetime(merged[time_col], errors="coerce")
    if merged["datetime"].isna().all():
        raise ValueError(f"Could not parse any valid timestamps from `{time_col}`.")

    return merged


def ensure_subnet_key(df: pd.DataFrame, subnet_id_fallback: str) -> pd.DataFrame:
    """Training uses subnet_id per series; add constant if single-file export has neither key."""
    out = df.copy()
    if "subnet_id" in out.columns or "id_ip" in out.columns:
        return out
    out["subnet_id"] = subnet_id_fallback
    return out
