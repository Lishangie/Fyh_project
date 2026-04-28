#!/usr/bin/env python3
import os
import sys

try:
    import requests
except ImportError:
    print("MISSING_REQUESTS")
    sys.exit(2)

token = os.environ.get("GITHUB_TOKEN")
if not token:
    print("NO_TOKEN")
    sys.exit(1)

resp = requests.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
if resp.status_code != 200:
    print("ERR_USER", resp.status_code)
    sys.exit(2)

login = resp.json().get("login")
repo = sys.argv[1] if len(sys.argv) > 1 else os.path.basename(os.getcwd())

repo_resp = requests.get(f"https://api.github.com/repos/{login}/{repo}", headers={"Authorization": f"token {token}"})
if repo_resp.status_code == 200:
    clone_url = repo_resp.json().get("clone_url")
    print(login)
    print(clone_url)
    sys.exit(0)
else:
    print(login)
    print("NOT_FOUND")
    sys.exit(3)
