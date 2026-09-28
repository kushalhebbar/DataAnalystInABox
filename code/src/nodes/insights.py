from __future__ import annotations

import json

from ..llm import get_llm, llm_enabled
from ..state import Insights, LineageEntry, RunState
from ..logging_config import setup_logging

logger = setup_logging(name="insights_node")


def _as_text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return "" if value is None else str(value)


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [_flatten_item(v) for v in value if v]
    return [_flatten_item(value)] if value else []


def _flatten_item(item) -> str:
    if isinstance(item, dict):
        for key in ("action", "recommendation", "text", "statement", "risk", "description", "detail"):
            if item.get(key):
                return str(item[key])
        return "; ".join(f"{k}: {v}" for k, v in item.items())
    return str(item)


def _evidence_pack(state: RunState) -> dict:
    """Compact, numbers-only context so the model summarizes facts rather than inventing them."""
    profile = state.profile
    eda = state.eda
    pack = {
        "rows": profile.rows if profile else 0,
        "cols": profile.cols if profile else 0,
        "target": state.inputs.target_column or "none",
        "top_correlations": eda.correlations[:5] if eda else [],
        "target_relationships": eda.target_relationships[:5] if eda else [],
        "findings": [f.model_dump() for f in (eda.findings if eda else [])],
    }
    if profile:
        high_missing = {c: p for c, p in profile.missing_pct.items() if p > 0}
        pack["columns_with_missing"] = dict(sorted(high_missing.items(), key=lambda kv: kv[1], reverse=True)[:5])
    return pack


def insights_node(state: RunState) -> RunState:
    logger.info("Insights node started")
    if not state.eda:
        logger.warning("No EDA result available, skipping insights")
        state.audit.append({"step": "insights", "status": "skip", "reason": "no_eda"})
        return state

    evidence = _evidence_pack(state)
    system = (
        "You are a senior data analyst briefing a stakeholder. "
        "Write findings grounded ONLY in the evidence provided; never invent numbers. "
        "Respond with VALID JSON ONLY, no markdown. Keys:\n"
        "{\n"
        '  "headline": "one-sentence takeaway",\n'
        '  "narrative": "3-5 sentence summary citing concrete numbers from the evidence",\n'
        '  "recommendations": ["actionable next step", ...],\n'
        '  "risks": ["caveat or data limitation", ...]\n'
        "}"
    )
    user = (
        f"Problem: {state.improved_problem_statement or state.inputs.problem_statement}\n"
        f"Audience: {state.inputs.audience}\n"
        f"Success metric: {state.inputs.success_metric}\n"
        f"Evidence (JSON): {json.dumps(evidence, default=str)}"
    )

    llm = get_llm() if llm_enabled() else None
    raw = llm.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}]).strip() if llm else ""

    try:
        obj = json.loads(raw)
        state.insights = Insights(
            headline=_as_text(obj.get("headline")),
            narrative=_as_text(obj.get("narrative")),
            recommendations=_as_list(obj.get("recommendations")),
            risks=_as_list(obj.get("risks")),
        )
        status, confidence = "success", 0.75
        caveat = "LLM-generated summary grounded in computed evidence. Verify against domain knowledge."
    except Exception as e:
        logger.warning(f"Insights JSON parse failed: {e}, using evidence fallback")
        headline = state.eda.findings[0].statement if state.eda.findings else "Exploratory analysis complete."
        state.insights = Insights(
            headline=headline,
            narrative=" ".join(f.statement for f in state.eda.findings[:3]) or "See charts and correlations.",
            recommendations=["Review flagged data-quality issues before drawing conclusions."],
            risks=[f.caveat for f in state.eda.findings[:2] if f.caveat],
        )
        status, confidence = "fallback", 0.5
        caveat = "LLM parsing failed; summary assembled from computed findings."

    state.audit.append({"step": "insights", "status": "ok"})
    state.lineage.append(
        LineageEntry(
            node="insights",
            transformations=[{"type": "llm_summary", "response_tokens": len(raw)}],
            decisions=[
                {
                    "decision": "insight_generation",
                    "status": status,
                    "recommendations": len(state.insights.recommendations),
                    "risks": len(state.insights.risks),
                    "confidence": confidence,
                    "caveat": caveat,
                }
            ],
        )
    )
    state.stage = "insights_done"
    logger.info("Insights node completed")
    return state
