from state import ReportState
from core.llm_router import hybrid_llm_call


def error_resolver_node(state: ReportState) -> dict:
    """Attempt to resolve the last execution error by asking an LLM to propose fixes.

    Behavior:
    - Read `execution_errors` and `retry_counts` from state
    - If retry_count for the failing node < 3, ask LLM to suggest corrected payload
    - Set `last_resolution` to 'retry' or 'abort'
    """
    errors = list(state.get("execution_errors", []))
    if not errors:
        return {"last_resolution": "abort"}

    # Simple policy: pick the most recent error and try to fix
    last = errors[-1]
    retry_counts = dict(state.get("retry_counts", {}))
    # heuristic: determine failing node from error message
    if ":" in last:
        node_hint = last.split(":")[0]
    else:
        node_hint = "coder_node"

    count = retry_counts.get(node_hint, 0)
    if count >= 3:
        # Give up
        return {"last_resolution": "abort"}

    # Ask LLM to propose a fix. Provide context: draft_text, last error, and (optionally) code snippets.
    prompt = (
        f"You are an expert agent fixer. The node '{node_hint}' produced the following error:\n{last}\n"
        f"Current draft/text (truncated): {state.get('draft_text','')[:800]}\n"
        f"Knowledge snippets: {str(state.get('knowledge_chunks',[])[:5])}\n"
        "Provide a concise fix suggestion (either corrected code or rewriting instructions). Return the word 'RETRY' if you provided a fix to apply, otherwise return 'ABORT'."
    )

    resp = hybrid_llm_call(prompt, "error_fix")
    decision = "abort"
    if isinstance(resp, str) and resp.strip().upper().startswith("RETRY"):
        decision = "retry"
    elif isinstance(resp, str) and "fix" in resp.lower():
        decision = "retry"

    # increment retry counter
    retry_counts[node_hint] = count + 1

    return {
        "last_resolution": "retry" if decision == "retry" else "abort",
        "retry_counts": retry_counts,
        "last_failed_node": node_hint
    }
