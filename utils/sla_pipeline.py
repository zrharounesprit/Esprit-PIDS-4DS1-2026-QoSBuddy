# ─────────────────────────────────────────────────────────────────────────────
# sla_pipeline.py — CESNET SLA feature engineering (sub548weeks40 notebook logic)
#
# Run this in Streamlit (or any client) on raw merged hourly data BEFORE calling
# the SLA API. The API only scales + predict_proba(engineered rows).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import numpy as np
import pandas as pd

ROLLING_24_MINP = 6
ROLLING_6_MINP = 3


def _detect_group_col(df: pd.DataFrame) -> str:
    if "subnet_id" in df.columns:
        return "subnet_id"
    if "id_ip" in df.columns:
        return "id_ip"
    raise ValueError(
        "SLA feature engineering needs a series key: add column `subnet_id` or `id_ip`."
    )


def _ensure_datetime(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    if "datetime" in out.columns:
        out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    elif "timestamp" in out.columns:
        out["datetime"] = pd.to_datetime(out["timestamp"], errors="coerce")
    elif "time" in out.columns:
        out["datetime"] = pd.to_datetime(out["time"], errors="coerce")
    else:
        raise ValueError(
            "Need a time column: `datetime`, `timestamp`, or `time` (parsable by pandas)."
        )
    return out


def engineer_sla_features(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """
    Notebook-aligned engineering (per subnet_id / id_ip). Preserves __row_id if present.
    Output: rows with all feature_cols non-null; may be fewer rows than input (warmup/NaN).
    """
    data = df.copy()
    if "__row_id" not in data.columns:
        data = data.reset_index(drop=False).rename(columns={"index": "__row_id"})

    group_col = _detect_group_col(data)
    data = _ensure_datetime(data)
    data = data.sort_values([group_col, "datetime"]).reset_index(drop=True)

    data["hour"] = data["datetime"].dt.hour
    data["dayofweek"] = data["datetime"].dt.dayofweek
    data["is_weekend"] = (data["dayofweek"] >= 5).astype(int)
    data["is_business_hours"] = ((data["hour"] >= 8) & (data["hour"] <= 18)).astype(int)
    data["hour_sin"] = np.sin(2 * np.pi * data["hour"] / 24)
    data["hour_cos"] = np.cos(2 * np.pi * data["hour"] / 24)
    data["dow_sin"] = np.sin(2 * np.pi * data["dayofweek"] / 7)
    data["dow_cos"] = np.cos(2 * np.pi * data["dayofweek"] / 7)

    grouped = data.groupby(group_col)
    volume_cols = ["n_flows", "n_packets", "n_bytes"]
    for col in volume_cols:
        if col not in data.columns:
            raise ValueError(f"Missing required column `{col}` for SLA features.")

        data[f"{col}_mean_24h"] = grouped[col].transform(
            lambda x, w=ROLLING_24_MINP: x.rolling(24, min_periods=w).mean()
        )
        data[f"{col}_std_24h"] = grouped[col].transform(
            lambda x, w=ROLLING_24_MINP: x.rolling(24, min_periods=w).std()
        )
        data[f"{col}_mean_6h"] = grouped[col].transform(
            lambda x, w=ROLLING_6_MINP: x.rolling(6, min_periods=w).mean()
        )
        data[f"{col}_pct_change"] = grouped[col].transform(lambda x: x.pct_change())
        for lag in (1, 2, 3):
            data[f"{col}_lag_{lag}h"] = grouped[col].transform(
                lambda x, lg=lag: x.shift(lg)
            )

    ratio_cols = [
        c
        for c in data.columns
        if "ratio" in c.lower() and "rolling" not in c.lower() and "mean" not in c.lower()
    ]
    for col in ratio_cols:
        data[f"{col}_mean_24h"] = grouped[col].transform(
            lambda x, w=ROLLING_24_MINP: x.rolling(24, min_periods=w).mean()
        )

    for col in volume_cols:
        data[f"{col}_peak_ratio"] = data[col] / data[f"{col}_mean_24h"].replace(0, np.nan)

    if "avg_duration" in data.columns:
        data["avg_duration_mean_24h"] = grouped["avg_duration"].transform(
            lambda x, w=ROLLING_24_MINP: x.rolling(24, min_periods=w).mean()
        )

    data = data.replace([np.inf, -np.inf], np.nan)

    missing = [c for c in feature_cols if c not in data.columns]
    if missing:
        raise ValueError(
            f"After engineering, model features still missing: {missing}. "
            "CSV must include base CESNET-style columns used in training."
        )

    data = data.dropna(subset=feature_cols)
    return data
