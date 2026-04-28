#!/usr/bin/env bash
set -euo pipefail

print_usage() {
  cat <<EOF
Usage: sudo ./remote_setup_ubuntu.sh [--user <username>] [--gpu]

Installs Docker Engine, Docker Compose plugin, and optionally NVIDIA Container Toolkit
on Ubuntu. MUST be run as root (use sudo).

Options:
  --user <username>   Add the specified user to the 'docker' group (recommended).
  --gpu               Install NVIDIA Container Toolkit (requires NVIDIA drivers installed separately).
  -h, --help          Show this help message.
EOF
}

if [[ ${1:-} == "-h" || ${1:-} == "--help" ]]; then
  print_usage
  exit 0
fi

INSTALL_GPU=0
USER_TO_ADD=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      USER_TO_ADD="$2"
      shift 2
      ;;
    --gpu)
      INSTALL_GPU=1
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      print_usage
      exit 1
      ;;
  esac
done

if [[ $(id -u) -ne 0 ]]; then
  echo "This script must be run as root. Use sudo." >&2
  exit 2
fi

set -x

# Install prerequisites
apt-get update
apt-get install -y ca-certificates curl gnupg lsb-release software-properties-common apt-transport-https

# Install Docker CE (official repo)
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
ARCH=$(dpkg --print-architecture)
CODENAME=$(lsb_release -cs)
cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group if requested or if SUDO_USER is available
if [[ -n "${USER_TO_ADD}" ]]; then
  usermod -aG docker "${USER_TO_ADD}" || true
  echo "Added ${USER_TO_ADD} to docker group"
elif [[ -n "${SUDO_USER:-}" ]]; then
  usermod -aG docker "${SUDO_USER}" || true
  echo "Added ${SUDO_USER} (invoking user) to docker group"
else
  echo "No user specified to add to docker group. You may need to add your user manually."
fi

# Optional: NVIDIA Container Toolkit installation (does NOT install GPU drivers)
if [[ ${INSTALL_GPU} -eq 1 ]]; then
  echo "Installing NVIDIA Container Toolkit (nvidia-docker2)..."
  distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
  curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
  curl -s -L https://nvidia.github.io/nvidia-docker/${distribution}/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
  apt-get update
  apt-get install -y nvidia-docker2
  systemctl restart docker
  echo "nvidia-docker2 installed. Ensure NVIDIA drivers are installed on the host (outside this script)."
fi

# Helpful next steps
cat <<EOF

Done.
- Docker Engine and Compose plugin installed.
- If you were added to the 'docker' group, log out and back in (or run: newgrp docker).
- To run the project:
    git clone <repo-url> fyh_project
    cd fyh_project
    # optionally create .env with secrets
    docker compose up --build -d
- If you plan to run huihuiai on GPU, ensure host NVIDIA drivers are installed and place model weights under /models/huihuiai (or another path you choose).

Notes:
- This script does NOT install NVIDIA GPU drivers. Install them via your distribution's recommended method before using --gpu.
- For custom paths, edit docker-compose.yml to set HOST_PROJECT_ROOT to the absolute path on the host.

EOF

set +x
