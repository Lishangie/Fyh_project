"""Loads textual skill descriptions from the `skills/` directory.

Skills are plain Markdown files that contain strict instructions to be injected
into agent system prompts when performing specific subtasks (e.g., table
formatting rules for ГОСТ, PlantUML syntax guidance, code-safety rules).
"""
from pathlib import Path
from typing import Dict, List

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def load_all_skills() -> Dict[str, str]:
    skills: Dict[str, str] = {}
    if not SKILLS_DIR.exists():
        return skills
    for p in SKILLS_DIR.glob("*.md"):
        try:
            skills[p.stem] = p.read_text(encoding="utf8")
        except Exception:
            continue
    return skills


def select_skills_for_task(task_type: str) -> List[str]:
    """A lightweight heuristic to select skill documents for a given task_type.

    For now, matches substrings against filenames (e.g., 'gost' -> gost_tables).
    """
    skills = load_all_skills()
    if not skills:
        return []
    selected = []
    t = task_type.lower()
    for name, content in skills.items():
        if any(k in name for k in (t.split(), t, "gost", "plantuml", "table", "code")):
            selected.append(content)
    # fallback: return all if nothing matched
    return selected or list(skills.values())
