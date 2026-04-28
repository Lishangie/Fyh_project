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

Publishing to GitHub
---------------------

Options to publish the repo:

- Manual (you create the repo on GitHub):

	```powershell
	git remote add origin https://github.com/USERNAME/REPO.git
	git branch -M main
	git push -u origin main
	```

- Automated (I can create the repo if you provide a GitHub Personal Access Token):

	1. Export your token locally (only in your shell):

	```powershell
	$env:GITHUB_TOKEN = "ghp_..."
	python scripts/create_github_repo.py my-repo public
	```

	2. The script will create the repo, add `origin` and push the `main` branch.

Security note: do not commit tokens into the repo. Use environment variables and remove them after use.

Repository
----------

This project has been published to GitHub: https://github.com/Lishangie/Fyh_project

