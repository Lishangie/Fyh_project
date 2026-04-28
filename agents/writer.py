from state import ReportState

def writer_node(state: ReportState) -> dict:
    title = state.get("task_description", "Академический Отчет")
    ctx = state.get("context_data", "")
    draft = f"{title}\n\nРезюме:\nАвтоматически сгенерированный черновик (фрагмент):\n{ctx[:800]}"
    return {"draft_text": draft, "execution_errors": state.get("execution_errors", [])}
