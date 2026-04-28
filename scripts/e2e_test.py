import requests
import time
import os
import sys

API_URL = os.environ.get("API_URL", "http://localhost:8000")


def ensure_test_file():
    kb_dir = os.path.join("assets", "knowledge_base")
    os.makedirs(kb_dir, exist_ok=True)
    path = os.path.join(kb_dir, "test_upload.txt")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf8") as f:
            f.write("This is a small test knowledge file for automated E2E testing.\n")
    return path


def upload(file_path):
    with open(file_path, "rb") as fh:
        files = [("files", (os.path.basename(file_path), fh, "text/plain"))]
        r = requests.post(f"{API_URL}/knowledge/upload", files=files, timeout=60)
    r.raise_for_status()
    return r.json()


def start_report():
    payload = {"task_description": "E2E smoke test report generation", "context_data": "Automated test"}
    r = requests.post(f"{API_URL}/report/start", json=payload, timeout=10)
    r.raise_for_status()
    return r.json().get("thread_id")


def poll_status(thread_id, timeout_seconds=600):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        r = requests.get(f"{API_URL}/report/status/{thread_id}", timeout=10)
        if not r.ok:
            raise RuntimeError(f"Status request failed: {r.status_code} {r.text}")
        data = r.json()
        status = data.get("status")
        print("status:", status)
        if status == "paused_for_hitl":
            return "paused"
        if status == "completed":
            return "completed"
        time.sleep(2)
    raise TimeoutError("Status poll timed out")


def send_feedback(thread_id, feedback_text="Auto-approve"):
    r = requests.post(f"{API_URL}/report/feedback/{thread_id}", json={"feedback": feedback_text}, timeout=10)
    r.raise_for_status()
    return r.json()


def download_report(thread_id, out_dir="artifacts"):
    os.makedirs(out_dir, exist_ok=True)
    r = requests.get(f"{API_URL}/report/download/{thread_id}", timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Download failed: {r.status_code} {r.text}")
    out_path = os.path.join(out_dir, f"Final_Academic_Report_{thread_id}.docx")
    with open(out_path, "wb") as f:
        f.write(r.content)
    return out_path


def main():
    print("Using API at:", API_URL)
    file_path = ensure_test_file()
    print("Uploading test file:", file_path)
    print(upload(file_path))
    print("Starting report...")
    tid = start_report()
    print("Started thread:", tid)
    s = poll_status(tid)
    if s == "paused":
        print("Thread paused for HITL — sending auto feedback")
        send_feedback(tid, "Auto-approve: proceed")
    print("Waiting for completion...")
    final = poll_status(tid)
    if final != "completed":
        raise RuntimeError("Run did not complete successfully")
    path = download_report(tid)
    print("Downloaded report to:", path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("E2E test failed:", e)
        sys.exit(2)
    print("E2E test succeeded")
    sys.exit(0)
