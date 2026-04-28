import os
from state import ReportState
from tools.plot_generator import generate_sample_plot

def coder_visualizer_node(state: ReportState) -> dict:
    os.makedirs("artifacts", exist_ok=True)
    out_path = generate_sample_plot(os.path.join("artifacts", "plot_exp_1.png"))
    artifact_paths = list(state.get("artifact_paths", [])) + [out_path]
    dynamic_tables = list(state.get("dynamic_tables", []))
    dynamic_tables.append({"parameter_name": "sample_count", "value": 100})
    return {
        "artifact_paths": artifact_paths,
        "dynamic_tables": dynamic_tables,
        "execution_errors": []
    }
