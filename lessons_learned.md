# Lessons Learned

A knowledge base of errors, gotchas, and insights discovered during development. Organized by category for quick reference.

---

## 🔴 Coding & Syntax

### Pandas Date Parsing Warning
**Issue**: `pd.to_datetime()` without explicit format raises `UserWarning` about date format inference.  
**Solution**: Use `format="mixed"` parameter when dates have varied formats.  
**Example**: `pd.to_datetime(df[col], errors="coerce", format="mixed")`

### Streamlit Session State Key Collisions
**Issue**: Using numeric indices (e.g., `answer_1`, `answer_2`) as widget keys causes answers to persist incorrectly when questions change.  
**Solution**: Use content-based keys (hash of question text) to tie state to specific questions.  
**Example**: `key=f"answer_{hashlib.md5(question.encode()).hexdigest()[:8]}"`

### Pydantic V1 + Python 3.14 Incompatibility
**Issue**: `langchain-core` imports Pydantic V1 which doesn't support Python 3.14+.  
**Solution**: Use Python 3.13 or lower until LangChain updates.  
**Command**: `poetry env use python3.13 && poetry install`

---

## 🟠 Debugging & Environment

### Duplicate Log Folders
**Issue**: Logs appearing in both `logs/` and `code/logs/` due to relative path resolution.  
**Solution**: Use absolute paths or ensure consistent working directory. Keep only root `logs/`.

### Poetry Virtual Environment Switching
**Issue**: Poetry caches virtualenvs by Python version. Switching requires explicit path.  
**Command**: `poetry env use /opt/homebrew/bin/python3.13`

---

## 🔵 Conceptual & Architecture

### Streamlit Forms Require Explicit Submit
**Issue**: `st.text_area()` inside `st.form()` won't persist values without `st.form_submit_button()`.  
**Solution**: Always include submit button in forms; handle submission state explicitly.

### LLM Follow-up Context Must Be Explicit
**Issue**: Re-running pipeline with user answers doesn't automatically include them in LLM prompt.  
**Solution**: Explicitly detect follow-up runs (`len(answered_questions) > 0`) and inject Q&A context into prompt.

### Question Preservation on Re-run
**Issue**: After re-run, old answered questions disappear and only new questions show.  
**Solution**: Preserve unanswered questions from previous run, filter out answered ones, add only truly new questions.
