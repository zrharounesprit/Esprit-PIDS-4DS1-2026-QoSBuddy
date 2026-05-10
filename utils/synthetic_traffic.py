# ─────────────────────────────────────────────────────────────────────────────
# utils/synthetic_traffic.py — Synthetic CESNET Hourly Traffic Generator
#
# Produces realistic 18-column CESNET-format rows that exactly match the
# schema expected by the SLA preprocessing pipeline:
#   id_time, n_flows, n_packets, n_bytes,
#   sum_n_dest_asn, average_n_dest_asn, std_n_dest_asn,
#   sum_n_dest_ports, average_n_dest_ports, std_n_dest_ports,
#   sum_n_dest_ip, average_n_dest_ip, std_n_dest_ip,
#   tcp_udp_ratio_packets, tcp_udp_ratio_bytes,
#   dir_ratio_packets, dir_ratio_bytes,
#   avg_duration, avg_ttl
#
# DESIGN PRINCIPLE:
#   - Base means from real CESNET data (0.csv, 6717 rows)
#   - Std REDUCED to CV≈0.15 within a single 48h window so that normal
#     traffic stays below the SLA threshold (n_bytes_peak_ratio < ~1.3)
#   - Breach injection spikes the tail rows by 5-7× so peak_ratio → 5-7×
#   - inject_scenario reduces ONLY the spike rows (above 75th percentile)
#     so peak_ratio drops even though the baseline 24h mean is unchanged
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import math
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
import pandas as pd

# ── Base means from real CESNET data ─────────────────────────────────────────
_MEANS = {
    "n_flows":             221_728,
    "n_packets":          48_073_793,
    "n_bytes":        48_533_282_860,
    "sum_n_dest_asn":          280,
    "average_n_dest_asn":     14.5,
    "std_n_dest_asn":          6.8,
    "sum_n_dest_ports":      2_800,
    "average_n_dest_ports":   22.0,
    "std_n_dest_ports":       12.0,
    "sum_n_dest_ip":       3_200_000,
    "average_n_dest_ip":       420,
    "std_n_dest_ip":           185,
    "tcp_udp_ratio_packets":  0.710,
    "tcp_udp_ratio_bytes":    0.705,
    "dir_ratio_packets":      0.420,
    "dir_ratio_bytes":        0.415,
    "avg_duration":           23.92,
    "avg_ttl":               135.39,
}

# Coefficient of variation per column group
# LOW CV (≈0.12) for count columns so that within a 48h window the
# rolling 24h mean stays close to the current value → peak_ratio rarely > 1.3
_CV_COUNTS  = 0.07   # n_flows, n_packets, n_bytes, sum_* — tight so peak_ratio stays < 1.3 normally
_CV_AVG     = 0.05   # average_n_dest_*, avg_duration, avg_ttl
_CV_STD_    = 0.08   # std_n_dest_* columns
_CV_RATIO   = 0.025  # ratio columns (tightly distributed in real data)

def _cv(col: str) -> float:
    if col.startswith("average_") or col in ("avg_duration", "avg_ttl"):
        return _CV_AVG
    if col.startswith("std_"):
        return _CV_STD_
    if "ratio" in col:
        return _CV_RATIO
    return _CV_COUNTS

# Hourly traffic multipliers (index = hour 0–23)
# Range kept tight (0.88–1.12) so that peak_ratio stays below the SLA threshold
# in normal conditions. The diurnal shape is preserved but amplitude is limited.
_HOUR_MULT = np.array([
    0.88, 0.87, 0.87, 0.88, 0.89, 0.91,   # 00–05
    0.93, 0.96, 0.99, 1.03, 1.06, 1.07,   # 06–11
    1.05, 1.03, 1.05, 1.07, 1.09, 1.08,   # 12–17
    1.05, 1.03, 1.00, 0.97, 0.94, 0.91,   # 18–23
])

_WEEKEND_MULT = 0.93  # mild reduction — less variation

_COUNT_COLS  = ("n_flows", "n_packets", "n_bytes",
                "sum_n_dest_asn", "sum_n_dest_ports", "sum_n_dest_ip")
_RATIO_COLS  = ("tcp_udp_ratio_packets", "tcp_udp_ratio_bytes",
                "dir_ratio_packets", "dir_ratio_bytes")


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _sample_row(
    hour: int,
    is_weekend: bool,
    rng: np.random.Generator,
    breach: bool = False,
    breach_factor: float = 5.5,
) -> dict:
    """Sample one hourly CESNET row."""
    tmult = _HOUR_MULT[hour % 24]
    if is_weekend:
        tmult *= _WEEKEND_MULT

    row: dict = {}
    for col, base_mean in _MEANS.items():
        mean = base_mean * tmult
        cv   = _cv(col)
        std  = mean * cv

        if col in _COUNT_COLS:
            # Lognormal with small sigma → tight distribution
            sigma = math.sqrt(math.log(1 + cv ** 2))
            mu    = math.log(mean) - sigma ** 2 / 2
            val   = float(rng.lognormal(mu, sigma))
        elif col in _RATIO_COLS:
            val = float(rng.normal(mean, std))
        else:
            val = float(rng.normal(mean, std))
            val = max(0.01, val)

        row[col] = val

    # Clamp ratios
    for c in _RATIO_COLS:
        row[c] = _clamp(row[c], 0.05, 0.95)
    row["avg_ttl"]      = _clamp(row["avg_ttl"],      30.0, 255.0)
    row["avg_duration"] = max(0.1, row["avg_duration"])

    # Inject breach: spike n_bytes + correlated cols on the designated rows
    if breach:
        row["n_bytes"]   *= breach_factor
        row["n_packets"] *= (breach_factor ** 0.65)
        row["n_flows"]   *= (breach_factor ** 0.40)

    # Round count columns
    for c in _COUNT_COLS:
        row[c] = max(1, int(row[c]))

    return row


def generate_traffic_window(
    n_rows: int = 48,
    inject_breach: bool = False,
    breach_start_offset: int = -6,  # last 6 rows breach by default
    breach_factor: float = 5.5,
    anchor_dt: Optional[datetime] = None,
    seed: Optional[int] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate `n_rows` consecutive hourly synthetic traffic rows.

    The first (n_rows − 6) rows are "normal" traffic.
    When inject_breach=True, the last 6 rows spike n_bytes by breach_factor.
    The 24h rolling window will see stable baseline → peak_ratio will be high
    only in those spike rows → XGBoost reliably detects the breach.

    Returns:
        data_df   — CESNET traffic rows (id_time + 18 feature columns)
        times_df  — id_time ↔ datetime mapping (mirrors times_1_hour.csv format)
    """
    rng = np.random.default_rng(seed)

    if anchor_dt is None:
        anchor_dt = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
    start_dt = anchor_dt - timedelta(hours=n_rows - 1)

    breach_start_row = (
        n_rows + breach_start_offset if breach_start_offset < 0 else breach_start_offset
    )

    rows, times_rows = [], []
    for i in range(n_rows):
        dt = start_dt + timedelta(hours=i)
        is_breach_row = inject_breach and i >= breach_start_row
        bf = breach_factor + rng.uniform(-0.5, 0.8)  # slight randomness
        row = _sample_row(
            hour=dt.hour,
            is_weekend=dt.weekday() >= 5,
            rng=rng,
            breach=is_breach_row,
            breach_factor=bf,
        )
        row["id_time"] = i
        rows.append(row)
        times_rows.append({"id_time": i, "time": dt.isoformat()})

    # Canonical column order
    cols = [
        "id_time", "n_flows", "n_packets", "n_bytes",
        "sum_n_dest_asn", "average_n_dest_asn", "std_n_dest_asn",
        "sum_n_dest_ports", "average_n_dest_ports", "std_n_dest_ports",
        "sum_n_dest_ip", "average_n_dest_ip", "std_n_dest_ip",
        "tcp_udp_ratio_packets", "tcp_udp_ratio_bytes",
        "dir_ratio_packets", "dir_ratio_bytes",
        "avg_duration", "avg_ttl",
    ]
    data_df  = pd.DataFrame(rows)[[c for c in cols if c in pd.DataFrame(rows).columns]]
    times_df = pd.DataFrame(times_rows)
    return data_df, times_df


def inject_scenario(
    data_df: pd.DataFrame,
    scenario: str = "capacity_increase",
    factor: float = 0.55,
) -> pd.DataFrame:
    """
    Apply a mitigation scenario for the VERIFY/SIMULATE phases.

    Key insight: to reduce n_bytes_peak_ratio (current / 24h_rolling_mean),
    we must reduce the HIGH rows more than the baseline rows.
    Scaling all rows uniformly keeps the ratio unchanged.

    Scenarios:
      capacity_increase — cap rows above 75th percentile to 75th × factor
      qos_throttle      — hard cap on rows above 80th percentile to that value
      rate_limit        — collapse variance: pull all rows toward the window mean
    """
    df = data_df.copy()

    for col in ("n_bytes", "n_packets", "n_flows"):
        if col not in df.columns:
            continue

        if scenario == "capacity_increase":
            # Reduce the spike rows proportionally more than the baseline
            p75 = df[col].quantile(0.75)
            mask = df[col] > p75
            df.loc[mask, col] = (df.loc[mask, col] * factor).astype(int)

        elif scenario == "qos_throttle":
            # Hard cap: anything above 80th percentile gets capped
            cap = df[col].quantile(0.80)
            df[col] = df[col].clip(upper=cap).astype(int)

        elif scenario == "rate_limit":
            # Pull everything toward the mean: halve the deviation from mean
            mean_val = df[col].mean()
            df[col] = (mean_val + (df[col] - mean_val) * 0.35).astype(int)
            df[col] = df[col].clip(lower=1)

    return df
