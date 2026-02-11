# Implementation Roadmap: Enhanced Intake & Analyst Feedback Loop

## Core Principle: Radical Transparency
**Every action on data must be visible, explainable, and reversible.**
Users must never wonder "what happened to my data?" — they should see the exact transformation at each step.

---

## Phase 0: Transparency & Data Lineage ✅ DONE

### Data Audit Trail
- [x] **Capture state at each node**
  - Before: row count, shape, dtypes, sample rows
  - Transformation: what changed and why
  - After: row count, shape, dtypes, sample rows
  - Save to: `artifacts/<run_id>/state.json`
  - Implementation: `LineageEntry`, `LineageSnapshot` models in state.py

- [x] **Lineage JSON structure**
  ```python
  {
    "node": "profile",
    "timestamp": "2026-02-02T09:15:14",
    "input": {
      "rows": 10,
      "cols": 14,
      "sample": [{...}, {...}],
      "dtypes": {...}
    },
    "transformations": [
      {"type": "load_csv", "path": "delivery_operations.csv", "rows_loaded": 10}
    ],
    "output": {
      "rows": 10,
      "cols": 14,
      "sample": [{...}, {...}],
      "profile": {...}
    },
    "decisions_made": [
      {"decision": "PII check passed", "flagged_columns": [], "action": "proceed"}
    ]
  }
  ```

### Visual Data Lineage Dashboard (Streamlit)
- [x] **Timeline view**
  - Vertical flow: `Upload → Profile → Target Detect → Intake → (Feedback Loop) → Analysis`
  - At each step: show before/after stats (rows, cols, nulls, types)
  - Expandable detail: see sample rows at each stage
  - Implementation: Expandable sections with metrics, transformations, decisions, samples
  
- [x] **Data diff viewer**
  - Side-by-side comparison of data pre/post each transformation
  - Highlight what changed (e.g., rows removed, columns retyped, nulls filled)
  - Interactive: shows row/col delta when data changes
  - Implementation: Metrics with delta indicators
  
- [x] **Metrics tracking**
  ```
  Profile Node:
  ✓ Rows: 10 (unchanged)
  ✓ Cols: 14 (unchanged)
  ✓ Missing: 2.1% avg (within acceptable)
  ✓ Duplicates: 0 found
  ✓ PII: 0 suspicious columns
  → Ready to proceed
  ```

### Decision Explanation
- [x] **Every decision must have a "why"**
  - Why was this column flagged as PII? → "Matched pattern: 'email' in column name"
  - Why are we suggesting this target? → "Score: 7 (boolish=5, strong_hint=2). Only 2 unique values"
  - Why are we asking this question? → "Data source unclear; critical for understanding potential bias"
  - Implementation: `decisions` list in LineageEntry (all nodes)
  
- [x] **Confidence & caveats**
  - "I'm 95% confident this is a target column (sample size: 10 rows, concern: small n)"
  - "PII check flagged 'customer_name' (pattern match, recommend manual review)"
  - "This question is critical to answer; analysis is unreliable without it"
  - Implementation: confidence scores (0-1) + caveat strings in decisions

### Explainability Logs
- [x] **Human-readable audit log**
  - Implementation: `artifacts/<run_id>/explainability.log`
  - Tree-structured format showing each node's transformations and decisions
  - Includes confidence scores and caveats
  ```
  [09:15:14] PROFILE NODE
  ├─ Loaded CSV: delivery_operations.csv (10 rows, 14 cols)
  ├─ Data Quality:
  │  ├─ Missing values: 2.1% average (acceptable)
  │  ├─ Duplicates: 0 (clean)
  │  └─ Outliers: 3 detected in 'shipping_cost_usd' (top 1%)
  ├─ PII Check:
  │  ├─ Scanned 14 columns against 7 PII patterns
  │  ├─ 'order_id', 'plant', 'region' → safe
  │  └─ 'customer_name' ⚠ flagged (pattern: "name" in column)
  └─ ✓ Passed: Ready for target detection
  
  [09:15:14] TARGET DETECT NODE
  ├─ Scanned 14 candidate columns
  ├─ Scoring logic:
  │  ├─ Exclude: 'order_id' (ID hint), 'order_date', 'ship_date' (date hint)
  │  ├─ Candidates: 'late_delivery' (score=7), 'priority_flag' (score=5)
  │  └─ Recommendation: 'late_delivery' (boolish + strong_label_hint)
  ├─ User provided: late_delivery ✓
  └─ ✓ Target confirmed: late_delivery
  ```

### Data Sampling & Examples
- [x] **Always show concrete examples**
  - "We detected 3 rows with missing shipping_cost:" `[{order_id: 123, ...}, ...]`
  - "Your data has 2 duplicate rows (identical across all columns):" `[{...}, {...}]`
  - "Sample of 'late_delivery' values:" `{0: 7 rows, 1: 3 rows}` with examples
  - Implementation: `detect_data_quality_issues()` in tools.py, displayed in lineage
  
- [x] **Stratified sampling**
  - Show examples from each category/bin
  - Show edge cases (min, max, median values) - outlier detection

---

## Phase 1: Mature Question Generation ✅ DONE

### Profile Node Enhancements
- [x] **Advanced profiling metrics**
  - Data quality score (missing %, duplicates, outliers)
  - Temporal patterns (date ranges, seasonality indicators)
  - Cardinality analysis (categorical complexity)
  - Statistical signatures (skewness, kurtosis, multimodality hints)
  - Implementation: `advanced_profile()` in tools.py, `data_quality_score` decision in profile_node
  
- [x] **Smarter PII & sensitivity detection**
  - Pattern-based detection (email, phone, IP regex)
  - Domain-specific flags (financial, health, personal identifiers)
  - Cross-column dependency analysis (first name + last name = PII) - partial
  - Implementation: `detect_pii_columns()` in tools.py with masked samples

### Intake Node Enhancements
- [x] **Senior analyst-grade question generation**
  - Business context questions (stakeholder alignment, decision framework)
  - Data lineage questions (source, collection method, update frequency)
  - Assumption validation (implicit filters, historical changes)
  - Risk/bias questions (sampling bias, survivorship bias, data drift)
  - Success criteria refinement (statistical vs. business significance)
  - Implementation: Enhanced system prompt in intake_node
  
- [x] **Question classification & prioritization**
  - Critical (blocks analysis) → high priority
  - High (impacts interpretation) → high/medium priority
  - Medium (nice-to-have context) → medium priority
  - Low (advanced optimizations) → low priority
  - Implementation: Question model already has priority field
  
- [x] **LLM prompt engineering**
  - System prompt: "You are a senior enterprise data scientist..."
  - Few-shot examples of mature questions - partial (1 example)
  - Chain-of-thought reasoning for question selection - not yet
  - Structured output: `{improved_problem_statement, user_questions, internal_questions}`

---

## Phase 2: Feedback Collection & Storage ✅ DONE

- [x] **User response capture UI**
  - Checkbox for each decision to disagree
  - Text input for user reasoning
  - Implementation: Streamlit feedback UI in lineage expanders
  
- [x] **State extension: UserFeedback model**
  - Implementation: UserFeedback model in state.py
  - Fields: node, decision_type, action, affected_indices, reason, timestamp
  
- [x] **Persist feedback in artifacts**
  - Save user corrections in state.user_feedback
  - Tracked in state.json

---

## Phase 3: Re-evaluation Loop ✅ DONE

- [x] **Feedback-aware nodes**
  - Profile node respects user feedback about outliers/duplicates
  - Filters out user-approved rows from quality issues
  
- [x] **Re-run button**
  - "Re-run Pipeline with Feedback" button
  - Creates new RunState with feedback applied
  - Saves new artifact with updated run_id

- [x] **Question key stability**
  - Questions keyed by content hash (not index)
  - Answers persist correctly across re-runs
  - Unanswered questions preserved + new questions added
  
- [ ] **Decision logic: Continue analysis vs. Ask more questions**
  ```python
  # Intake node returns one of:
  {
    "action": "proceed_to_analysis",
    "confidence": 0.92,
    "summary": "Questions answered, assumptions validated"
  }
  OR
  {
    "action": "ask_follow_up",
    "follow_up_questions": [...],
    "rationale": "Need clarity on data collection process before proceeding"
  }
  ```

- [ ] **Graph branching based on feedback**
  - After feedback intake: `[ask_more] -> [intake_round_2]` or `[proceed] -> [eda_node]`
  - Track iteration count (prevent infinite loops, max 3 rounds?)

---

## Phase 4: Automated Testing ✅ DONE

- [x] **Test runner with auto-answer**
  - `poetry run python code/tests/test_runner.py` — run all tests
  - `--auto-answer` — LLM generates answers, loops until no questions
  - `--config <path>` — run single config
  - `--max-iterations N` — limit loop iterations (default: 5)
  
- [x] **Auto-answer logic**
  - LLM generates plausible domain-expert answers
  - Context includes problem statement, audience, goal, success metric
  - Answers are 1-3 sentences, specific and actionable

- [x] **Test configs**
  - `test_config.json` — stress test (205 rows, data quality issues)
  - `test_config_baseline.json` — baseline (10 rows, clean)
  - `test_config_exploratory.json` — no target specified

---

## Phase 4.5: Code Quality & Bug Fixes 🔲 NOT STARTED

### High Priority (Bugs/Regressions)

- [ ] **Fix test_runner.py auto-answer capability**
  - Current: 140 lines, missing `--auto-answer` flag implementation
  - Needed: Restore LLM auto-answer loop with `--max-iterations`
  - Location: `code/tests/test_runner.py`

- [ ] **Fix or remove `generate_test_results()` in streamlit_app.py**
  - Issue: Writes to `TEST_RESULTS.md` which was deleted
  - Options: Remove the call entirely, or fix path to valid location
  - Location: `code/app/streamlit_app.py` line ~620

- [ ] **Complete exception handler in profile_node**
  - Issue: Exception block at line ~137 appears truncated
  - Location: `code/src/nodes/profile.py`

### Medium Priority (Type Hints & Docstrings)

- [ ] **Add return type hint to `get_llm()`**
  - Current: `def get_llm(model: str = "llama3.1:8b", temperature: float = 0.2):`
  - Should be: `def get_llm(...) -> OllamaLLM:`
  - Location: `code/src/llm.py`

- [ ] **Add docstrings to tools.py functions**
  - Missing on: `advanced_profile()`, `detect_pii_columns()`, `detect_data_quality_issues()`
  - Format: Google-style docstrings with Args/Returns/Raises
  - Location: `code/src/tools.py`

- [ ] **Move `import hashlib` to top of streamlit_app.py**
  - Issue: Currently imported inside function body (~line 158)
  - Convention: All imports at module top
  - Location: `code/app/streamlit_app.py`

### Low Priority (Code Quality)

- [ ] **Add `__all__` exports to node modules**
  - Files: `profile.py`, `intake.py`, `target.py`
  - Purpose: Explicit public API for each module
  - Location: `code/src/nodes/`

- [ ] **Consolidate duplicate import patterns**
  - Issue: Some files import `logging` + `setup_logging`, could simplify
  - Location: Various node files

- [ ] **Add input validation to graph entry point**
  - `build_graph()` should validate RunState on entry
  - Fail fast with clear error messages for missing required fields
  - Location: `code/src/graph.py`

### Testing Improvements

- [ ] **Add unit tests for tools.py functions**
  - `advanced_profile()` — test with edge cases (empty df, single row, all nulls)
  - `detect_pii_columns()` — test pattern matching accuracy
  - `detect_data_quality_issues()` — test outlier/duplicate detection
  - Location: New file `code/tests/test_tools.py`

- [ ] **Add integration test for feedback loop**
  - Simulate user feedback → re-run → verify state changes
  - Location: `code/tests/test_feedback_loop.py`

- [ ] **Add test for explainability.log format**
  - Parse generated log, verify structure
  - Location: `code/tests/test_explainability.py`

### Documentation

- [ ] **Update lessons_learned.md with test_runner regression**
  - Document: "File edits may not persist if session interrupted"
  - Mitigation: Always verify changes with `wc -l` or `cat`

- [ ] **Add CONTRIBUTING.md**
  - Code style guide
  - Testing requirements before PR
  - Commit message conventions

- [ ] **Add architecture diagram to README.md**
  - Mermaid diagram of LangGraph flow
  - State transitions and node responsibilities

---

## Phase 5: Senior Analyst Reasoning 🔲 NOT STARTED

- [ ] **Structured analytical reasoning layer**
  - Hypothesis generation (what would a 10+ year analyst look for?)
  - Red flags & validation checks (missing data, unusual patterns, contradictions)
  - Confidence & uncertainty quantification per finding
  
- [ ] **Senior analyst perspective prompts**
  - "Based on my 10+ years of experience in [domain], here are the likely pain points..."
  - Acknowledge what we DON'T know and why it matters
  - Suggest data collection/validation steps
  - Warn about common pitfalls in [industry/domain]
  
- [ ] **Assumption documentation**
  - Explicit list of what we're assuming to be true
  - Rationale for each assumption
  - What we'd need to see to overturn each assumption

---

## Phase 6: UI & Workflow Integration 🔲 NOT STARTED

- [ ] **Streamlit multi-page flow**
  - Page 1: Input collection (existing)
  - Page 2: Initial questions display + feedback form
  - Page 3: Re-evaluation results (proceed or more questions)
  - Page 4: Analysis output (when ready)
  
- [ ] **Session state management**
  - Track current feedback round (round 1, 2, 3)
  - Store accumulated feedback across rounds
  - Show feedback history (what user answered before)
  
- [ ] **Progress indicator**
  - Show "Gathering clarifications: Round 1/3"
  - Display which questions have been answered

---

## Phase 7: Output & Artifacts 🔲 NOT STARTED

- [ ] **Artifact structure**
  ```
  artifacts/<run_id>/
  ├── state.json (final state)
  ├── intake_summary.json (questions, answers, decisions)
  ├── feedback_round_1.json (user responses)
  ├── feedback_round_2.json (if applicable)
  ├── reasoning_log.json (analyst reasoning, assumptions, confidence)
  └── analysis_output.json (when ready)
  ```

- [ ] **Audit trail**
  - Track every question asked, answer received, decision made
  - LLM call history with prompts & responses
  - Timing: when did user answer, how long did analysis take?

---

## Phase 8: EDA & Modeling Agents 🔲 NOT STARTED

- [ ] **EDA agent**
  - Charts (histograms, scatter plots, correlation matrices)
  - Statistical tests (normality, independence, significance)
  - Correlation analysis (feature relationships)

- [ ] **Modeling agent**
  - Baseline models (logistic regression, decision tree)
  - Error analysis (where does the model fail?)
  - Feature importance ranking

- [ ] **Verifier agent**
  - Catches statistical errors
  - Validates assumptions
  - Cross-checks findings

---

## Nice-to-Have (Future)

- [ ] **Domain-specific question templates**
  - E-commerce: "What's your customer acquisition cost model?"
  - Logistics: "Do you have seasonal patterns we should account for?"
  - Finance: "Are there regulatory compliance requirements?"
  
- [ ] **Confidence scoring**
  - Per-question: how confident is the analyst in understanding the problem?
  - Per-answer: how confident is the user in their response?
  
- [ ] **Multi-turn conversation UI**
  - Chat-like interface for feedback collection
  - Follow-up probes ("You said X, can you elaborate on Y?")
  
- [ ] **Visual feedback summarization**
  - Infographics: "Here's what we understood from your answers"
  - Comparison: "Here's how this changes our initial hypothesis"

---

## Cross-Cutting Concern: Transparency & Explainability

**Every phase must include:**
1. **What happened** - concrete data state before/after
2. **Why it happened** - decision logic with confidence scores
3. **What changed** - visual diff of transformed data
4. **What's next** - clear indication of next step

**All logging should answer:**
- "If I review this, will I understand exactly what happened to my data?"
- "Can I see examples of what was changed/removed/flagged?"
- "Do I understand why this decision was made?"
- "What assumptions are we making that might be wrong?"

**User-facing transparency (Streamlit):**
- Expandable "Data Journey" timeline (each step shows before/after)
- "Why did we..." pop-ups (click any decision to see reasoning)
- "Download audit log" button (JSON/CSV export)
- Data sample viewer (raw, filtered, transformed side-by-side)

---

## Summary of Core Changes

1. **Intake node**: Mature question generation + senior analyst framing
2. **Feedback node**: Collect user responses → decide proceed/ask-more
3. **Re-eval node**: Process feedback + generate next-step output
4. **Graph branching**: Linear flow → conditional flow based on feedback
5. **UI flow**: Multi-page, rounds of clarification
6. **State**: Add UserFeedback list, iteration tracking, assumptions
7. **Artifacts**: Rich documentation of entire reasoning chain
8. **Testing**: Automated test runner with LLM auto-answer capability
