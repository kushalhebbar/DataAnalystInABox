import pytest

from evals.fixtures import cases
from evals.metrics import extract_numbers, faithfulness, pii_score, target_rank


def test_extract_numbers_handles_decimals_and_percent():
    nums = extract_numbers("r = 0.795 with 89% confidence over 205 rows")
    assert 0.795 in nums
    assert 0.89 in nums  # percent returned as fraction
    assert 205.0 in nums


def test_faithfulness_all_grounded():
    evidence = '{"r": 0.795, "confidence": 0.895, "rows": 205}'
    summary = "Correlation r = 0.80 at 89% confidence across 205 rows."
    f = faithfulness(summary, evidence)
    assert f.score == 1.0
    assert f.ungrounded == []


def test_faithfulness_flags_fabricated_number():
    evidence = '{"r": 0.795, "rows": 205}'
    summary = "Correlation r = 0.80 across 205 rows, plus a fabricated 0.42 effect."
    f = faithfulness(summary, evidence)
    assert 0.42 in f.ungrounded
    assert f.score < 1.0


def test_target_rank():
    assert target_rank(["churn", "x", "y"], "churn") == 1
    assert target_rank(["x", "churn", "y"], "churn") == 2
    assert target_rank(["x", "y"], "churn") is None


def test_pii_score_perfect():
    s = pii_score({"email", "name"}, {"email", "name"})
    assert s.precision == 1.0 and s.recall == 1.0 and s.f1 == 1.0


def test_pii_score_false_positive():
    s = pii_score({"email", "age"}, {"email"})
    assert s.recall == 1.0
    assert s.precision == 0.5
    assert "age" in s.false_positives


def test_pii_score_empty_truth_and_flags_is_perfect():
    s = pii_score(set(), set())
    assert s.f1 == 1.0


@pytest.mark.parametrize("case", cases(), ids=lambda c: c.name)
def test_fixture_has_labeled_target_and_pii(case):
    df = case.frame()
    assert case.target in df.columns
    assert case.pii_columns.issubset(set(df.columns))
