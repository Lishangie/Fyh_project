import sqlite3
import pickle
import os
from typing import Optional, Tuple

class SqliteSaver:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        # Allow longer wait for concurrent writers to avoid 'database is locked' errors
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self._init_table()

    @classmethod
    def from_conn_string(cls, conn_str: str):
        return cls(conn_str)

    def _init_table(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT PRIMARY KEY,
            data BLOB,
            current_node TEXT
        )
        """)
        self.conn.commit()

    def save(self, thread_id: str, state: dict, current_node: Optional[str]):
        cur = self.conn.cursor()
        payload = pickle.dumps({"state": state})
        cur.execute("REPLACE INTO checkpoints (thread_id, data, current_node) VALUES (?, ?, ?)",
                    (thread_id, payload, current_node))
        self.conn.commit()

    def load(self, thread_id: str) -> Tuple[Optional[dict], Optional[str]]:
        cur = self.conn.cursor()
        cur.execute("SELECT data, current_node FROM checkpoints WHERE thread_id = ?", (thread_id,))
        row = cur.fetchone()
        if not row:
            return None, None
        payload, current_node = row
        obj = pickle.loads(payload)
        return obj.get("state"), current_node
