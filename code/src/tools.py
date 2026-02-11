from __future__ import annotations
import re
import pandas as pd
import numpy as np
from typing import Any

def read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

def basic_profile(df: pd.DataFrame, sample_n: int = 5) -> dict[str, Any]:
    miss = (df.isna().mean() * 100).round(2).to_dict()
    return {
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "missing_pct": {k: float(v) for k, v in miss.items()},
        "n_unique": {c: int(df[c].nunique(dropna=True)) for c in df.columns},
        "sample_rows": df.head(sample_n).to_dict(orient="records"),
    }

def _mask_value(value: Any) -> str:
    raw = str(value)
    if "@" in raw:
        name, domain = raw.split("@", 1)
        if len(name) <= 2:
            masked_name = "*" * len(name)
        else:
            masked_name = f"{name[0]}{'*' * (len(name) - 2)}{name[-1]}"
        return f"{masked_name}@{domain}"
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 6:
        return "***" + digits[-2:]
    if len(raw) <= 4:
        return "*" * len(raw)
    return f"{raw[0]}{'*' * (len(raw) - 2)}{raw[-1]}"

def _safe_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)

def _detect_date_columns(df: pd.DataFrame, sample_n: int = 50) -> list[str]:
    date_cols = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
            continue
        sample = df[col].dropna().astype(str).head(sample_n)
        if sample.empty:
            continue
        with pd.option_context("mode.chained_assignment", None):
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.8:
            date_cols.append(col)
    return date_cols

def advanced_profile(df: pd.DataFrame, sample_n: int = 5) -> dict[str, Any]:
    profile = basic_profile(df, sample_n=sample_n)

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    numeric_stats: dict[str, dict[str, Any]] = {}
    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        numeric_stats[col] = {
            "mean": _safe_float(series.mean()),
            "std": _safe_float(series.std()),
            "min": _safe_float(series.min()),
            "max": _safe_float(series.max()),
            "skew": _safe_float(series.skew()),
            "kurtosis": _safe_float(series.kurt()),
            "zero_pct": _safe_float((series == 0).mean() * 100),
            "negative_pct": _safe_float((series < 0).mean() * 100),
        }

    cardinality: dict[str, Any] = {"per_column": {}, "low": [], "medium": [], "high": []}
    rows = max(int(df.shape[0]), 1)
    for col in df.columns:
        n_unique = int(df[col].nunique(dropna=True))
        ratio = n_unique / rows
        if n_unique <= 10:
            bucket = "low"
        elif n_unique <= 50:
            bucket = "medium"
        else:
            bucket = "high"
        cardinality["per_column"][col] = {"n_unique": n_unique, "ratio": round(ratio, 4), "bucket": bucket}
        cardinality[bucket].append(col)

    date_ranges: dict[str, dict[str, Any]] = {}
    for col in _detect_date_columns(df):
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.notna().any():
            date_ranges[col] = {
                "min": parsed.min().isoformat(),
                "max": parsed.max().isoformat(),
                "missing_pct": float(parsed.isna().mean() * 100),
            }

    profile["numeric_stats"] = numeric_stats
    profile["cardinality"] = cardinality
    profile["date_ranges"] = date_ranges
    return profile

def detect_data_quality_issues(df: pd.DataFrame) -> dict[str, Any]:
    """Detect duplicates, outliers, missing values with concrete examples."""
    issues = {
        "duplicates": {"count": 0, "examples": []},
        "outliers": {"count": 0, "examples": []},
        "missing": {"count": 0, "examples": []},
    }
    
    # Duplicates
    dup_mask = df.duplicated(keep=False)
    dup_count = dup_mask.sum()
    if dup_count > 0:
        issues["duplicates"]["count"] = int(dup_count)
        issues["duplicates"]["examples"] = df[dup_mask].head(3).to_dict(orient="records")
    
    # Missing values (show rows with most missing)
    missing_per_row = df.isna().sum(axis=1)
    rows_with_missing = (missing_per_row > 0).sum()
    if rows_with_missing > 0:
        issues["missing"]["count"] = int(rows_with_missing)
        worst_rows = df[missing_per_row > 0].head(3)
        issues["missing"]["examples"] = worst_rows.to_dict(orient="records")
    
    # Outliers (numeric columns using IQR method)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    outlier_rows = set()
    outlier_details = []
    
    for col in numeric_cols:
        if df[col].nunique() > 10:  # Skip low-cardinality numeric
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 3 * IQR
            upper = Q3 + 3 * IQR
            outlier_mask = (df[col] < lower) | (df[col] > upper)
            
            if outlier_mask.any():
                outlier_indices = df[outlier_mask].index.tolist()
                outlier_rows.update(outlier_indices[:3])
                outlier_details.append({
                    "column": col,
                    "count": int(outlier_mask.sum()),
                    "range": f"{lower:.2f} to {upper:.2f}",
                })
    
    if outlier_rows:
        issues["outliers"]["count"] = len(outlier_rows)
        issues["outliers"]["examples"] = df.loc[list(outlier_rows)[:3]].to_dict(orient="records")
        issues["outliers"]["details"] = outlier_details
    
    return issues

def detect_pii_columns(df: pd.DataFrame, patterns: list[str]) -> list[dict[str, Any]]:
    pats = [p.lower() for p in patterns]
    flagged: list[dict[str, Any]] = []
    value_patterns = {
        "email": re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
        "phone": re.compile(r"\+?\d[\d\s().-]{7,}\d"),
        "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "ip": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    }

    for col in df.columns:
        col_lower = col.lower()
        name_matches = [p for p in pats if p in col_lower]
        sample = df[col].dropna().astype(str).head(50)
        value_hits: dict[str, int] = {}
        for label, regex in value_patterns.items():
            if sample.empty:
                continue
            count = int(sample.str.contains(regex).sum())
            if count:
                value_hits[label] = count

        if name_matches or value_hits:
            masked_samples = [_mask_value(v) for v in sample.head(3)]
            flagged.append(
                {
                    "column": col,
                    "name_matches": name_matches,
                    "value_matches": value_hits,
                    "sample_values": masked_samples,
                }
            )

    return flagged
