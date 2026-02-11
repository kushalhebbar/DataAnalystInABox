from __future__ import annotations

from ..state import RunState, Profile, LineageSnapshot, LineageEntry
from ..tools import read_csv, advanced_profile, detect_pii_columns, detect_data_quality_issues
from ..logging_config import setup_logging

logger = setup_logging(name="profile_node")

def profile_node(state: RunState) -> RunState:
    logger.info("Profile node started")
    try:
        path = state.inputs.dataset_paths[0]
        logger.info(f"Reading CSV from: {path}")
        df = read_csv(path)
        logger.info(f"CSV loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        
        prof = advanced_profile(df)
        state.profile = Profile(**prof)
        state.audit.append({"step": "profile", "status": "ok", "rows": state.profile.rows, "cols": state.profile.cols})
        logger.info(f"Profile created: {state.profile.rows} rows, {state.profile.cols} cols")

        flagged = detect_pii_columns(df, state.config.pii_column_patterns)
        decisions = []
        
        # PII check
        if flagged:
            flagged_cols = [f["column"] for f in flagged]
            logger.warning(f"PII-like columns detected: {flagged_cols}")
            state.audit.append({"step": "pii_check", "status": "warn", "flagged_columns": flagged_cols})
            decisions.append({
                "decision": "pii_check",
                "status": "warn",
                "flagged_columns": flagged_cols,
                "examples": flagged,
                "confidence": 0.7,
                "caveat": "Pattern/value-based detection with masked samples. Manual review recommended.",
            })
        else:
            logger.info("PII check: no suspicious columns detected")
            state.audit.append({"step": "pii_check", "status": "ok"})
            decisions.append({
                "decision": "pii_check",
                "status": "ok",
                "confidence": 0.9,
                "caveat": "Pattern-based detection only. May miss obfuscated PII or non-standard formats."
            })
        
        # Data quality issues
        quality_issues = detect_data_quality_issues(df)
        
        # Check if user provided feedback to override quality decisions
        feedback_outlier_indices = set()
        feedback_duplicate_indices = set()
        
        for feedback in state.user_feedback:
            if feedback.node == "profile":
                if feedback.decision_type == "outliers_detected" and feedback.action == "keep_rows":
                    feedback_outlier_indices.update(feedback.affected_indices)
                elif feedback.decision_type == "duplicates_detected" and feedback.action == "keep_rows":
                    feedback_duplicate_indices.update(feedback.affected_indices)
        
        # Apply feedback: remove user-approved rows from issues
        if feedback_outlier_indices and quality_issues["outliers"]["examples"]:
            # Filter out rows user wants to keep
            original_count = quality_issues["outliers"]["count"]
            quality_issues["outliers"]["count"] = max(0, original_count - len(feedback_outlier_indices))
            if quality_issues["outliers"]["count"] == 0:
                quality_issues["outliers"]["examples"] = []
        
        if feedback_duplicate_indices and quality_issues["duplicates"]["examples"]:
            original_count = quality_issues["duplicates"]["count"]
            quality_issues["duplicates"]["count"] = max(0, original_count - len(feedback_duplicate_indices))
            if quality_issues["duplicates"]["count"] == 0:
                quality_issues["duplicates"]["examples"] = []
        
        rows = max(state.profile.rows, 1)
        missing_avg = sum(state.profile.missing_pct.values()) / max(len(state.profile.missing_pct), 1)
        dup_pct = (quality_issues["duplicates"]["count"] / rows) * 100
        outlier_pct = (quality_issues["outliers"]["count"] / rows) * 100
        score = max(0.0, 100 - (missing_avg * 0.5 + dup_pct * 2 + outlier_pct * 1.5))
        decisions.append({
            "decision": "data_quality_score",
            "score": round(score, 2),
            "missing_avg_pct": round(missing_avg, 2),
            "duplicate_row_pct": round(dup_pct, 2),
            "outlier_row_pct": round(outlier_pct, 2),
            "confidence": 0.7,
            "caveat": "Heuristic score based on missingness, duplicates, and outliers.",
        })

        if quality_issues["duplicates"]["count"] > 0:
            dup_count = quality_issues["duplicates"]["count"]
            logger.warning(f"Found {dup_count} duplicate rows")
            decisions.append({
                "decision": "duplicates_detected",
                "count": dup_count,
                "examples": quality_issues["duplicates"]["examples"],
                "confidence": 1.0,
                "caveat": f"{dup_count} duplicate rows found. Review before analysis.",
            })
        
        if quality_issues["missing"]["count"] > 0:
            missing_count = quality_issues["missing"]["count"]
            logger.info(f"Found {missing_count} rows with missing values")
            decisions.append({
                "decision": "missing_values_detected",
                "rows_affected": missing_count,
                "examples": quality_issues["missing"]["examples"],
                "confidence": 1.0,
                "caveat": f"{missing_count} rows have missing values. May impact analysis.",
            })
        
        if quality_issues["outliers"]["count"] > 0:
            outlier_count = quality_issues["outliers"]["count"]
            logger.info(f"Found {outlier_count} rows with outliers")
            decisions.append({
                "decision": "outliers_detected",
                "rows_affected": outlier_count,
                "details": quality_issues["outliers"].get("details", []),
                "examples": quality_issues["outliers"]["examples"],
                "confidence": 0.8,
                "caveat": f"Outliers detected using IQR method. May be valid extreme values.",
            })

        entry = LineageEntry(
            node="profile",
            input=LineageSnapshot(**prof),
            transformations=[{"type": "load_csv", "path": path, "rows_loaded": df.shape[0]}],
            output=LineageSnapshot(**state.profile.model_dump()),
            decisions=decisions,
        )
        state.lineage.append(entry)

        state.stage = "profile_done"
        logger.info("Profile node completed successfully")
        return state
    except Exception as e:
        logger.error(f"Profile node error: {str(e)}", exc_info=True)
        state.errors.append(str(e))
        state.stage = "failed"
        return state
