import os
from typing import List, Dict
from state import ReportState

try:
    import pdfplumber
except Exception:
    pdfplumber = None

from pydantic import BaseModel
from core.llm_router import hybrid_llm_call_structured


class GostRequirement(BaseModel):
    parameter: str
    value: str
    context: str
    page: int | None = None
    source: str | None = None


class GostRequirements(BaseModel):
    requirements: List[GostRequirement]


def _extract_pdf_pages(path: str) -> List[Dict]:
    """Extract text by page and return list of chunks with metadata."""
    chunks: List[Dict] = []
    if pdfplumber:
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    chunks.append({"source": path, "page": i, "text": text, "metadata": {}})
            return chunks
        except Exception:
            pass

    # Fallback: very basic text extraction via PyPDF2 if installed
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, pg in enumerate(reader.pages, start=1):
                try:
                    text = pg.extract_text() or ""
                except Exception:
                    text = ""
                chunks.append({"source": path, "page": i, "text": text, "metadata": {}})
        return chunks
    except Exception:
        # last fallback: return empty list
        return []


def research_node(state: ReportState) -> dict:
    """Layout-aware RAG staging: extract pages from PDFs into `knowledge_chunks`.

    This node does NOT attempt to call an LLM; it prepares the structured
   , page-level data for downstream retrieval and formatting.
    """
    os.makedirs("assets/knowledge_base", exist_ok=True)
    files = []
    kb_dir = os.path.join("assets", "knowledge_base")
    if os.path.isdir(kb_dir):
        for fn in os.listdir(kb_dir):
            if fn.lower().endswith(".pdf"):
                files.append(os.path.join(kb_dir, fn))

    existing = list(state.get("knowledge_chunks", []))
    new_chunks: List[Dict] = []
    for path in files:
        try:
            chunks = _extract_pdf_pages(path)
            new_chunks.extend(chunks)
        except Exception as e:
            # record error but continue
            existing_errors = list(state.get("execution_errors", []))
            existing_errors.append(f"researcher: failed to parse {path}: {e}")
            return {"execution_errors": existing_errors}

    # Append newly extracted chunks to state (reducer semantics will concat)
    ctx = state.get("context_data", "")
    # Optionally, include a short index to context_data for backward compatibility
    if new_chunks:
        idx_lines = [f"[EXTRACTED] {os.path.basename(c['source'])}#p{c['page']}: {c['text'][:200]}" for c in new_chunks]
        ctx = ctx + "\n" + "\n".join(idx_lines)

    # Try to extract formal ГОСТ-style requirements from the newly extracted pages
    parsed_requirements: List[Dict] = []
    try:
        # Build a compact prompt that includes page indices and short excerpts
        examples = []
        for c in new_chunks:
            examples.append(f"PAGE={c['page']} SOURCE={os.path.basename(c['source'])}\n{c['text'][:800]}")

        prompt = (
            "Extract layout, table and formatting requirements following ГОСТ rules from the following page excerpts.\n"
            "Return a JSON object with a single key `requirements` which is an array of objects:\n"
            "{parameter: str, value: str, context: str, page: int, source: str}.\n"
            "Only return valid JSON that matches this schema.\n\n"
            "Page excerpts:\n" + "\n---\n".join(examples)
        )

        schema = GostRequirements
        parsed = hybrid_llm_call_structured(prompt, schema, task_type="gost_extraction")
        parsed_requirements = [r.dict() for r in parsed.requirements]
    except Exception:
        # If structured extraction fails, leave parsed_requirements empty but continue
        parsed_requirements = list(state.get("parsed_requirements", []))

    return {
        "context_data": ctx,
        "knowledge_chunks": new_chunks,
        "parsed_requirements": parsed_requirements,
        "execution_errors": list(state.get("execution_errors", [])),
    }
