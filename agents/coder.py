import os
import tempfile
import subprocess
import ast
from typing import Tuple
from state import ReportState
from core.llm_router import hybrid_llm_call, hybrid_vlm_call

# Optional import of docker SDK; used when backend runs inside a container
try:
    import docker as _docker_sdk
except Exception:
    _docker_sdk = None


def _security_review(code: str) -> Tuple[bool, str]:
    """Static analysis of generated code to block dangerous constructs.

    Returns (allowed: bool, reason: str)
    """
    # Keep a conservative banned list but allow `requests` conditionally for PlantUML
    banned_modules = {"os", "sys", "subprocess", "socket", "urllib", "ftplib", "paramiko"}
    banned_names = {"exec", "eval", "compile", "open", "__import__"}
    try:
        tree = ast.parse(code)
    except Exception as e:
        return False, f"parse_error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mod = n.name.split(".")[0]
                if mod == "requests":
                    # allow requests only when the code explicitly references PlantUML
                    if "plantuml" in code.lower() or "plantuml.com" in code.lower():
                        continue
                    return False, f"banned import: {n.name}"
                if mod in banned_modules:
                    return False, f"banned import: {n.name}"
        if isinstance(node, ast.ImportFrom):
            mod0 = (node.module or "").split(".")[0]
            if mod0 == "requests":
                if "plantuml" in code.lower() or "plantuml.com" in code.lower():
                    continue
                return False, f"banned import from: {node.module}"
            if mod0 in banned_modules:
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
    """Execute generated code inside an ephemeral Docker container for isolation.

    This function requires the `docker` Python SDK and a reachable Docker daemon
    via the host socket `/var/run/docker.sock`. It will NOT fall back to local
    execution to avoid executing untrusted code on the host.

    Returns (ok, stdout, stderr).
    """
    # Ensure target directory exists and write the script there so it can be mounted
    os.makedirs(cwd, exist_ok=True)
    fd, host_path = tempfile.mkstemp(suffix=".py", dir=cwd)
    os.close(fd)
    with open(host_path, "w", encoding="utf8") as f:
        f.write(code)

    host_cwd = os.path.abspath(cwd)
    container_wd = "/workspace"
    script_name = os.path.basename(host_path)

    # Decide whether to allow network (only for PlantUML rendering)
    allow_network = False
    if "plantuml" in code.lower() or "plantuml.com" in code.lower():
        allow_network = True

    # Strict requirement: docker SDK and docker socket must be available
    docker_socket = "/var/run/docker.sock"
    if _docker_sdk is None:
        try:
            os.remove(host_path)
        except Exception:
            pass
        return False, "", "docker SDK (python package 'docker') is not installed"

    if not os.path.exists(docker_socket):
        try:
            os.remove(host_path)
        except Exception:
            pass
        return False, "", "/var/run/docker.sock not found; docker daemon not reachable"

    try:
        client = _docker_sdk.from_env()
        # quick connectivity check
        client.ping()
    except Exception as e:
        try:
            os.remove(host_path)
        except Exception:
            pass
        return False, "", f"Cannot connect to Docker daemon: {e}"

    image = "python:3.10-slim"
    try:
        # ensure image is present (pull if missing)
        try:
            client.images.get(image)
        except _docker_sdk.errors.ImageNotFound:
            client.images.pull(image)

        volumes = {host_cwd: {"bind": container_wd, "mode": "rw"}}
        run_kwargs = {
            "volumes": volumes,
            "remove": True,
            "mem_limit": "256m",
        }
        if not allow_network:
            run_kwargs["network_mode"] = "none"

        logs = client.containers.run(image, ["python", f"{container_wd}/{script_name}"], **run_kwargs)
        out = logs.decode() if isinstance(logs, (bytes, bytearray)) else str(logs)
        try:
            os.remove(host_path)
        except Exception:
            pass
        return True, out, ""
    except _docker_sdk.errors.ContainerError as e:
        out = e.stdout.decode() if isinstance(e.stdout, (bytes, bytearray)) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or str(e))
        try:
            os.remove(host_path)
        except Exception:
            pass
        return False, out, err
    except Exception as e:
        try:
            os.remove(host_path)
        except Exception:
            pass
        return False, "", f"Docker execution failed: {e}"


def coder_visualizer_node(state: ReportState) -> dict:
    """Prompt LLM to generate plotting code, review it and execute in subprocess.

    Produces image files in `artifacts/` and appends their paths to `artifact_paths`.
    On failure, appends traceback to `execution_errors`.
    """
    os.makedirs("artifacts", exist_ok=True)
    title = state.get("task_description", "Experiment")
    context = state.get("context_data", "")
    draft = state.get("draft_text", "")
    # Heuristics: detect UML/architecture, code snippet, or plotting request
    low_draft = draft.lower() if isinstance(draft, str) else ""
    lowt = title.lower() if isinstance(title, str) else ""

    wants_uml = any(k in low_draft for k in ("uml", "plantuml", "архитектура", "architecture", "архитектур")) or any(k in lowt for k in ("uml", "plantuml", "архитектура", "architecture", "архитектур"))

    # Heuristic: if the draft contains a fenced code block or the title mentions code,
    # produce a highlighted code image. Otherwise, produce a matplotlib plot.
    wants_code_image = False
    if "```" in draft:
        wants_code_image = True
    if any(k in lowt for k in ("код", "code", "snippet", "пример кода")):
        wants_code_image = True

    if wants_uml:
        # prepare a script that will render PlantUML via the public PlantUML server
        import re
        m = re.search(r"```plantuml\n([\s\S]*?)```", draft, re.I)
        plantuml_text = m.group(1) if m else None
        if not plantuml_text:
            # fallback: ask LLM to generate PlantUML based on the draft description
            plantuml_text = "'@startuml\nactor User\n@enduml'"

        prompt = (
            "Write a standalone Python script that contains a variable `PLANTUML_TEXT` with PlantUML source as a triple-quoted string,\n"
            "encodes it appropriately for the PlantUML server, downloads the rendered PNG from http://www.plantuml.com/plantuml/png/<encoded>,\n"
            "saves it under the `artifacts/` folder (e.g. artifacts/diagram_plantuml.png) and prints the path to the saved PNG.\n"
            "The script may use the `requests` library but must not perform any other network actions.\n"
            f"PLANTUML_SOURCE:\n{plantuml_text}\n\nTaskTitle: {title}\nContext: {context}\n"
        )
    elif wants_code_image:
        # try to extract a fenced code block from the draft
        import re
        m = re.search(r"```(?:python)?\n([\s\S]*?)```", draft)
        snippet = m.group(1) if m else None
        if not snippet:
            # include a small default snippet if none found
            snippet = "print('Hello, world')\n"

        prompt = (
            "Write a standalone Python script that imports `generate_code_image` from `tools.pygments_renderer`\n"
            "and renders the provided code snippet into a PNG saved under the `artifacts/` folder.\n"
            "The script must NOT perform any network operations and must only write files under the `artifacts/` directory.\n"
            "On success, the script should print the path to the generated image.\n\n"
            f"CODE_SNIPPET:\n{snippet}\n\n"
            f"TaskTitle: {title}\nContext: {context}\n"
        )
    else:
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
        parts = code.split("```")
        if len(parts) >= 3:
            code = parts[1]

    allowed, reason = _security_review(code)
    if not allowed:
        errs = list(state.get("execution_errors", []))
        errs.append(f"security_reject: {reason}")
        return {"execution_errors": errs}

    # Execute code in artifacts directory (isolation via Docker)
    ok, out, err = _exec_code_in_subprocess(code, cwd="artifacts")
    if not ok:
        errs = list(state.get("execution_errors", []))
        errs.append(f"execution_failed: {err}\nstdout:{out}")
        return {"execution_errors": errs}

    # Find generated PNGs in artifacts after execution and perform VLM review
    artifact_paths = list(state.get("artifact_paths", []))
    pre_existing = set(state.get("artifact_paths", []))
    files_after = [f for f in os.listdir("artifacts") if f.lower().endswith(".png")]
    new_pngs = [f for f in files_after if os.path.join("artifacts", f) not in pre_existing]

    for fn in new_pngs:
        path = os.path.join("artifacts", fn)
        # Ask VLM to review the image for readability/labels/truncation
        try:
            vlm_prompt = (
                "Please inspect the attached image for the following issues: readability of text, presence and clarity of axes labels and ticks, "
                "whether any labels or text are truncated/clipped, and whether the figure is generally publication-quality. "
                "Respond briefly with 'OK' if no issues, otherwise describe issues concisely."
            )
            vlm_resp = hybrid_vlm_call(vlm_prompt, path, task_type="vlm_review")
        except Exception as e:
            vlm_resp = f"[VLM_CALL_FAILED] {e}"

        if isinstance(vlm_resp, str) and vlm_resp.startswith("[VLM_FALLBACK_ACCEPTED]"):
            # VLM not available; accept by default
            artifact_paths.append(path)
            continue

        verdict = (vlm_resp or "").lower()
        # basic heuristics for severe visual issues
        bad_tokens = ("cropped", "truncat", "clipp", "overlap", "blur", "not readable", "no labels", "axes missing", "cut off")
        if any(tok in verdict for tok in bad_tokens):
            errs = list(state.get("execution_errors", []))
            errs.append(f"vlm_detected_issue for {path}: {vlm_resp}")
            return {"execution_errors": errs}
        # otherwise accept the artifact
        artifact_paths.append(path)

    dynamic_tables = list(state.get("dynamic_tables", []))
    return {
        "artifact_paths": artifact_paths,
        "dynamic_tables": dynamic_tables,
        "execution_errors": []
    }
