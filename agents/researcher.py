import os
import json
from typing import List, Dict, Optional
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


# Optional imports for advanced RAG
try:
    from langchain_community.vectorstores import Chroma as ChromaVec
    from langchain_community.embeddings import HuggingFaceEmbeddings
except Exception:
    try:
        from langchain.vectorstores import Chroma as ChromaVec
        from langchain.embeddings import HuggingFaceEmbeddings
    except Exception:
        ChromaVec = None
        HuggingFaceEmbeddings = None

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except Exception:
    RecursiveCharacterTextSplitter = None


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

    # Context accumulation: short index lines for human inspection
    ctx = state.get("context_data", "")

    # If Chroma is available, build or load a persistent vector DB and perform
    # a semantic search for the task description to avoid context overflow.
    chroma_dir = os.path.join("chroma_db")
    os.makedirs(chroma_dir, exist_ok=True)
    ingested_index_path = os.path.join(chroma_dir, "ingested.json")
    try:
        ingested_index = {}
        if os.path.exists(ingested_index_path):
            with open(ingested_index_path, "r", encoding="utf8") as f:
                ingested_index = json.load(f)
    except Exception:
        ingested_index = {}

    collected_chunks: List[Dict] = []

    if ChromaVec and HuggingFaceEmbeddings and RecursiveCharacterTextSplitter:
        # instantiate embeddings (local HF) or fallback to OpenAIEmbeddings if necessary
        try:
            hf_model = os.environ.get("HUGGINGFACE_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            embeddings = HuggingFaceEmbeddings(model_name=hf_model)
        except Exception:
            try:
                from langchain.embeddings import OpenAIEmbeddings
                embeddings = OpenAIEmbeddings()
            except Exception:
                embeddings = None

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200) if RecursiveCharacterTextSplitter else None

        collection_name = os.environ.get("CHROMA_COLLECTION", "fyh_collection")

        # Ingest files that changed since last run
        for path in files:
            try:
                mtime = os.path.getmtime(path)
                prev = ingested_index.get(path)
                if prev and prev == mtime:
                    continue

                # extract pages and chunk them
                pages = _extract_pdf_pages(path)
                texts = []
                metadatas = []
                for p in pages:
                    page_text = p.get("text", "")
                    page_num = p.get("page")
                    if splitter:
                        chunks = splitter.split_text(page_text)
                    else:
                        # coarse fallback: use the full page as single chunk
                        chunks = [page_text]
                    for idx, ch in enumerate(chunks):
                        texts.append(ch)
                        metadatas.append({"source": os.path.basename(path), "page": page_num, "chunk": idx})

                # upsert into Chroma persistent DB
                if embeddings is not None and texts:
                    try:
                        # try common langchain Chroma factory
                        try:
                            ChromaVec.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas, persist_directory=chroma_dir, collection_name=collection_name)
                        except TypeError:
                            # alternative signature
                            ChromaVec.from_texts(texts, embeddings, metadatas=metadatas, persist_directory=chroma_dir, collection_name=collection_name)
                    except Exception:
                        pass

                ingested_index[path] = mtime
            except Exception as e:
                errs = list(state.get("execution_errors", []))
                errs.append(f"researcher: failed to ingest {path}: {e}")
                return {"execution_errors": errs}

        # persist ingested index
        try:
            with open(ingested_index_path, "w", encoding="utf8") as f:
                json.dump(ingested_index, f)
        except Exception:
            pass

        # Perform semantic search using the task description
        try:
            query = state.get("task_description", "") or state.get("context_data", "")
            if query and embeddings is not None:
                try:
                    # load vectorstore from persistence
                    try:
                        db = ChromaVec(persist_directory=chroma_dir, embedding_function=embeddings, collection_name=collection_name)
                    except TypeError:
                        db = ChromaVec(persist_directory=chroma_dir, embedding_function=embeddings)

                    docs = db.similarity_search(query, k=5)
                    for d in docs:
                        meta = getattr(d, "metadata", {}) or {}
                        collected_chunks.append({"source": meta.get("source"), "page": meta.get("page"), "text": getattr(d, "page_content", str(d)), "metadata": meta})
                except Exception:
                    # On failure fall back to naive extraction below
                    collected_chunks = []
        except Exception:
            collected_chunks = []

    # If vector DB unavailable or search failed, fall back to naive extraction but limit to Top-K
    if not collected_chunks:
        naive_chunks: List[Dict] = []
        for path in files:
            try:
                pages = _extract_pdf_pages(path)
                naive_chunks.extend(pages)
            except Exception:
                continue

        # simple heuristic: pick first K pages or best matching by token overlap
        k = 5
        query_tokens = set((state.get("task_description", "") + " " + state.get("context_data", "")).lower().split())
        scored = []
        for c in naive_chunks:
            txt = (c.get("text") or "").lower()
            score = sum(1 for t in query_tokens if t and t in txt)
            scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        topk = [c for s, c in scored[:k]] if scored else naive_chunks[:k]
        collected_chunks = topk

    # Append a human-readable index to context for traceability
    if collected_chunks:
        idx_lines = [f"[EXTRACTED] {c.get('source')}#p{c.get('page')}: {c.get('text','')[:200]}" for c in collected_chunks]
        ctx = ctx + "\n" + "\n".join(idx_lines)

    # Extract structured ГОСТ requirements from the top-K relevant chunks
    parsed_requirements: List[Dict] = []
    try:
        examples = []
        for c in collected_chunks:
            examples.append(f"PAGE={c.get('page')} SOURCE={os.path.basename(c.get('source') or '')}\n{(c.get('text') or '')[:1200]}")

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
        parsed_requirements = list(state.get("parsed_requirements", []))

    return {
        "context_data": ctx,
        "knowledge_chunks": collected_chunks,
        "parsed_requirements": parsed_requirements,
        "execution_errors": list(state.get("execution_errors", [])),
    }
