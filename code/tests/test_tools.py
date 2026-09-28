import pandas as pd
import pytest

from src.tools import (
    advanced_profile,
    basic_profile,
    detect_data_quality_issues,
    detect_pii_columns,
    target_relationships,
    top_correlations,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": range(1, 11),
            "distance_km": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
            "delivery_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "region": ["N", "S", "N", "S", "N", "S", "N", "S", "N", "S"],
            "late": [0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
        }
    )


def test_basic_profile_shape(sample_df):
    prof = basic_profile(sample_df)
    assert prof["rows"] == 10
    assert prof["cols"] == 5
    assert set(prof["columns"]) == set(sample_df.columns)
    assert prof["n_unique"]["region"] == 2


def test_advanced_profile_numeric_stats(sample_df):
    prof = advanced_profile(sample_df)
    assert "distance_km" in prof["numeric_stats"]
    stats = prof["numeric_stats"]["distance_km"]
    assert stats["min"] == 10
    assert stats["max"] == 100
    assert prof["cardinality"]["per_column"]["region"]["bucket"] == "low"


def test_top_correlations_detects_perfect_relationship(sample_df):
    corrs = top_correlations(sample_df, threshold=0.5)
    pair = next((c for c in corrs if {c["x"], c["y"]} == {"distance_km", "delivery_days"}), None)
    assert pair is not None
    assert pair["r"] == pytest.approx(1.0, abs=1e-6)


def test_top_correlations_respects_threshold():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 2, 3, 4], "c": [4, 1, 3, 2]})
    corrs = top_correlations(df, threshold=0.99)
    assert all(abs(c["r"]) >= 0.99 for c in corrs)


def test_target_relationships_binary_target(sample_df):
    rels = target_relationships(sample_df, target="late")
    assert rels
    assert all(r["type"] == "group_means" for r in rels)
    features = {r["feature"] for r in rels}
    assert "distance_km" in features


def test_target_relationships_numeric_target(sample_df):
    rels = target_relationships(sample_df, target="delivery_days")
    assert rels
    assert all(r["type"] == "correlation" for r in rels)


def test_target_relationships_missing_column(sample_df):
    assert target_relationships(sample_df, target="does_not_exist") == []


def test_detect_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    issues = detect_data_quality_issues(df)
    assert issues["duplicates"]["count"] == 2


def test_detect_missing():
    df = pd.DataFrame({"a": [1, None, 3], "b": [None, 2, 3]})
    issues = detect_data_quality_issues(df)
    assert issues["missing"]["count"] == 2


def test_detect_outliers_flags_extremes():
    values = list(range(1, 51)) + [100000]
    df = pd.DataFrame({"val": values})
    issues = detect_data_quality_issues(df)
    assert issues["outliers"]["count"] >= 1


def test_detect_pii_by_column_name():
    df = pd.DataFrame({"customer_email": ["a@b.com"], "amount": [10]})
    flagged = detect_pii_columns(df, patterns=["email"])
    assert any(f["column"] == "customer_email" for f in flagged)


def test_detect_pii_by_value_pattern():
    df = pd.DataFrame({"contact": ["reach me at john@example.com"]})
    flagged = detect_pii_columns(df, patterns=[])
    assert flagged
    assert "email" in flagged[0]["value_matches"]
