# Copilot Instructions for DataAnalystAgentFramework

**See [README.md](../README.md) for setup commands, dependencies, and basic run instructions.**

---

## Project Overview

Autonomous data analysis agent that mimics senior analyst workflows. Not a chatbot—produces complete analysis reports with transparency at every step.

**Core principle**: Radical transparency with auditable lineage tracking.

---

## Architecture: LangGraph Multi-Agent Pipeline

**Graph Flow**: `profile → target_detect → intake → END`

1. **profile_node** - Loads CSV, profiles data, detects PII-like columns, flags quality issues (duplicates, outliers, missing values)
2. **target_detect_node** - Scores candidate target columns using heuristics (boolish, label hints, cardinality)
3. **intake_node** - Calls LLM to generate clarification questions and improve problem statement

**Key file**: [code/src/graph.py](../code/src/graph.py) - `build_graph()` defines the flow

---

## State Management Pattern

**Central model**: `RunState` in [code/src/state.py](../code/src/state.py)

```python
RunState(
    config: RunConfig,           # run_id, timestamps, PII patterns
    inputs: Inputs,               # dataset paths, problem statement, audience, goal_type, success_metric
    profile: Profile,             # row/col counts, dtypes, missing %, sample rows
    user_questions: list[Question],
    internal_questions: list[Question],
    improved_problem_statement: str,
    lineage: list[LineageEntry],  # CRITICAL: tracks data transformations
    audit: list[dict],            # Simple log entries
    user_feedback: list[UserFeedback],  # User corrections to decisions
    stage: Literal["init", "intake_done", "profile_done", "failed"]
)
```

**State is passed through graph nodes and mutated in place.**

---

## Lineage & Transparency Pattern

Every node appends a `LineageEntry` to track transformations:

```python
LineageEntry(
    node="profile",
    timestamp="2026-02-11T10:15:00",
    input: LineageSnapshot,      # Before: rows, cols, dtypes, sample
    transformations: [           # What changed
        {"type": "load_csv", "path": "...", "rows_loaded": 205}
    ],
    output: LineageSnapshot,     # After: rows, cols, dtypes, sample
    decisions: [                 # Decision with confidence + caveat
        {
            "decision": "outliers_detected",
            "rows_affected": 12,
            "examples": [{...}, {...}],
            "confidence": 0.8,
            "caveat": "Using IQR method. May be valid extreme values."
        }
    ]
)
```

**Key pattern**: Every decision MUST include:
- `confidence` (0.0-1.0)
- `caveat` (explain uncertainty, sample size concerns, limitations)
- `examples` (concrete data rows when flagging issues)

---

## Artifact Persistence

After each run:
```
artifacts/<run_id>/
├── state.json              # Full RunState dump
└── explainability.log      # Human-readable tree format of lineage
```

**Explainability log format**:
```
[timestamp] PROFILE NODE
├─ Transformations: load_csv (205 rows)
├─ Decisions:
│  ├─ duplicates_detected (confidence: 100%)
│  │  └─ 💡 4 duplicate rows found. Review before analysis.
│  └─ outliers_detected (confidence: 80%)
│     └─ 💡 Using IQR method. May be valid extreme values.
└─ Output: 205 rows, 14 cols
```

Generated in [code/app/streamlit_app.py](../code/app/streamlit_app.py) after graph execution.

---

## Testing Pattern

**Test mode**: Set `TEST_CONFIG=code/tests/test_config.json` env var before running Streamlit. Auto-populates UI fields.

**Test configs**:
- `test_config_baseline.json` - Clean dataset (10 rows)
- `test_config.json` - Complex dataset (205 rows, PII, outliers, duplicates)
- `test_config_exploratory.json` - No target specified

**Validation**: Always click "Run Phase 1" button in UI. Assertions read from `artifacts/<run_id>/state.json`.

**Run all tests**: `poetry run python code/tests/test_runner.py`

---

## Feedback Loop Pattern (Implemented)

Users can override agent decisions via UI:

1. **LineageEntry displays decision** with examples in Streamlit expander
2. **User provides feedback** via checkbox + text input (e.g., "These outliers are valid")
3. **Feedback stored** in `state.user_feedback` as `UserFeedback` model
4. **Re-run button** creates new RunState with feedback applied
5. **Nodes respect feedback** - profile_node filters out user-approved rows from quality issues

**Example**: User disagrees with outlier detection → provides reason → re-runs → outliers excluded from analysis.

---

## Logging Convention

**Pattern**: File-only by default, optional console output.

```python
from src.logging_config import setup_logging

logger = setup_logging(name="my_node")  # Logs to logs/my_node.log
logger.info("Processing...")
```

Set `console_output=True` for debugging. Logs stored in `logs/` directory.

---

## LLM Integration

**Current**: Ollama local models via `langchain-ollama`.

```python
from src.llm import get_llm

llm = get_llm(model="llama3.1:8b", temperature=0.2)
llm.invoke(messages)  # Returns JSON (format="json" enforced)
```

**Pattern**: All LLM calls in intake_node use structured prompts expecting JSON output with fallback handling.

---

## What's NOT Implemented Yet

- EDA agent (charts, statistical tests)
- Modeling agent (baseline models, error analysis)
- Verifier agent (catches statistical errors)
- Multi-round feedback loops (currently 1 round)

These are documented in [IMPLEMENTATION_ROADMAP.md](../IMPLEMENTATION_ROADMAP.md) but not present in code.

---

## Key Conventions

- **snake_case** for all Python identifiers
- **Pydantic models** for all state/config/data structures
- **Type hints required** (Python 3.12+) - all functions must have return type annotations
- **No print statements** - use logging (exception: CLI main() functions for user feedback)
- **All data transformations** must append to `state.lineage`
- **All decisions** must include `confidence` (0.0-1.0) + `caveat` (string explaining limitations)

---

## Global Instruction Compliance

This project follows global Copilot instructions. Key compliance items:

- **`lessons_learned.md`** — Knowledge base of errors/gotchas in root directory. Update when bugs are fixed.
- **`.github/ai_scripts/`** — Directory for script-first edits (Python scripts that modify files programmatically)
- **Planning protocol** — Multi-step tasks require plan approval before execution
- **Clarification protocol** — Propose 3-5 options with recommended default for ambiguous requirements
