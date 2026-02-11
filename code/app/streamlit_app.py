import sys
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
import tempfile
import os
import json

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from src.state import Inputs, RunState
from src.graph import build_graph
from src.tools import read_csv, basic_profile
from src.logging_config import setup_logging

logger = setup_logging(log_dir=str(ROOT / "logs"), name="streamlit_app")
logger.info("Streamlit app started")


def generate_test_results(artifacts_root: Path, output_path: Path) -> None:
    runs = []
    for state_path in artifacts_root.glob("*/state.json"):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            state = RunState(**data)
            runs.append(
                {
                    "run_id": state.config.run_id,
                    "created_at": state.config.created_at,
                    "dataset": (state.inputs.dataset_paths or [""])[0],
                    "target": state.inputs.target_column or "(none)",
                    "stage": state.stage,
                    "user_questions": len(state.user_questions),
                    "internal_questions": len(state.internal_questions),
                    "audit_entries": len(state.audit),
                    "errors": state.errors,
                    "state_path": str(state_path),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to parse artifact {state_path}: {e}")

    runs.sort(key=lambda r: r.get("created_at") or "")

    total = len(runs)
    passed = sum(1 for r in runs if not r["errors"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# Test Results",
        "",
        f"Generated: {now}",
        f"Total runs: {total}",
        f"Passed: {passed}",
        f"Failed: {total - passed}",
        "",
        "## Runs",
    ]

    for r in runs:
        status = "PASS" if not r["errors"] else "FAIL"
        created = r.get("created_at") or "(unknown)"
        lines.extend(
            [
                "",
                f"### {status} — Run ID {r['run_id']}",
                f"- Created: {created}",
                f"- Dataset: {r['dataset']}",
                f"- Target: {r['target']}",
                f"- Stage: {r['stage']}",
                f"- User questions: {r['user_questions']}",
                f"- Internal questions: {r['internal_questions']}",
                f"- Audit entries: {r['audit_entries']}",
                f"- Artifact: {r['state_path']}",
            ]
        )
        if r["errors"]:
            lines.append(f"- Errors: {r['errors']}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Test results written to: {output_path}")

st.set_page_config(page_title="Analyst-in-a-Box", layout="wide")
st.title("Analyst-in-a-Box (Phase 1: Intake + Profiling)")

# Initialize session state with defaults
if "test_mode" not in st.session_state:
    test_config_path = os.getenv("TEST_CONFIG")
    if test_config_path and os.path.exists(test_config_path):
        logger.info(f"Test mode enabled: {test_config_path}")
        with open(test_config_path) as f:
            test_config = json.load(f)
        st.session_state.uploaded_path = test_config.get("csv_path")
        st.session_state.problem_statement = test_config.get("problem_statement", "")
        st.session_state.audience = test_config.get("audience", "")
        st.session_state.goal_type = test_config.get("goal_type", "unsure")
        st.session_state.success_metric = test_config.get("success_metric", "")
        st.session_state.data_dictionary = test_config.get("data_dictionary", "")
        st.session_state.target_column = test_config.get("target_column", "")
        st.session_state.test_mode = True
    else:
        st.session_state.test_mode = False
        logger.info("Manual mode: waiting for CSV upload")

# File upload (skipped in test mode)
if st.session_state.test_mode:
    st.info(f"🧪 Test mode: using {st.session_state.uploaded_path}")
    uploaded = None
else:
    uploaded = st.file_uploader("Upload dataset (CSV)", type=["csv"])

col1, col2 = st.columns(2)
with col1:
    audience = st.text_input(
        "Audience (mandatory)",
        value=st.session_state.get("audience", ""),
        placeholder="Ops manager / Exec / Analyst / Engineer"
    )
    success_metric = st.text_input(
        "Success metric (mandatory)",
        value=st.session_state.get("success_metric", ""),
        placeholder="Reduce cycle time by 10%, lower cost, etc."
    )
with col2:
    goal_type = st.selectbox(
        "Goal type (mandatory)",
        ["unsure", "analysis", "prediction"],
        index=["unsure", "analysis", "prediction"].index(st.session_state.get("goal_type", "unsure"))
    )

problem_statement = st.text_area(
    "Problem statement (mandatory)",
    value=st.session_state.get("problem_statement", ""),
    height=140
)
data_dictionary = st.text_area(
    "Data dictionary (optional, encouraged)",
    value=st.session_state.get("data_dictionary", ""),
    height=120,
    placeholder="Paste column meanings, units, notes..."
)

target_column = st.text_input(
    "Target column (optional)",
    value=st.session_state.get("target_column", ""),
    placeholder="Leave blank unless you know it"
)

run_btn = st.button(
    "Run Phase 1",
    type="primary",
    disabled=(
        (uploaded is None and not st.session_state.test_mode)
        or not problem_statement.strip()
        or not audience.strip()
        or not success_metric.strip()
    ),
)

if run_btn:
    with st.spinner("Running..."):
        logger.info("Run button clicked")
        if st.session_state.test_mode:
            dataset_path = st.session_state.uploaded_path
            logger.info(f"Using test dataset: {dataset_path}")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(uploaded.getbuffer())
                dataset_path = tmp.name
            logger.info(f"Uploaded CSV saved to: {dataset_path}")

        inputs = Inputs(
            dataset_paths=[dataset_path],
            problem_statement=problem_statement.strip(),
            audience=audience.strip(),
            goal_type=goal_type,  # type: ignore
            success_metric=success_metric.strip(),
            data_dictionary=data_dictionary.strip() or None,
            target_column=target_column.strip() or None,
        )
        logger.info(f"Inputs created: problem_statement={len(problem_statement)} chars, audience={audience}")
        state = RunState(inputs=inputs)

        app = build_graph()
        logger.info("Graph built, invoking...")
        out = app.invoke(state)
        logger.info("Graph execution completed")
        
        # Convert dict to RunState if needed
        if isinstance(out, dict):
            out = RunState(**out)
        
        # Store in session state to preserve across reruns
        st.session_state.last_run_result = out

        # Persist artifacts
        run_id = out.config.run_id
        out_dir = os.path.join("artifacts", run_id)
        os.makedirs(out_dir, exist_ok=True)
        logger.info(f"Artifacts saved to: {out_dir}")

        with open(os.path.join(out_dir, "state.json"), "w", encoding="utf-8") as f:
            f.write(out.model_dump_json(indent=2))
        logger.info(f"State saved to state.json")
        
        # Generate human-readable explainability log
        explainability_lines = [
            f"EXPLAINABILITY LOG — Run ID: {run_id}",
            f"Generated: {out.config.created_at}",
            "=" * 80,
            "",
        ]
        
        for entry in out.lineage:
            explainability_lines.append(f"[{entry.timestamp}] {entry.node.upper()} NODE")
            
            if entry.transformations:
                explainability_lines.append("├─ Transformations:")
                for t in entry.transformations:
                    explainability_lines.append(f"│  └─ {t.get('type', 'unknown')}: {t}")
            
            if entry.decisions:
                explainability_lines.append("├─ Decisions:")
                for d in entry.decisions:
                    decision_name = d.get('decision', 'unknown')
                    confidence = d.get('confidence')
                    caveat = d.get('caveat')
                    conf_str = f" (confidence: {int(confidence*100)}%)" if confidence is not None else ""
                    explainability_lines.append(f"│  ├─ {decision_name}{conf_str}")
                    if caveat:
                        explainability_lines.append(f"│  │  └─ 💡 {caveat}")
                    for k, v in d.items():
                        if k not in ['decision', 'confidence', 'caveat']:
                            explainability_lines.append(f"│  │     {k}: {v}")
            
            if entry.input:
                explainability_lines.append(f"├─ Input: {entry.input.rows} rows, {entry.input.cols} cols")
            if entry.output:
                explainability_lines.append(f"└─ Output: {entry.output.rows} rows, {entry.output.cols} cols")
            
            explainability_lines.append("")
        
        with open(os.path.join(out_dir, "explainability.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(explainability_lines))
        logger.info("Explainability log saved")

        if st.session_state.test_mode:
            generate_test_results(
                artifacts_root=ROOT / "artifacts",
                output_path=ROOT / "TEST_RESULTS.md",
            )

# Display results (from current run or session_state)
if 'last_run_result' in st.session_state:
    out = st.session_state.last_run_result
    run_id = out.config.run_id
    out_dir = os.path.join("artifacts", run_id)
    
    st.success(f"✅ Analysis Complete — Run ID: {run_id}")
    st.caption(f"📁 Artifacts: `{out_dir}/`")
    
    # Clear results button
    if st.button("🗑️ Clear Results & Start New Analysis"):
        st.session_state.clear()
        st.rerun()
    
    # Download buttons
    if os.path.exists(out_dir):
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            state_path = os.path.join(out_dir, "state.json")
            if os.path.exists(state_path):
                with open(state_path, "r") as f:
                    st.download_button("⬇️ Download state.json", f.read(), f"{run_id}_state.json", "application/json")
        with col_dl2:
            log_path = os.path.join(out_dir, "explainability.log")
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    st.download_button("⬇️ Download explainability.log", f.read(), f"{run_id}_explainability.log", "text/plain")
    
    st.divider()
    
    # === SUMMARY DASHBOARD ===
    st.subheader("📊 Summary")
    metric_cols = st.columns(5)
    metric_cols[0].metric("Rows Processed", out.profile.rows if out.profile else 0)
    metric_cols[1].metric("Columns", out.profile.cols if out.profile else 0)
    
    # Count issues from lineage
    pii_count = 0
    quality_issues = 0
    avg_confidence = []
    
    for entry in out.lineage:
        for decision in entry.decisions:
            if decision.get("confidence"):
                avg_confidence.append(decision["confidence"])
            if "pii" in decision.get("decision", "").lower() and decision.get("status") == "warn":
                pii_count = len(decision.get("flagged_columns", []))
            if "duplicates" in decision.get("decision", "").lower():
                quality_issues += decision.get("count", 0)
            if "missing" in decision.get("decision", "").lower():
                quality_issues += decision.get("rows_affected", 0)
    
    metric_cols[2].metric("PII Columns", pii_count, delta="⚠️" if pii_count > 0 else None)
    metric_cols[3].metric("Quality Issues", quality_issues, delta="⚠️" if quality_issues > 0 else None)
    
    if avg_confidence:
        avg_conf_pct = int(sum(avg_confidence) / len(avg_confidence) * 100)
        metric_cols[4].metric("Avg Confidence", f"{avg_conf_pct}%")
    
    st.divider()
    
    # === DATA JOURNEY (LINEAGE) ===
    st.subheader("🔍 Data Journey & Transparency")
    if not out.lineage:
        st.info("No lineage entries yet.")
    else:
        for entry in out.lineage:
            with st.expander(f"{entry.node.upper()} — {entry.timestamp}", expanded=True):
                    # Before/After metrics
                    if entry.input:
                        st.markdown("**Before**")
                        col_a, col_b, col_c = st.columns(3)
                        col_a.metric("Rows", entry.input.rows)
                        col_b.metric("Cols", entry.input.cols)
                        col_c.metric("Missing % (avg)", f"{sum(entry.input.missing_pct.values())/max(len(entry.input.missing_pct),1):.2f}%")

                    if entry.output:
                        st.markdown("**After**")
                        col_d, col_e, col_f = st.columns(3)
                        col_d.metric("Rows", entry.output.rows)
                        col_e.metric("Cols", entry.output.cols)
                        col_f.metric("Missing % (avg)", f"{sum(entry.output.missing_pct.values())/max(len(entry.output.missing_pct),1):.2f}%")
                        
                        # Data diff viewer
                        if entry.input and (entry.input.rows != entry.output.rows or entry.input.cols != entry.output.cols):
                            st.markdown("**⚠️ Data Changed**")
                            diff_col1, diff_col2 = st.columns(2)
                            diff_col1.metric("Rows changed", entry.output.rows - entry.input.rows, delta=entry.output.rows - entry.input.rows)
                            diff_col2.metric("Cols changed", entry.output.cols - entry.input.cols, delta=entry.output.cols - entry.input.cols)

                    if entry.transformations:
                        st.markdown("**Transformations**")
                        st.table(entry.transformations)

                    if entry.decisions:
                        st.markdown("**Decisions & Confidence**")
                        for dec_idx, decision in enumerate(entry.decisions):
                            with st.container():
                                dec_cols = st.columns([3, 1, 2])
                                dec_cols[0].write(f"**{decision.get('decision', 'N/A')}**")
                                
                                # Confidence badge
                                confidence = decision.get('confidence')
                                if confidence is not None:
                                    conf_pct = int(confidence * 100)
                                    if confidence >= 0.8:
                                        dec_cols[1].success(f"✓ {conf_pct}% confident")
                                    elif confidence >= 0.5:
                                        dec_cols[1].warning(f"⚠ {conf_pct}% confident")
                                    else:
                                        dec_cols[1].error(f"⚠️ {conf_pct}% confident")
                                
                                # Caveat
                                caveat = decision.get('caveat')
                                if caveat:
                                    dec_cols[2].caption(f"💡 {caveat}")
                                
                                # Decision details
                                detail_items = {k: v for k, v in decision.items() if k not in ['decision', 'confidence', 'caveat']}
                                if detail_items:
                                    with st.expander("Details & Feedback", expanded=False):
                                        # Show examples prominently if present
                                        if 'examples' in detail_items:
                                            st.markdown("**📋 Example Rows:**")
                                            st.dataframe(detail_items['examples'], width="stretch")
                                            
                                            # Feedback UI for quality issues
                                            decision_type = decision.get('decision', '')
                                            if decision_type in ['outliers_detected', 'duplicates_detected']:
                                                st.markdown("---")
                                                st.markdown("**🔄 Provide Feedback**")
                                                
                                                feedback_key = f"feedback_{entry.node}_{dec_idx}"
                                                
                                                with st.form(key=f"form_{feedback_key}"):
                                                    disagree = st.checkbox(
                                                        f"These are NOT {decision_type.replace('_', ' ')} - keep them in analysis",
                                                        key=f"{feedback_key}_checkbox"
                                                    )
                                                    
                                                    reason = st.text_input(
                                                        "Why should we keep these rows?",
                                                        key=f"{feedback_key}_reason",
                                                        placeholder="e.g., These are valid extreme values for our business"
                                                    )
                                                    
                                                    submitted = st.form_submit_button("Save Feedback")
                                                    
                                                    if submitted and disagree and reason.strip():
                                                        st.session_state[f"stored_{feedback_key}"] = {
                                                            "node": entry.node,
                                                            "decision_type": decision_type,
                                                            "action": "keep_rows",
                                                            "reason": reason,
                                                            "count": decision.get('count') or decision.get('rows_affected', 0),
                                                        }
                                                        st.success("✓ Feedback saved!")
                                                
                                                # Show if feedback already stored
                                                if f"stored_{feedback_key}" in st.session_state:
                                                    stored = st.session_state[f"stored_{feedback_key}"]
                                                    st.info(f"✓ Feedback stored: {stored['reason']}")
                                            
                                            detail_items = {k: v for k, v in detail_items.items() if k != 'examples'}
                                        
                                        if detail_items:
                                            st.json(detail_items)

                    if entry.output and entry.output.sample_rows:
                        st.markdown("**Sample Rows**")
                        st.dataframe(entry.output.sample_rows, width="stretch")
    
    st.divider()
    
    # === QUESTIONS FOR USER ===
    st.subheader("❓ Questions for You (Clarifications)")
    if out.user_questions:
        # Use hash of question text as stable key (not index)
        import hashlib
        def question_key(q_text: str) -> str:
            return hashlib.md5(q_text.encode()).hexdigest()[:8]
        
        with st.form(key="clarification_form"):
            answers = {}  # Maps question text -> answer
            for i, q in enumerate(out.user_questions, 1):
                q_key = question_key(q.question)
                priority_icon = "🔴" if q.priority == "high" else "🟡" if q.priority == "medium" else "🟢"
                st.markdown(f"**{priority_icon} {i}. {q.question}**")
                st.caption(f"Why: {q.why}")
                answers[q.question] = st.text_area(
                    f"Answer {i}",
                    key=f"answer_{q_key}",
                    placeholder="Type your response here...",
                    label_visibility="collapsed",
                    height=80,
                )
                st.markdown("---")
            
            submitted = st.form_submit_button("💾 Save Answers", type="primary")
            
            if submitted:
                saved_count = 0
                for q_text, answer in answers.items():
                    if answer.strip():
                        q_key = question_key(q_text)
                        st.session_state[f"clarification_answer_{q_key}"] = {
                            "question": q_text,
                            "answer": answer.strip()
                        }
                        saved_count += 1
                if saved_count > 0:
                    st.success(f"✓ {saved_count} answer(s) saved!")
                else:
                    st.warning("No answers provided.")
        
        # Show saved answers
        saved_answers = {k: v for k, v in st.session_state.items() if k.startswith("clarification_answer_")}
        if saved_answers:
            st.info(f"📝 {len(saved_answers)} answer(s) saved for this session.")
    else:
        st.info("No clarification questions generated.")
    
    st.divider()
    
    # === RE-RUN WITH FEEDBACK ===
    st.subheader("🔄 Re-run Analysis with Your Feedback")
    
    # Collect all feedback from session state
    collected_feedback = []
    for key in st.session_state:
        if key.startswith("stored_feedback_"):
            fb_data = st.session_state[key]
            collected_feedback.append(fb_data)
    
    # Collect clarification answers (now stored as {question, answer} dicts)
    collected_answers = {}  # Maps question text -> answer
    for key, value in st.session_state.items():
        if key.startswith("clarification_answer_"):
            if isinstance(value, dict) and "question" in value:
                collected_answers[value["question"]] = value["answer"]
            else:
                # Legacy format: just a string answer (skip, can't map to question)
                pass
    
    has_feedback = bool(collected_feedback) or bool(collected_answers)
    
    if has_feedback:
        if collected_feedback:
            st.info(f"📝 {len(collected_feedback)} quality feedback item(s) collected.")
            for fb in collected_feedback:
                st.caption(f"• {fb['node']}: {fb['decision_type']} — {fb.get('reason', 'No reason provided')}")
        if collected_answers:
            st.info(f"💬 {len(collected_answers)} clarification answer(s) provided.")
            for q_text, ans in collected_answers.items():
                q_preview = q_text[:40] + "..." if len(q_text) > 40 else q_text
                ans_preview = ans[:50] + "..." if len(ans) > 50 else ans
                st.caption(f"• {q_preview}: {ans_preview}")
        
        if st.button("🔄 Re-run Pipeline with Feedback", type="primary"):
            with st.spinner("Re-running analysis with your corrections..."):
                # Import here to avoid circular dependency
                from src.state import UserFeedback
                
                # Create new state with feedback
                new_state = RunState(inputs=out.inputs)
                
                # Add quality feedback
                for fb_data in collected_feedback:
                    feedback = UserFeedback(
                        node=fb_data['node'],
                        decision_type=fb_data['decision_type'],
                        action=fb_data['action'],
                        affected_indices=list(range(fb_data.get('count', 0))),  # Simplified: affect all flagged rows
                        reason=fb_data.get('reason'),
                    )
                    new_state.user_feedback.append(feedback)
                
                # Copy questions with user answers (matched by question text)
                for q in out.user_questions:
                    q_copy = q.model_copy()
                    if q.question in collected_answers:
                        q_copy.answer = collected_answers[q.question]
                    new_state.user_questions.append(q_copy)
                
                # Re-run graph
                app_rerun = build_graph()
                out_rerun = app_rerun.invoke(new_state)
                
                if isinstance(out_rerun, dict):
                    out_rerun = RunState(**out_rerun)
                
                # Save new run
                rerun_id = out_rerun.config.run_id
                rerun_dir = os.path.join("artifacts", rerun_id)
                os.makedirs(rerun_dir, exist_ok=True)
                
                with open(os.path.join(rerun_dir, "state.json"), "w", encoding="utf-8") as f:
                    f.write(out_rerun.model_dump_json(indent=2))
                
                # Generate explainability log for re-run
                explainability_lines = [
                    f"EXPLAINABILITY LOG — Run ID: {rerun_id}",
                    f"Generated: {out_rerun.config.created_at}",
                    f"Re-run with {len(collected_feedback)} user feedback item(s)",
                    "=" * 80,
                    "",
                ]
                
                for entry in out_rerun.lineage:
                    explainability_lines.append(f"NODE: {entry.node.upper()}")
                    explainability_lines.append(f"Timestamp: {entry.timestamp}")
                    
                    if entry.transformations:
                        explainability_lines.append("Transformations:")
                        for t in entry.transformations:
                            explainability_lines.append(f"  • {t.get('operation', 'N/A')}: {t.get('description', 'No description')}")
                    
                    if entry.decisions:
                        explainability_lines.append("Decisions:")
                        for d in entry.decisions:
                            confidence = d.get('confidence', 'N/A')
                            if isinstance(confidence, float):
                                confidence = f"{int(confidence * 100)}%"
                            explainability_lines.append(f"  • {d.get('decision', 'N/A')} (confidence: {confidence})")
                            if d.get('caveat'):
                                explainability_lines.append(f"    └─ Caveat: {d['caveat']}")
                    
                    if entry.input:
                        explainability_lines.append(f"├─ Input: {entry.input.rows} rows, {entry.input.cols} cols")
                    if entry.output:
                        explainability_lines.append(f"└─ Output: {entry.output.rows} rows, {entry.output.cols} cols")
                    
                    explainability_lines.append("")
                
                with open(os.path.join(rerun_dir, "explainability.log"), "w", encoding="utf-8") as f:
                    f.write("\n".join(explainability_lines))
                
                # Update session state with new result and clear old feedback
                st.session_state.last_run_result = out_rerun
                # Clear stored feedback and answers
                for key in list(st.session_state.keys()):
                    if key.startswith("stored_feedback_") or key.startswith("clarification_answer_"):
                        del st.session_state[key]
                
                st.success(f"✅ Re-run complete! New Run ID: {rerun_id}")
                st.rerun()
    else:
        st.info("💡 No feedback provided yet. Answer clarification questions above or expand decision details to provide corrections.")
    
    st.divider()
    
    # === IMPROVED PROBLEM STATEMENT ===
    with st.expander("📝 Improved Problem Statement", expanded=False):
        st.write(out.improved_problem_statement or "No improvements suggested.")
    
    # === RAW DATA (COLLAPSED) ===
    with st.expander("🔧 Internal Questions (Planning)", expanded=False):
        st.json([q.model_dump() for q in out.internal_questions])
    
    with st.expander("📊 Raw Data Profile", expanded=False):
        if out.profile:
            st.json(out.profile.model_dump())
        else:
            st.warning("No profile generated.")
    
    with st.expander("📜 Audit Log", expanded=False):
        st.json(out.audit)
    
    # cleanup temp file
    if not st.session_state.test_mode:
        try:
            os.unlink(dataset_path)
        except Exception:
            pass
