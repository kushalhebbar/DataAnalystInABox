"""Labeled datasets for evaluating the pipeline.

Each case carries ground truth (the real target column and the columns that
contain PII) so the harness can score target detection and PII detection. The
synthetic datasets are generated deterministically; the two delivery datasets
are the real CSVs used elsewhere in the project.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "code" / "tests" / "data"

_EMAIL_DOMAINS = ["gmail.com", "outlook.com", "company.co", "mail.net"]


def _emails(rng: np.random.Generator, n: int) -> list[str]:
    return [f"user{int(rng.integers(1000, 9999))}@{rng.choice(_EMAIL_DOMAINS)}" for _ in range(n)]


def _names(rng: np.random.Generator, n: int) -> list[str]:
    first = ["Alex", "Sam", "Jordan", "Riley", "Casey", "Morgan", "Taylor", "Jamie"]
    last = ["Lee", "Patel", "Garcia", "Khan", "Nguyen", "Silva", "Cohen", "Ito"]
    return [f"{rng.choice(first)} {rng.choice(last)}" for _ in range(n)]


@dataclass
class EvalCase:
    name: str
    target: str
    pii_columns: set[str]
    problem_statement: str
    audience: str
    success_metric: str
    builder: Optional[Callable[[], pd.DataFrame]] = None
    csv_path: Optional[str] = None

    def frame(self) -> pd.DataFrame:
        if self.csv_path:
            return pd.read_csv(self.csv_path)
        assert self.builder is not None
        return self.builder()


def _churn(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    tenure = rng.integers(1, 72, n)
    monthly = rng.normal(70, 25, n).clip(15, 150)
    tickets = rng.poisson(1.5, n)
    logit = -2.5 + 0.03 * (60 - tenure) + 0.02 * (monthly - 70) + 0.4 * tickets
    churn = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame(
        {
            "customer_id": np.arange(1, n + 1),
            "full_name": _names(rng, n),
            "email": _emails(rng, n),
            "tenure_months": tenure,
            "monthly_charges": monthly.round(2),
            "total_charges": (monthly * tenure).round(2),
            "contract_type": rng.choice(["monthly", "one_year", "two_year"], n),
            "support_tickets": tickets,
            "churn": churn,
        }
    )


def _loan_default(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(2)
    income = rng.normal(60000, 20000, n).clip(15000, 200000)
    loan = rng.normal(20000, 9000, n).clip(1000, 60000)
    credit = rng.normal(680, 70, n).clip(300, 850)
    logit = 3.0 - 0.004 * (credit - 680) + 0.00004 * (loan - 20000) - 0.00002 * (income - 60000)
    defaulted = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame(
        {
            "application_id": np.arange(1, n + 1),
            "applicant_name": _names(rng, n),
            "ssn": [f"{rng.integers(100,999)}-{rng.integers(10,99)}-{rng.integers(1000,9999)}" for _ in range(n)],
            "annual_income": income.round(0),
            "loan_amount": loan.round(0),
            "interest_rate": rng.normal(11, 3, n).clip(3, 25).round(2),
            "credit_score": credit.round(0),
            "employment_years": rng.integers(0, 35, n),
            "defaulted": defaulted,
        }
    )


def _fraud(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    amount = rng.exponential(80, n).clip(1, 5000)
    distance = rng.exponential(15, n).clip(0, 300)
    hour = rng.integers(0, 24, n)
    logit = -3.0 + 0.0008 * amount + 0.01 * distance + 0.06 * ((hour < 5).astype(int) * 10)
    is_fraud = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame(
        {
            "transaction_id": np.arange(1, n + 1),
            "cardholder_email": _emails(rng, n),
            "amount_usd": amount.round(2),
            "merchant_category": rng.choice(["grocery", "travel", "electronics", "dining", "online"], n),
            "hour_of_day": hour,
            "distance_from_home_km": distance.round(1),
            "is_fraud": is_fraud,
        }
    )


def _attrition(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(4)
    age = rng.integers(22, 60, n)
    income = rng.normal(6500, 2500, n).clip(2000, 20000)
    years = rng.integers(0, 30, n)
    satisfaction = rng.integers(1, 5, n)
    overtime = rng.choice([0, 1], n)
    logit = -1.5 + 0.4 * overtime - 0.3 * satisfaction - 0.02 * years
    attrition = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    return pd.DataFrame(
        {
            "employee_id": np.arange(1, n + 1),
            "work_email": _emails(rng, n),
            "phone_number": [f"+1-{rng.integers(200,999)}-{rng.integers(200,999)}-{rng.integers(1000,9999)}" for _ in range(n)],
            "age": age,
            "monthly_income": income.round(0),
            "years_at_company": years,
            "job_satisfaction": satisfaction,
            "overtime": overtime,
            "attrition": attrition,
        }
    )


def cases() -> list[EvalCase]:
    return [
        EvalCase(
            name="customer_churn",
            target="churn",
            pii_columns={"full_name", "email"},
            problem_statement="Understand which customers are likely to churn and why.",
            audience="Retention team",
            success_metric="Reduce monthly churn by 15%.",
            builder=_churn,
        ),
        EvalCase(
            name="loan_default",
            target="defaulted",
            pii_columns={"applicant_name", "ssn"},
            problem_statement="Identify drivers of loan default risk.",
            audience="Credit risk team",
            success_metric="Lower default rate without shrinking the book by more than 5%.",
            builder=_loan_default,
        ),
        EvalCase(
            name="fraud_transactions",
            target="is_fraud",
            pii_columns={"cardholder_email"},
            problem_statement="Find the signals most associated with fraudulent transactions.",
            audience="Fraud operations",
            success_metric="Catch more fraud at a fixed false-positive rate.",
            builder=_fraud,
        ),
        EvalCase(
            name="employee_attrition",
            target="attrition",
            pii_columns={"work_email", "phone_number"},
            problem_statement="Explain what drives employees to leave.",
            audience="People analytics",
            success_metric="Cut regretted attrition by 10%.",
            builder=_attrition,
        ),
        EvalCase(
            name="delivery_operations",
            target="late_delivery",
            pii_columns=set(),
            problem_statement="Understand what drives late deliveries.",
            audience="Operations manager",
            success_metric="Improve on-time delivery rate.",
            csv_path=str(DATA / "delivery_operations.csv"),
        ),
        EvalCase(
            name="delivery_operations_complex",
            target="late_delivery",
            pii_columns={"customer_name", "customer_email"},
            problem_statement="Understand what drives late deliveries across regions and carriers.",
            audience="Operations manager",
            success_metric="Improve on-time delivery rate.",
            csv_path=str(DATA / "delivery_operations_complex.csv"),
        ),
    ]
