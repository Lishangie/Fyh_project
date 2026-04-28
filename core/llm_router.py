"""Hybrid LLM router utility.

Tries to use a fast/local model first, and falls back to a heavier cloud model.
This module uses LangChain when available; if not present, it falls back to a safe
mock responder so the rest of the system remains runnable for development.
"""
from typing import Optional
import os
import traceback

def hybrid_llm_call(prompt: str, task_type: str, fallback_limit: int = 3) -> str:
    """Attempt fast model, then heavy model. Returns text response.

    - Uses LangChain Chat models if available.
    - Uses environment variables to configure model names:
      FAST_LLM_NAME, HEAVY_LLM_NAME. If not set, defaults will be used.
    - In absence of any real model, returns a deterministic mock response.
    """
    attempts = []
    fast_name = os.environ.get("FAST_LLM_NAME")
    heavy_name = os.environ.get("HEAVY_LLM_NAME", os.environ.get("HEAVY_MODEL", "gpt-4"))

    # Preferred order: FAST -> HEAVY
    candidates = []
    if fast_name:
        candidates.append(("fast", fast_name))
    # allow an empty fast candidate to prefer default ChatOpenAI lightweight model
    candidates.append(("heavy", heavy_name))

    # Try LangChain chat models if available
    try:
        from langchain.chat_models import ChatOpenAI
        from langchain.schema import HumanMessage

        for label, model_name in candidates:
            try:
                # low temperature for deterministic behavior in most tasks
                client = ChatOpenAI(model_name=model_name, temperature=0.0)
                resp = client([HumanMessage(content=prompt)])
                # LangChain chat models often return AIMessage or list-like
                if hasattr(resp, "content"):
                    return resp.content
                if isinstance(resp, list) and resp:
                    return getattr(resp[0], "content", str(resp[0]))
                return str(resp)
            except Exception as e:
                attempts.append(f"{label}({model_name}) -> {e}")
    except Exception as e:
        attempts.append(f"langchain not available: {e}")

    # Try OpenAI HTTP API directly as a backup (if key present)
    try:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
        if api_key:
            openai.api_key = api_key
            resp = openai.ChatCompletion.create(
                model=heavy_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1500,
            )
            return resp["choices"][0]["message"]["content"]
    except Exception as e:
        attempts.append(f"openai fallback failed: {e}")

    # Final fallback: return a concise mock reply to keep the pipeline working.
    attempts.append("final fallback: mock responder used")
    # Provide a short, deterministic mock based on the prompt and task_type
    try:
        summary = prompt.replace("\n", " ")[:400]
        return f"[MOCK_LLM_RESPONSE for {task_type}] {summary}"
    finally:
        # keep debug info in environment log if requested
        if os.environ.get("LLM_ROUTER_DEBUG"):
            tb = "\n".join(attempts)
            print("hybrid_llm_call debug:\n", tb)
