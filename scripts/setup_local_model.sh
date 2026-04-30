#!/usr/bin/env bash
set -euo pipefail

# setup_local_model.sh
# Creates an Ollama Modelfile optimized for a 6GB VRAM GPU and runs `ollama create`.
# Run this on the host machine (outside Docker).

WORKDIR=$(cd "$(dirname "$0")" && pwd)
cd "$WORKDIR"

MODEL_LOCAL_FILENAME="huihui4-8b-a4b-v2.gguf"
MODELFILENAME="Modelfile"
OLLAMA_MODEL_NAME="local_agent_model"

# Check for ollama
if ! command -v ollama >/dev/null 2>&1; then
  echo "Error: 'ollama' not found in PATH. Please install Ollama first: https://ollama.com/docs/installation"
  exit 2
fi

# Prepare FROM line: prefer local GGUF if present, otherwise reference a known HF repo name
if [ -f "$MODEL_LOCAL_FILENAME" ]; then
  FROM_LINE="FROM $MODEL_LOCAL_FILENAME"
  echo "Using local GGUF: $MODEL_LOCAL_FILENAME"
else
  echo "Local file $MODEL_LOCAL_FILENAME not found. You can download a compatible 8B GGUF model (Q4_K_M) manually."
  echo "Example commands (pick one):"
  echo "  # 1) Using huggingface_hub Python helper (requires HF token env var HUGGINGFACE_HUB_TOKEN):"
  echo "  python - <<'PY'"
  echo "from huggingface_hub import hf_hub_download"
  echo "hf_hub_download(repo_id=\"QuantFactory/Meta-Llama-3-8B-Instruct-GGUF\", filename=\"meta-llama-3-8b-instruct.gguf\", local_dir=\".\")"
  echo "PY"
  echo
  echo "  # 2) Using huggingface-cli (requires login):"
  echo "  huggingface-cli repo download -r QuantFactory/Meta-Llama-3-8B-Instruct-GGUF -o $MODEL_LOCAL_FILENAME"
  echo
  echo "  # 3) Or download a publicly hosted GGUF file via wget (if you have a direct URL):"
  echo "  wget -O $MODEL_LOCAL_FILENAME <DIRECT_GGUF_URL_HERE>"
  echo
  echo "If you prefer Ollama to fetch a remote model by repo, you can also let FROM reference a model repo."
  echo "We'll use a repo reference as a fallback so 'ollama create' can attempt to fetch it."
  FROM_LINE="FROM QuantFactory/Meta-Llama-3-8B-Instruct-GGUF"
fi

# Write Modelfile with VRAM-conscious parameters
cat > "$MODELFILENAME" <<EOF
$FROM_LINE
# Optimizations for ~6GB VRAM (Q4_K_M style quantized 8B)
PARAMETER num_ctx 4096
PARAMETER num_thread 8
PARAMETER num_gpu 99
EOF

echo "Created $MODELFILENAME with content:"
cat "$MODELFILENAME"

echo
echo "Running: ollama create $OLLAMA_MODEL_NAME -f $MODELFILENAME"
# Create or update the Ollama model (this may download and compile; it can take time)
ollama create "$OLLAMA_MODEL_NAME" -f "$MODELFILENAME"

echo "Ollama model '$OLLAMA_MODEL_NAME' created. You can list with: ollama list"

echo "If you want the application to use this model, set FAST_LLM_NAME=ollama/$OLLAMA_MODEL_NAME in your .env or environment."

exit 0
