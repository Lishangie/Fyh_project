from state import ReportState
from core.llm_router import hybrid_llm_call
from core.skill_loader import select_skills_for_task

def writer_node(state: ReportState) -> dict:
    """Generate draft_text using hybrid_llm_call and injected skills.

    The node updates `draft_text` and clears/updates `execution_errors`.
    """
    title = state.get("task_description", "Академический Отчет")
    context = state.get("context_data", "")
    knowledge = state.get("knowledge_chunks", [])

    # Build prompt with skills
    task_type = "gost_report"
    skills = select_skills_for_task(task_type)
    system_instructions = "\n\n".join(skills)

    prompt = (
        f"You are an expert technical writer for academic reports. Follow exact formatting rules.\n"
        f"SystemInstructions:\n{system_instructions}\n\n"
        f"Task: {title}\n\nContext: {context}\n\nKnowledge snippets: {str(knowledge[:5])}\n\n"
        "Generate a structured draft (sections: Abstract, Introduction, Methods, Results, Conclusion)."
    )

    try:
        resp = hybrid_llm_call(prompt, task_type)
        return {"draft_text": resp, "execution_errors": []}
    except Exception as e:
        errs = list(state.get("execution_errors", []))
        errs.append(f"writer_node error: {e}")
        return {"execution_errors": errs}
