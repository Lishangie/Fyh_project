import os
import tempfile
import subprocess
import ast
from typing import Tuple
from state import ReportState
from core.llm_router import hybrid_llm_call


def _security_review(code: str) -> Tuple[bool, str]:
    """Static analysis of generated code to block dangerous constructs.

    Returns (allowed: bool, reason: str)
    """
    banned_modules = {"os", "sys", "subprocess", "socket", "requests", "urllib", "ftplib", "paramiko"}
    banned_names = {"exec", "eval", "compile", "open", "__import__"}
    try:
        tree = ast.parse(code)
    except Exception as e:
        return False, f"parse_error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                if n.name.split(".")[0] in banned_modules:
                    return False, f"banned import: {n.name}"
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in banned_modules:
                return False, f"banned import from: {node.module}"
        if isinstance(node, ast.Call):
            # function being called may be Name or Attribute
            func = node.func
            fname = None
            if isinstance(func, ast.Name):
                fname = func.id
            elif isinstance(func, ast.Attribute):
                fname = func.attr
            if fname in banned_names:
                return False, f"banned call: {fname}"
    return True, "ok"


def _exec_code_in_subprocess(code: str, cwd: str) -> Tuple[bool, str, str]:
    """Write code to a temp file and run it in a subprocess; return (ok, stdout, stderr)."""
    fd, path = tempfile.mkstemp(suffix=".py", dir=cwd)
    os.close(fd)
    with open(path, "w", encoding="utf8") as f:
        f.write(code)

    proc = subprocess.Popen([os.sys.executable, path], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate(timeout=120)
    ok = proc.returncode == 0
    return ok, out, err


def coder_visualizer_node(state: ReportState) -> dict:
    """Prompt LLM to generate plotting code, review it and execute in subprocess.

    Produces image files in `artifacts/` and appends their paths to `artifact_paths`.
    On failure, appends traceback to `execution_errors`.
    """
    os.makedirs("artifacts", exist_ok=True)
    title = state.get("task_description", "Experiment")
    context = state.get("context_data", "")
    prompt = (
        f"Write a Python script that loads sample data (or uses provided data) and saves a publication-quality PNG plot to artifacts/."
        f" The output file should be named plot_auto.png and use matplotlib. Only provide runnable Python code, no explanation.\n"
        f"TaskTitle: {title}\nContext: {context}\n"
    )

    try:
        code = hybrid_llm_call(prompt, "code_gen")
    except Exception as e:
        errs = list(state.get("execution_errors", []))
        errs.append(f"coder: llm generation failed: {e}")
        return {"execution_errors": errs}

    # Simple heuristic: if code block fences exist, strip them
    if code.strip().startswith("```"):
        # remove first and last fence
        parts = code.split("```")
        # take the middle part
        if len(parts) >= 3:
            code = parts[1]

    allowed, reason = _security_review(code)
    if not allowed:
        errs = list(state.get("execution_errors", []))
        errs.append(f"security_reject: {reason}")
        return {"execution_errors": errs}

    # Execute code in artifacts directory
    ok, out, err = _exec_code_in_subprocess(code, cwd="artifacts")
    if not ok:
        errs = list(state.get("execution_errors", []))
        errs.append(f"execution_failed: {err}\nstdout:{out}")
        return {"execution_errors": errs}

    # Find generated PNGs in artifacts after execution
    artifact_paths = list(state.get("artifact_paths", []))
    for fn in os.listdir("artifacts"):
        if fn.lower().endswith(".png"):
            path = os.path.join("artifacts", fn)
            if path not in artifact_paths:
                artifact_paths.append(path)

    dynamic_tables = list(state.get("dynamic_tables", []))
    return {
        "artifact_paths": artifact_paths,
        "dynamic_tables": dynamic_tables,
        "execution_errors": []
    }
