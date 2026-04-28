# Academic Agentic Report Generator (Minimal Scaffold)

This repository contains a minimal scaffold implementing a simplified multi-agent workflow for generating academic reports. It includes:

- A tiny `langgraph` emulator (graph runner + sqlite checkpointer)
- Agents: `researcher`, `writer`, `coder`
- Tools: sample `plot_generator`
- `main.py` — builds and runs the graph with a Human-in-the-Loop checkpoint before final assembly

Run:

```powershell
python -m pip install -r requirements.txt
python main.py
# or non-interactive (auto-approve HITL checkpoint):
python main.py -y
```

After the first run the process will pause before assembling the final DOCX (Human-in-the-Loop). Inspect `artifacts/` and `assets/`, then approve to finish (or use `-y` to auto-approve).
