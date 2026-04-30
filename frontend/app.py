import streamlit as st
import requests
import os
import time

API_URL = os.environ.get("API_URL", "http://backend:8000")

st.set_page_config(page_title="Fyh Report Generator", layout="wide")

st.sidebar.title("Knowledge Upload")
uploaded_files = st.sidebar.file_uploader("Upload PDFs/CSVs", accept_multiple_files=True, type=['pdf', 'csv', 'md', 'txt'])
if st.sidebar.button("Upload Files"):
    if not uploaded_files:
        st.sidebar.warning("No files selected")
    else:
        try:
            files_payload = []
            for f in uploaded_files:
                files_payload.append(("files", (f.name, f.getvalue(), f.type or 'application/octet-stream')))
            r = requests.post(f"{API_URL}/knowledge/upload", files=files_payload, timeout=60)
            if r.ok:
                st.sidebar.success("Uploaded: " + ", ".join(r.json().get('saved', [])))
            else:
                st.sidebar.error(f"Upload failed: {r.status_code} {r.text}")
        except Exception as e:
            st.sidebar.error(str(e))

try:
    r = requests.get(f"{API_URL}/knowledge/list", timeout=5)
    files_list = r.json().get('files', []) if r.ok else []
except Exception:
    files_list = []

st.sidebar.markdown("**Uploaded files:**")
for fn in files_list:
    st.sidebar.write(fn)

st.title("Fyh — Academic Report Generator")
task_description = st.text_area("Task description", value="", height=120)
context_data = st.text_area("Context data", value="", height=120)

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = None

if st.button("Start Generation"):
    if not task_description.strip():
        st.error("Please provide a task description")
    else:
        payload = {"task_description": task_description, "context_data": context_data}
        try:
            r = requests.post(f"{API_URL}/report/start", json=payload, timeout=10)
            if r.ok:
                tid = r.json().get('thread_id')
                st.session_state['thread_id'] = tid
                st.success(f"Started generation: {tid}")
            else:
                st.error(f"Failed to start: {r.status_code} {r.text}")
        except Exception as e:
            st.error(str(e))

if st.session_state.get('thread_id'):
    tid = st.session_state['thread_id']
    st.markdown(f"**Thread ID:** {tid}")
    status_box = st.empty()
    logs_box = st.empty()

    with st.spinner("Monitoring generation..."):
        while True:
            try:
                r = requests.get(f"{API_URL}/report/status/{tid}", timeout=10)
            except Exception as e:
                status_box.error(f"Backend unreachable: {e}")
                break
            if not r.ok:
                status_box.error(f"Status request failed: {r.status_code}")
                break
            data = r.json()
            status = data.get('status')
            current_node = data.get('current_node')
            state = data.get('state')
            status_box.info(f"Status: {status} | Node: {current_node}")
            logs_box.write(state)

            if status == 'running':
                time.sleep(2)
                continue
            if status == 'paused_for_hitl':
                st.warning("Generation paused for review. Check artifacts.")
                feedback = st.text_area("Human feedback (leave empty to auto-approve)")
                if st.button("Submit Feedback & Resume"):
                    try:
                        r2 = requests.post(f"{API_URL}/report/feedback/{tid}", json={'feedback': feedback}, timeout=10)
                        if r2.ok:
                            st.success("Resumed")
                        else:
                            st.error(f"Failed to resume: {r2.status_code} {r2.text}")
                    except Exception as e:
                        st.error(str(e))
                break
            if status == 'completed':
                try:
                    r3 = requests.get(f"{API_URL}/report/download/{tid}", timeout=30)
                    if r3.ok:
                        st.success("Generation completed")
                        report_bytes = r3.content
                        st.download_button("Download Report", data=report_bytes, file_name=f"Final_Academic_Report_{tid}.docx")
                    else:
                        st.error(f"Download failed: {r3.status_code}")
                except Exception as e:
                    st.error(str(e))
                break
            # unknown status
            break