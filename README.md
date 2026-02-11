# DataAnalystAgentFramework

Autonomous data analysis agent that mimics senior analyst workflows. Produces complete analysis reports with radical transparency at every step.

## Quick Start

```bash
# Install dependencies
poetry install

# Start Ollama and pull model
ollama pull llama3.1:8b

# Run Streamlit app
poetry run streamlit run code/app/streamlit_app.py

# Run with test config (auto-populate fields)
TEST_CONFIG=code/tests/test_config.json poetry run streamlit run code/app/streamlit_app.py
```

---

## Setup

### Dependencies (Poetry)
```bash
poetry install        # Install all dependencies
poetry add <package>  # Add new dependency
```

**Core**: numpy, pandas, pyarrow, pydantic, scikit-learn, streamlit  
**Agent**: langgraph, langchain, langchain-ollama

### LLM (Ollama)
```bash
ollama pull llama3.1:8b   # Download model
ollama serve              # Start server (default: http://localhost:11434)
```

---

## Run Commands

| Command | Description |
|---------|-------------|
| `poetry run streamlit run code/app/streamlit_app.py` | Start Streamlit UI |
| `poetry run python code/tests/test_runner.py` | Run all tests (single iteration) |
| `poetry run python code/tests/test_runner.py --auto-answer` | Run tests with auto-answer loop |
| `poetry run python -c "from code.src.graph import main; main()"` | Visualize graph |

---

## Project Structure

```
code/
├── app/
│   └── streamlit_app.py      # UI: upload, inputs, graph invocation, artifacts
├── src/
│   ├── state.py              # Pydantic models: RunState, Inputs, Profile, Question
│   ├── graph.py              # LangGraph: build_graph(), profile → target → intake
│   ├── llm.py                # LLM client: get_llm() (Ollama)
│   ├── tools.py              # Data utils: read_csv(), advanced_profile(), detect_pii_columns()
│   ├── logging_config.py     # Logging: setup_logging()
│   └── nodes/
│       ├── profile.py        # Profile node: data profiling, quality scoring, PII detection
│       ├── target.py         # Target node: candidate label scoring
│       └── intake.py         # Intake node: LLM question generation, Q&A loop
└── tests/
    ├── test_runner.py        # Automated test runner with --auto-answer
    ├── TEST_STRATEGY.md      # Test documentation
    ├── test_config.json      # Stress test (205 rows, data quality issues)
    ├── test_config_baseline.json   # Baseline (10 rows, clean)
    ├── test_config_exploratory.json # No target specified
    └── data/
        ├── delivery_operations.csv
        ├── delivery_operations_complex.csv
        └── delivery_operations_complex.py
```

**Other folders:**
- `artifacts/<run_id>/` — Pipeline outputs (state.json, explainability.log)
- `logs/` — Application logs (one file per node)

---

## Pipeline Flow

```
Profile Node → Target Detect Node → Intake Node → (Feedback Loop) → END
```

1. **Profile Node** — Loads CSV, computes stats, detects PII, flags quality issues
2. **Target Detect Node** — Scores candidate target columns if not user-provided
3. **Intake Node** — Calls LLM to generate clarification questions, refines problem statement
4. **Feedback Loop** — User answers questions, re-runs intake until no questions remain

---

## Testing

### Automated Tests
```bash
# Run all test configs (single iteration)
poetry run python code/tests/test_runner.py

# Auto-answer questions until none remain
poetry run python code/tests/test_runner.py --auto-answer

# Run specific config
poetry run python code/tests/test_runner.py --config code/tests/test_config.json --auto-answer --max-iterations 3
```

### Test Configs
| Config | Dataset | Rows | Purpose |
|--------|---------|------|---------|
| `test_config.json` | Complex | 205 | Stress test (missing, outliers, PII) |
| `test_config_baseline.json` | Clean | 10 | Happy path |
| `test_config_exploratory.json` | Complex | 205 | No target specified |

See [code/tests/TEST_STRATEGY.md](code/tests/TEST_STRATEGY.md) for details.

---

## Key Features

- **Radical Transparency** — Every transformation tracked in lineage with before/after snapshots
- **Decision Explanations** — Each decision includes confidence score + caveat
- **PII Detection** — Pattern-based detection with masked samples
- **Data Quality Scoring** — Missing %, duplicates, outliers, impossible values
- **Auto-Answer Testing** — LLM generates answers for automated Q&A loop testing
- **Feedback Loop** — Users can disagree with decisions and re-run pipeline

---

## Artifacts

Each run produces:
```
artifacts/<run_id>/
├── state.json           # Full RunState (inputs, profile, questions, lineage)
└── explainability.log   # Human-readable audit log (tree format)
```
