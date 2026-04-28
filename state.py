from typing import TypedDict, List, Annotated
import operator

class ReportState(TypedDict, total=False):
    task_description: str
    context_data: str
    draft_text: str
    artifact_paths: Annotated[List[str], operator.add]
    dynamic_tables: Annotated[List[dict], operator.add]
    execution_errors: List[str]
    human_feedback: str
