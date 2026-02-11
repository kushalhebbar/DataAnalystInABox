from __future__ import annotations

from ..state import RunState, LineageEntry
from ..logging_config import setup_logging

logger = setup_logging(name="target_node")

LABEL_HINTS_STRONG = ["target", "label", "outcome", "class", "churn", "fraud", "late_delivery"]
LABEL_HINTS_WEAK = ["late", "delay", "failed", "defect", "is_", "has_"]

ID_HINTS = ["id", "uuid"]
DATE_HINTS = ["date", "time", "timestamp"]


def _has_any(s: str, hints: list[str]) -> bool:
    s = s.lower()
    return any(h in s for h in hints)


def target_detect_node(state: RunState) -> RunState:
    logger.info("Target detect node started")
    if not state.profile:
        logger.warning("No profile available, skipping target detection")
        state.audit.append({"step": "target_detect", "status": "skip", "reason": "no_profile"})
        return state

    # If user provided target, trust it
    if state.inputs.target_column:
        logger.info(f"User-provided target: {state.inputs.target_column}")
        state.audit.append({"step": "target_detect", "status": "ok", "target": state.inputs.target_column, "source": "user"})
        return state

    logger.info("Scanning for candidate target columns...")
    candidates = []
    for c in state.profile.columns:
        cname = c.lower()
        dtype = state.profile.dtypes.get(c, "").lower()
        nuniq = state.profile.n_unique.get(c, 10**9)

        # Exclude obvious non-targets
        if _has_any(cname, ID_HINTS):
            continue
        if _has_any(cname, DATE_HINTS):
            continue

        # Identify boolean-ish
        boolish = nuniq == 2 or (nuniq == 1)  # allow degenerate, flag later

        # Score
        score = 0
        reasons = []

        if boolish:
            score += 5
            reasons.append("boolish")

        if _has_any(cname, LABEL_HINTS_STRONG):
            score += 6
            reasons.append("strong_label_hint")
        elif _has_any(cname, LABEL_HINTS_WEAK):
            score += 2
            reasons.append("weak_label_hint")

        # Penalize high-cardinality for target
        if nuniq > 50:
            score -= 3
            reasons.append("high_cardinality_penalty")

        # Penalize continuous numeric targets ONLY slightly (they can be regression)
        numeric = ("int" in dtype) or ("float" in dtype)
        if numeric and not boolish:
            score += 1
            reasons.append("numeric_possible_regression")

        if score > 0:
            candidates.append({"column": c, "score": score, "n_unique": nuniq, "dtype": dtype, "reasons": reasons})

    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)[:5]
    logger.info(f"Found {len(candidates)} target candidates: {[c['column'] for c in candidates]}")
    state.audit.append({"step": "target_detect", "status": "ok", "candidates": candidates})
    
    # Lineage: capture target detection reasoning
    decisions = []
    if state.inputs.target_column:
        decisions.append({
            "decision": "target_confirmed",
            "target": state.inputs.target_column,
            "source": "user_provided",
            "confidence": 1.0,
            "caveat": "User-provided target accepted without validation."
        })
    elif candidates:
        top_candidate = candidates[0]
        decisions.append({
            "decision": "target_suggested",
            "column": top_candidate["column"],
            "score": top_candidate["score"],
            "reasons": top_candidate["reasons"],
            "n_unique": top_candidate["n_unique"],
            "confidence": min(top_candidate["score"] / 10.0, 1.0),  # Normalize score to 0-1
            "caveat": f"Based on heuristics. Sample size: {state.profile.rows} rows.",
        })
        for candidate in candidates[1:]:
            decisions.append({
                "decision": "alternative_target",
                "column": candidate["column"],
                "score": candidate["score"],
                "reasons": candidate["reasons"],
            })
    else:
        decisions.append({
            "decision": "no_target_found",
            "confidence": 0.0,
            "caveat": "No clear target column identified. Manual specification recommended.",
        })
    
    entry = LineageEntry(
        node="target_detect",
        transformations=[{"type": "target_scoring", "candidates_evaluated": len(state.profile.columns)}],
        decisions=decisions,
    )
    state.lineage.append(entry)
    
    logger.info("Target detect node completed")
    return state
