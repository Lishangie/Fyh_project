import os
from state import ReportState
from core.llm_router import hybrid_llm_call


def feedback_processor_node(state: ReportState) -> dict:
    """Process human feedback after HITL pause and append a learned rule.

    - Reads `human_feedback` and `execution_errors` from state.
    - Calls LLM to extract a generalized rule.
    - Appends the rule to `skills/learned_rules.md`.
    - Clears `human_feedback` and `execution_errors` and requests a retry.
    """
    fb = (state.get("human_feedback") or "").strip()
    errors = list(state.get("execution_errors", []))
    if not fb:
        return {}

    # Build prompt to generalize the feedback into a concise rule
    prompt = (
        f"You are a system that distills human feedback into a single concise guideline.\n"
        f"Human feedback:\n{fb}\n\n"
        f"Execution errors (if any):\n{errors}\n\n"
        "Produce one short, actionable rule (1-2 sentences) suitable for appending to a project's guidebook."
    )

    try:
        rule = hybrid_llm_call(prompt, task_type="feedback_learning")
        rule_text = rule.strip()
    except Exception:
        # Fallback: persist raw feedback if LLM fails
        rule_text = fb

    os.makedirs("skills", exist_ok=True)
    target = os.path.join("skills", "learned_rules.md")
    try:
        with open(target, "a", encoding="utf8") as f:
            f.write("- " + rule_text.replace("\n", " ") + "\n")
    except Exception:
        # best-effort; ignore write failures but surface via execution_errors
        return {"execution_errors": [f"feedback_processor: failed to write learned rule"]}

    # Clear feedback/errors and request a retry (route decision by error_resolver logic)
    return {"human_feedback": "", "execution_errors": [], "last_resolution": "retry", "last_failed_node": "writer_node"}
