import os
from state import ReportState

def research_node(state: ReportState) -> dict:
    os.makedirs("assets/knowledge_base", exist_ok=True)
    os.makedirs("artifacts", exist_ok=True)
    found = []
    kb_dir = os.path.join("assets", "knowledge_base")
    if os.path.isdir(kb_dir):
        for fn in os.listdir(kb_dir):
            if fn.lower().endswith(".pdf"):
                found.append(os.path.join(kb_dir, fn))
    ctx = state.get("context_data", "")
    ctx += "\n[researcher] indexed_files: " + ", ".join(found)
    return {"context_data": ctx, "execution_errors": state.get("execution_errors", [])}
