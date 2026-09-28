from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ..state import Chart, EDAResult, Finding, LineageEntry, RunState
from ..tools import read_csv, target_relationships, top_correlations
from ..logging_config import setup_logging

logger = setup_logging(name="eda_node")

ARTIFACTS_ROOT = Path("artifacts")
MAX_HISTOGRAMS = 6


def _charts_dir(run_id: str) -> Path:
    d = ARTIFACTS_ROOT / run_id / "charts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _distribution_charts(df, numeric_cols, out_dir: Path) -> list[Chart]:
    charts = []
    for col in numeric_cols[:MAX_HISTOGRAMS]:
        series = df[col].dropna()
        if series.empty:
            continue
        fig, ax = plt.subplots(figsize=(5, 3.2))
        ax.hist(series, bins=min(30, max(10, series.nunique())), color="#4C78A8", edgecolor="white")
        ax.set_title(f"Distribution of {col}")
        ax.set_xlabel(col)
        ax.set_ylabel("Count")
        fig.tight_layout()
        path = out_dir / f"dist_{col}.png"
        fig.savefig(path, dpi=110)
        plt.close(fig)
        charts.append(
            Chart(title=f"Distribution of {col}", path=str(path), kind="histogram",
                  caption=f"Spread of {col} (n={len(series)}).")
        )
    return charts


def _correlation_heatmap(df, numeric_cols, out_dir: Path) -> Chart | None:
    if len(numeric_cols) < 2:
        return None
    corr = df[numeric_cols].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(numeric_cols)))
    ax.set_yticks(range(len(numeric_cols)))
    ax.set_xticklabels(numeric_cols, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(numeric_cols, fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Correlation matrix")
    fig.tight_layout()
    path = out_dir / "correlation_matrix.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return Chart(title="Correlation matrix", path=str(path), kind="correlation",
                 caption="Pairwise Pearson correlation across numeric features.")


def _target_chart(df, target: str, relationships, out_dir: Path) -> Chart | None:
    if not relationships:
        return None
    top = relationships[:8]
    labels = [r["feature"] for r in top]
    values = [r["value"] for r in top]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.barh(labels[::-1], values[::-1], color="#F58518")
    kind_label = "correlation with" if top[0]["type"] == "correlation" else "group-mean spread by"
    ax.set_title(f"Top features {kind_label} {target}")
    ax.set_xlabel("Strength")
    fig.tight_layout()
    path = out_dir / "target_relationships.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return Chart(title=f"Feature relationship to {target}", path=str(path), kind="bar",
                 caption=f"Features most associated with {target}.")


def _findings(correlations, relationships, target: str | None) -> list[Finding]:
    findings: list[Finding] = []
    for c in correlations[:3]:
        strength = "strong" if abs(c["r"]) >= 0.7 else "moderate"
        findings.append(
            Finding(
                statement=f"{c['x']} and {c['y']} show a {strength} {'positive' if c['r'] > 0 else 'negative'} relationship.",
                evidence=f"Pearson r = {c['r']}",
                confidence=min(abs(c["r"]) + 0.1, 0.95),
                caveat="Correlation does not imply causation; confounders not controlled.",
            )
        )
    if target and relationships:
        top = relationships[0]
        if top["type"] == "correlation":
            findings.append(
                Finding(
                    statement=f"{top['feature']} is the numeric feature most correlated with {target}.",
                    evidence=f"r = {top['value']}",
                    confidence=min(abs(top["value"]) + 0.1, 0.9),
                    caveat="Univariate view only; multivariate effects not modeled here.",
                )
            )
        else:
            findings.append(
                Finding(
                    statement=f"{top['feature']} differs most across {target} groups.",
                    evidence=f"group-mean spread = {top['value']} ({top.get('by_group')})",
                    confidence=0.7,
                    caveat="Group sizes may be imbalanced; differences unadjusted.",
                )
            )
    return findings


def eda_node(state: RunState) -> RunState:
    logger.info("EDA node started")
    if not state.profile:
        logger.warning("No profile available, skipping EDA")
        state.audit.append({"step": "eda", "status": "skip", "reason": "no_profile"})
        return state

    try:
        df = read_csv(state.inputs.dataset_paths[0])
        numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
        out_dir = _charts_dir(state.config.run_id)

        correlations = top_correlations(df)
        target = state.inputs.target_column
        relationships = target_relationships(df, target) if target else []

        charts = _distribution_charts(df, numeric_cols, out_dir)
        heatmap = _correlation_heatmap(df, numeric_cols, out_dir)
        if heatmap:
            charts.append(heatmap)
        target_chart = _target_chart(df, target, relationships, out_dir) if target else None
        if target_chart:
            charts.append(target_chart)

        findings = _findings(correlations, relationships, target)

        state.eda = EDAResult(
            charts=charts,
            correlations=correlations,
            target_relationships=relationships,
            findings=findings,
        )
        state.audit.append({"step": "eda", "status": "ok", "charts": len(charts), "findings": len(findings)})

        state.lineage.append(
            LineageEntry(
                node="eda",
                transformations=[
                    {"type": "generate_charts", "count": len(charts), "dir": str(out_dir)},
                    {"type": "compute_correlations", "pairs": len(correlations)},
                ],
                decisions=[
                    {
                        "decision": "eda_summary",
                        "charts": len(charts),
                        "correlation_pairs": len(correlations),
                        "target_features_ranked": len(relationships),
                        "confidence": 0.8,
                        "caveat": "Automated EDA. Univariate/pairwise only; no causal or multivariate modeling.",
                    }
                ],
            )
        )
        state.stage = "eda_done"
        logger.info(f"EDA node completed: {len(charts)} charts, {len(findings)} findings")
        return state
    except Exception as e:
        logger.error(f"EDA node error: {e}", exc_info=True)
        state.errors.append(str(e))
        return state
