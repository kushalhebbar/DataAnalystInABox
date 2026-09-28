"""Run the evaluation harness over the labeled datasets.

Fast, deterministic checks (target detection, PII detection) run by default and
need no LLM. Pass --full to also run the whole graph per dataset and measure
insight faithfulness and latency (requires Ollama, or LLM_PROVIDER=none for a
heuristic-only baseline).

    poetry run python code/evals/run_eval.py
    poetry run python code/evals/run_eval.py --full
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evals.fixtures import EvalCase, cases
from evals.metrics import faithfulness, pii_score, target_rank
from src.nodes.insights import _evidence_pack
from src.nodes.target import target_detect_node
from src.state import Inputs, Profile, RunConfig, RunState
from src.tools import advanced_profile, detect_pii_columns


def _ranked_candidates(case: EvalCase) -> list[str]:
    df = case.frame()
    inputs = Inputs(
        dataset_paths=[case.name],
        problem_statement=case.problem_statement,
        audience=case.audience,
        goal_type="analysis",
        success_metric=case.success_metric,
    )
    state = RunState(inputs=inputs)
    state.profile = Profile(**advanced_profile(df))
    target_detect_node(state)
    entry = next((a for a in state.audit if a.get("step") == "target_detect"), {})
    return [c["column"] for c in entry.get("candidates", [])]


def _flagged_pii(case: EvalCase) -> set[str]:
    df = case.frame()
    patterns = RunConfig().pii_column_patterns
    return {f["column"] for f in detect_pii_columns(df, patterns)}


def _run_full(case: EvalCase) -> tuple[float, float, list[float], float]:
    from src.graph import build_graph

    df = case.frame()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        df.to_csv(tmp.name, index=False)
        path = tmp.name
    inputs = Inputs(
        dataset_paths=[path],
        problem_statement=case.problem_statement,
        audience=case.audience,
        goal_type="analysis",
        success_metric=case.success_metric,
        target_column=case.target,
    )
    start = time.perf_counter()
    out = build_graph().invoke(RunState(inputs=inputs))
    elapsed = time.perf_counter() - start
    if isinstance(out, dict):
        out = RunState(**out)
    Path(path).unlink(missing_ok=True)

    if not out.insights:
        return 1.0, 1.0, [], elapsed
    summary = f"{out.insights.headline} {out.insights.narrative}"
    evidence = json.dumps(_evidence_pack(out), default=str)
    f = faithfulness(summary, evidence)
    return f.score, f.salient_score, f.ungrounded, elapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="also run the graph for faithfulness + latency")
    args = parser.parse_args()

    rows = []
    for case in cases():
        ranked = _ranked_candidates(case)
        rank = target_rank(ranked, case.target)
        pii = pii_score(_flagged_pii(case), case.pii_columns)
        row = {
            "dataset": case.name,
            "target_rank": rank,
            "top1": rank == 1,
            "top3": rank is not None and rank <= 3,
            "pii_precision": round(pii.precision, 2),
            "pii_recall": round(pii.recall, 2),
            "pii_f1": round(pii.f1, 2),
        }
        if args.full:
            score, salient, ungrounded, elapsed = _run_full(case)
            row.update(
                {
                    "faithfulness": round(score, 3),
                    "faithfulness_salient": round(salient, 3),
                    "ungrounded_numbers": ungrounded,
                    "latency_s": round(elapsed, 1),
                }
            )
        rows.append(row)

    _print_report(rows, full=args.full)

    out_dir = ROOT / "evals" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {out_dir / 'report.json'}")
    return 0


def _print_report(rows: list[dict], full: bool) -> None:
    n = len(rows)
    print(f"\nEvaluation over {n} labeled datasets\n" + "=" * 60)
    for r in rows:
        line = (
            f"{r['dataset']:30s} target_rank={str(r['target_rank']):>4s} "
            f"pii_f1={r['pii_f1']:.2f}"
        )
        if full:
            line += f" faithful={r['faithfulness']:.2f} ({r['latency_s']}s)"
        print(line)

    top1 = sum(r["top1"] for r in rows) / n
    top3 = sum(r["top3"] for r in rows) / n
    mean_f1 = sum(r["pii_f1"] for r in rows) / n
    print("-" * 60)
    print(f"Target detection:  top-1 {top1:.0%}   top-3 {top3:.0%}")
    print(f"PII detection:     mean F1 {mean_f1:.2f}")
    if full:
        mean_faith = sum(r["faithfulness"] for r in rows) / n
        mean_salient = sum(r["faithfulness_salient"] for r in rows) / n
        mean_lat = sum(r["latency_s"] for r in rows) / n
        total_ungrounded = sum(len(r["ungrounded_numbers"]) for r in rows)
        print(f"Insight faithfulness: {mean_faith:.0%} of cited numbers grounded "
              f"({mean_salient:.0%} of statistical figures); {total_ungrounded} ungrounded total")
        print(f"Mean latency:      {mean_lat:.1f}s per dataset")


if __name__ == "__main__":
    raise SystemExit(main())
