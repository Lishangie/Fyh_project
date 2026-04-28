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
    # Extracted knowledge chunks from PDFs: list of dicts {source, page, text, metadata}
    knowledge_chunks: Annotated[List[dict], operator.add]
    # Parsed, structured ГОСТ requirements extracted from documents
    parsed_requirements: Annotated[List[dict], operator.add]
    # Retry counters per node name
    retry_counts: dict
    # Temporary field used by error resolver to indicate routing after repair
    last_resolution: str
