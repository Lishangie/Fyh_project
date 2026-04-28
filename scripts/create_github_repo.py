#!/usr/bin/env python3
"""
Create a GitHub repository using a Personal Access Token (GITHUB_TOKEN env var),
add it as `origin` and push the current branch as `main`.

Usage:
  GITHUB_TOKEN=ghp_xxx python scripts/create_github_repo.py [repo_name] [public|private]
If repo_name is omitted, current directory name is used.
"""
import os
import sys
import subprocess
import json

try:
    import requests
except ImportError:
    print("This script requires 'requests'. Install with: pip install requests")
    sys.exit(2)

token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not token:
    print("Error: set GITHUB_TOKEN environment variable with 'repo' scope.")
    sys.exit(1)

repo_name = sys.argv[1] if len(sys.argv) > 1 else os.path.basename(os.getcwd())
visibility = sys.argv[2] if len(sys.argv) > 2 else "private"
is_private = visibility.lower() != "public"

api = "https://api.github.com/user/repos"
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json"
}
payload = {"name": repo_name, "private": is_private, "description": "Academic agent scaffold"}

resp = requests.post(api, headers=headers, json=payload)
if resp.status_code not in (201,):
    print("Failed to create repository:", resp.status_code, resp.text)
    sys.exit(1)

repo = resp.json()
clone_url = repo.get("clone_url")
print("Created repo:", clone_url)

# Add remote (without token) if not exists
try:
    subprocess.check_call(["git", "remote", "add", "origin", clone_url])
except subprocess.CalledProcessError:
    print("Remote 'origin' may already exist, continuing...")

subprocess.check_call(["git", "branch", "-M", "main"])

# For pushing, embed token in the push URL but do NOT store it in git remotes
push_url = clone_url.replace("https://", f"https://{token}@")
try:
    subprocess.check_call(["git", "push", "-u", push_url, "main"])
    print("Pushed current repository to", clone_url)
except subprocess.CalledProcessError as e:
    print("Failed to push to remote. Error:", e)
    print("You may need to configure git credentials or push manually:")
    print(f"  git push -u {clone_url} main")
