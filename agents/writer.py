from state import ReportState
from core.llm_router import hybrid_llm_call, hybrid_llm_call_structured
from core.skill_loader import select_skills_for_task
from pydantic import BaseModel
from typing import List


class DataTable(BaseModel):
    name: str
    columns: List[str]
    rows: List[dict]


class WriterOutput(BaseModel):
    draft_text: str
    dynamic_tables: List[DataTable] = []


def writer_node(state: ReportState) -> dict:
    """Generate both `draft_text` and structured `dynamic_tables` via LLM.

    Uses structured output to ensure `dynamic_tables` conforms to the
    `data_tables` context variable expected by `docxtpl` templates.
    """
    title = state.get("task_description", "Академический Отчет")
    context = state.get("context_data", "")
    knowledge = state.get("knowledge_chunks", [])
    parsed_reqs = state.get("parsed_requirements", [])

    # Build prompt with skills
    task_type = "gost_report"
    skills = select_skills_for_task(task_type)
    system_instructions = "\n\n".join(skills)

    prompt = (
        f"You are an expert technical writer for academic reports. Follow exact formatting rules.\n"
        f"SystemInstructions:\n{system_instructions}\n\n"
        f"Task: {title}\n\nContext: {context}\n\nParsedRequirements: {parsed_reqs}\n\n"
        f"Knowledge snippets (first 5): {str(knowledge[:5])}\n\n"
        "Produce a JSON object matching the schema: {draft_text: str, dynamic_tables: [{name, columns, rows}]}.\n"
        "`dynamic_tables` should contain numerical summaries, comparative analyses, or any tabular data extracted from knowledge snippets."
    )

    try:
        # Prefer structured output to ensure parseability
        out = hybrid_llm_call_structured(prompt, WriterOutput, task_type)
        # Append/merge dynamic tables into state (reducer semantics handled by graph)
        tables = [t.dict() for t in getattr(out, "dynamic_tables", [])]
        return {"draft_text": out.draft_text, "dynamic_tables": tables, "execution_errors": []}
    except Exception as e:
        # Fallback to text response and leave dynamic_tables untouched
        try:
            resp = hybrid_llm_call(prompt, task_type)
            return {"draft_text": resp, "execution_errors": []}
        except Exception as e2:
            errs = list(state.get("execution_errors", []))
            errs.append(f"writer_node error: {e} | fallback error: {e2}")
            return {"execution_errors": errs}
