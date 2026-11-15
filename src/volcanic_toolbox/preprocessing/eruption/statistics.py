"""Descriptive statistics for candidate eruption samples."""

from __future__ import annotations
from typing import Iterable, Optional
import numpy as np
import pandas as pd


def summarize_samples(
    data: pd.DataFrame,
    columns: Optional[Iterable[str]] = None,
    quantiles=(0.05, 0.25, 0.50, 0.75, 0.95),
) -> pd.DataFrame:
    if data.empty:
        raise ValueError("data cannot be empty")
    selected = (
        list(data.select_dtypes(include=[np.number]).columns)
        if columns is None else list(columns)
    )
    rows = []
    for column in selected:
        values = pd.to_numeric(data[column], errors="coerce")
        valid = values.dropna()
        row = {
            "parameter": column,
            "count": int(valid.count()),
            "missing": int(values.isna().sum()),
            "mean": float(valid.mean()),
            "median": float(valid.median()),
            "std": float(valid.std(ddof=0)),
            "minimum": float(valid.min()),
            "maximum": float(valid.max()),
        }
        for q, value in valid.quantile(list(quantiles)).items():
            row["q%02d" % round(q * 100)] = float(value)
        rows.append(row)
    return pd.DataFrame(rows).set_index("parameter")
