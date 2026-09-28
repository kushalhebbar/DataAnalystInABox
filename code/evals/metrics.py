"""Metrics for the evaluation harness.

Three things are measured:

- Faithfulness: does the generated summary only cite numbers that were present
  in the evidence the model was given? This catches fabricated statistics.
- Target detection: is the true target column ranked first / within the top-k
  candidates by the heuristic scorer?
- PII detection: precision / recall / F1 of the flagged columns against the
  known PII columns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?%?")


def extract_numbers(text: str) -> list[float]:
    """Pull numeric literals from text. Percentages are returned as their fraction."""
    values = []
    for token in _NUMBER.findall(text or ""):
        if token.endswith("%"):
            values.append(float(token[:-1]) / 100.0)
        else:
            values.append(float(token))
    return values


def _matches(value: float, evidence: list[float], rel_tol: float = 0.02, abs_tol: float = 0.03) -> bool:
    """A narrative number is grounded if it (or its percent/fraction form) is close to some evidence number."""
    candidates = {value, value / 100.0, value * 100.0}
    for c in candidates:
        for e in evidence:
            if abs(c - e) <= max(abs_tol, rel_tol * max(abs(c), abs(e))):
                return True
    return False


def _is_salient(value: float) -> bool:
    """Substantive statistical claims: decimals, or magnitudes unlikely to be mere phrasing."""
    return value != int(value) or abs(value) >= 10


@dataclass
class Faithfulness:
    grounded: int
    total: int
    ungrounded: list[float]
    salient_grounded: int
    salient_total: int

    @property
    def score(self) -> float:
        return self.grounded / self.total if self.total else 1.0

    @property
    def salient_score(self) -> float:
        return self.salient_grounded / self.salient_total if self.salient_total else 1.0


def faithfulness(summary_text: str, evidence_text: str) -> Faithfulness:
    """Fraction of numbers in the summary that appear in the evidence given to the model."""
    evidence = extract_numbers(evidence_text)
    claimed = extract_numbers(summary_text)
    grounded = [n for n in claimed if _matches(n, evidence)]
    ungrounded = [n for n in claimed if not _matches(n, evidence)]
    salient = [n for n in claimed if _is_salient(n)]
    salient_grounded = [n for n in salient if _matches(n, evidence)]
    return Faithfulness(
        grounded=len(grounded),
        total=len(claimed),
        ungrounded=ungrounded,
        salient_grounded=len(salient_grounded),
        salient_total=len(salient),
    )


def target_rank(ranked_columns: list[str], true_target: str) -> int | None:
    """1-based rank of the true target among ranked candidates, or None if absent."""
    for i, col in enumerate(ranked_columns, start=1):
        if col == true_target:
            return i
    return None


@dataclass
class PIIScore:
    precision: float
    recall: float
    f1: float
    true_positives: set[str]
    false_positives: set[str]
    false_negatives: set[str]


def pii_score(flagged: set[str], truth: set[str]) -> PIIScore:
    tp = flagged & truth
    fp = flagged - truth
    fn = truth - flagged
    precision = len(tp) / len(flagged) if flagged else (1.0 if not truth else 0.0)
    recall = len(tp) / len(truth) if truth else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return PIIScore(precision, recall, f1, tp, fp, fn)
