from __future__ import annotations

import json

from ..llm import get_llm
from ..state import RunState, Question, LineageEntry, Profile
from ..tools import read_csv, basic_profile
from ..logging_config import setup_logging

logger = setup_logging(name="intake_node")

def intake_node(state: RunState) -> RunState:
    logger.info("Intake node started")
    llm = get_llm()
    
    # Read and profile dataset
    if not state.inputs.dataset_paths:
        logger.error("dataset_paths is required for intake")
        raise ValueError("dataset_paths is required for intake.")
    
    logger.info(f"Reading dataset from: {state.inputs.dataset_paths[0]}")
    df = read_csv(state.inputs.dataset_paths[0])
    logger.info(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns")
    
    if not state.profile:
        prof = basic_profile(df)
        state.profile = Profile(**prof)

    cols = state.profile.columns if state.profile else []
    logger.info(f"Columns: {cols}")
    
    # Check if we have previous questions with answers (re-run with feedback)
    answered_questions = [q for q in state.user_questions if q.answer]
    is_followup = len(answered_questions) > 0
    
    # Build prompt
    user_msg = (
        f"Problem statement: {state.inputs.problem_statement}\n"
        f"Audience: {state.inputs.audience}\n"
        f"Goal type: {state.inputs.goal_type}\n"
        f"Success metric: {state.inputs.success_metric}\n"
        f"Dataset columns: {', '.join(cols)}\n"
        f"Data dictionary: {state.inputs.data_dictionary or 'None'}\n"
        f"Target column: {state.inputs.target_column or 'None'}"
    )
    
    # Add previous Q&A if this is a follow-up run
    if is_followup:
        qa_context = "\n\nPrevious clarification questions and user answers:\n"
        for i, q in enumerate(answered_questions, 1):
            qa_context += f"Q{i}: {q.question}\nA{i}: {q.answer}\n\n"
        user_msg += qa_context
        logger.info(f"Including {len(answered_questions)} answered questions in prompt")
    
    # Adjust system prompt based on whether this is initial or follow-up
    if is_followup:
        system_content = (
            "You are a senior enterprise data scientist. "
            "The user has answered your previous clarification questions. "
            "Use their answers to REFINE the problem statement and generate FEWER, MORE SPECIFIC follow-up questions. "
            "Only ask questions that are still unclear after considering the user's answers. "
            "You MUST respond with VALID JSON ONLY. No markdown, no code blocks, no explanations. "
            "Return a JSON object with exactly these keys:\n"
            "{\n"
            '  "improved_problem_statement": "string (incorporate user answers into a clearer statement)",\n'
            '  "user_questions": [{"question": "string", "why": "string", "priority": "high|medium|low"}],\n'
            '  "internal_questions": [{"question": "string", "why": "string", "priority": "high|medium|low"}]\n'
            "}\n"
            "Generate 0-3 remaining user questions (only if still unclear). "
            "Generate 1-3 internal questions about modeling approach based on what you now know."
        )
    else:
        system_content = (
            "You are a senior enterprise data scientist. "
            "You MUST respond with VALID JSON ONLY. No markdown, no code blocks, no explanations. "
            "Return a JSON object with exactly these keys:\n"
            "{\n"
            '  "improved_problem_statement": "string",\n'
            '  "user_questions": [{"question": "string", "why": "string", "priority": "high|medium|low"}],\n'
            '  "internal_questions": [{"question": "string", "why": "string", "priority": "high|medium|low"}]\n'
            "}\n"
            "Ask 4-7 user questions that focus on decision context, data lineage, assumptions, risks, and success criteria. "
            "Ask 3-5 internal questions that clarify modeling approach, bias risks, and data limitations. "
            "Example response:\n"
            "{\n"
            '  "improved_problem_statement": "We need to identify key drivers of delivery delays...",\n'
            '  "user_questions": [{"question": "What is the target SLA?", "why": "Defines acceptable threshold", "priority": "high"}],\n'
            '  "internal_questions": [{"question": "Is this a classification problem?", "why": "Determines modeling approach", "priority": "high"}]\n'
            "}"
        )
    
    msg = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_msg}
    ]
    
    logger.info("Calling LLM for question generation...")
    raw = llm.invoke(msg).strip()
    logger.debug(f"LLM response length: {len(raw)} chars")

    try:
        logger.info("Parsing LLM JSON response...")
        obj = json.loads(raw)
        state.improved_problem_statement = obj.get("improved_problem_statement")
        
        new_user_questions = [Question(**q) for q in obj.get("user_questions", [])]
        new_internal_questions = [Question(**q) for q in obj.get("internal_questions", [])]
        
        if is_followup:
            # Keep unanswered questions from previous run
            unanswered_questions = [q for q in state.user_questions if not q.answer]
            # Add only NEW questions from LLM (avoid duplicates by checking question text)
            existing_texts = {q.question.lower().strip() for q in unanswered_questions}
            truly_new = [q for q in new_user_questions if q.question.lower().strip() not in existing_texts]
            
            # Final list: unanswered + new (answered questions are removed)
            state.user_questions = unanswered_questions + truly_new
            logger.info(f"Follow-up: kept {len(unanswered_questions)} unanswered, added {len(truly_new)} new questions, removed {len(answered_questions)} answered")
        else:
            state.user_questions = new_user_questions
        
        state.internal_questions = new_internal_questions
        logger.info(f"Total user questions: {len(state.user_questions)}, internal questions: {len(state.internal_questions)}")
        
        # Lineage: LLM success
        decisions = [{
            "decision": "llm_question_generation",
            "status": "success" if not is_followup else "followup_refinement",
            "is_followup": is_followup,
            "answered_questions": len(answered_questions),
            "unanswered_questions": len([q for q in state.user_questions if not q.answer]) if is_followup else 0,
            "new_questions_added": len(truly_new) if is_followup else len(new_user_questions),
            "total_user_questions": len(state.user_questions),
            "internal_questions": len(state.internal_questions),
            "confidence": 0.85 if is_followup else 0.8,
            "caveat": "Preserved unanswered questions, added new follow-ups based on user answers." if is_followup else "LLM-generated questions may need refinement based on domain expertise.",
        }]
        
    except Exception as e:
        logger.warning(f"LLM JSON parsing failed: {str(e)}, using fallback")
        # fallback
        state.improved_problem_statement = state.inputs.problem_statement
        state.user_questions = [
            Question(question="What decision will be made based on this output?",
                     why="Clarifies what matters for analysis and what to optimize.",
                     priority="high"),
            Question(question="What time window should the analysis cover?",
                     why="Prevents mixing incompatible periods and improves interpretability.",
                     priority="medium"),
        ]
        state.internal_questions = [
            Question(question="Are there obvious outcome/label columns that imply supervised learning?",
                     why="Determines Mode A vs Mode B path later.",
                     priority="high"),
        ]
        
        # Lineage: fallback used
        decisions = [{
            "decision": "llm_question_generation",
            "status": "fallback",
            "reason": str(e),
            "user_questions": len(state.user_questions),
            "internal_questions": len(state.internal_questions),
            "confidence": 0.5,
            "caveat": "Using fallback questions. LLM parsing failed. Questions are generic.",
        }]

    state.audit.append({"step": "intake", "status": "ok", "notes": "Generated questions and improved statement."})
    
    # Lineage entry for intake
    entry = LineageEntry(
        node="intake",
        transformations=[{
            "type": "llm_question_generation",
            "prompt_tokens": len(user_msg),
            "response_tokens": len(raw),
        }],
        decisions=decisions,
    )
    state.lineage.append(entry)
    
    state.stage = "intake_done"
    logger.info("Intake node completed successfully")
    return state
