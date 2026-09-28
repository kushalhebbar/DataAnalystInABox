import pandas as pd

from src.nodes.target import target_detect_node
from src.state import Inputs, Profile, RunState
from src.tools import advanced_profile


def _state_with(df: pd.DataFrame, target: str | None = None) -> RunState:
    inputs = Inputs(
        dataset_paths=["dummy.csv"],
        problem_statement="p",
        audience="a",
        goal_type="analysis",
        success_metric="m",
        target_column=target,
    )
    state = RunState(inputs=inputs)
    state.profile = Profile(**advanced_profile(df))
    return state


def test_user_target_is_trusted():
    df = pd.DataFrame({"late_delivery": [0, 1, 0, 1], "x": [1, 2, 3, 4]})
    state = target_detect_node(_state_with(df, target="late_delivery"))
    step = next(a for a in state.audit if a["step"] == "target_detect")
    assert step["source"] == "user"


def test_binary_label_column_ranked_first():
    df = pd.DataFrame(
        {
            "order_id": range(1, 21),
            "amount": range(100, 120),
            "churn": [0, 1] * 10,
        }
    )
    state = target_detect_node(_state_with(df))
    entry = next(e for e in state.lineage if e.node == "target_detect")
    suggested = next(d for d in entry.decisions if d["decision"] == "target_suggested")
    assert suggested["column"] == "churn"


def test_id_and_date_columns_excluded():
    df = pd.DataFrame(
        {
            "user_id": range(1, 11),
            "created_date": pd.date_range("2024-01-01", periods=10).astype(str),
            "is_fraud": [0, 1] * 5,
        }
    )
    state = target_detect_node(_state_with(df))
    step = next(a for a in state.audit if a["step"] == "target_detect")
    columns = {c["column"] for c in step["candidates"]}
    assert "user_id" not in columns
    assert "created_date" not in columns
    assert "is_fraud" in columns
