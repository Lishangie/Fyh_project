def generate_sample_plot(output_path: str) -> str:
    import matplotlib.pyplot as plt
    import numpy as np
    import os
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    data = np.random.randn(100).cumsum()
    plt.figure(figsize=(6, 4))
    plt.plot(data, lw=1.5)
    plt.title("Sample experiment")
    plt.xlabel("step")
    plt.ylabel("value")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    return output_path
