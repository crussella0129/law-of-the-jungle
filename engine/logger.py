"""SQLite event logger — every prompt, response, action, and death is recorded."""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone


_SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
    round_id    INTEGER PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    world_state JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    action_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id     INTEGER NOT NULL REFERENCES rounds(round_id),
    agent_name   TEXT NOT NULL,
    raw_prompt   TEXT,
    raw_response TEXT,
    parsed_action JSON,
    latency_ms   INTEGER
);

CREATE TABLE IF NOT EXISTS events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id     INTEGER NOT NULL REFERENCES rounds(round_id),
    event_type   TEXT NOT NULL,
    participants JSON,
    outcome      JSON
);

CREATE TABLE IF NOT EXISTS messages (
    message_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id    INTEGER NOT NULL REFERENCES rounds(round_id),
    sender      TEXT NOT NULL,
    recipient   TEXT NOT NULL,
    content     TEXT,
    private     BOOLEAN
);
"""


class SimulationLogger:
    def __init__(self, db_path: str = "simulation.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def log_round(self, round_id: int, world_state: dict) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO rounds (round_id, timestamp, world_state) VALUES (?, ?, ?)",
            (round_id, ts, json.dumps(world_state)),
        )
        self.conn.commit()

    def log_action(
        self,
        round_id: int,
        agent_name: str,
        raw_prompt: str,
        raw_response: str,
        parsed: dict,
        latency_ms: int,
    ) -> None:
        self.conn.execute(
            "INSERT INTO actions (round_id, agent_name, raw_prompt, raw_response, parsed_action, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (round_id, agent_name, raw_prompt, raw_response, json.dumps(parsed), latency_ms),
        )
        self.conn.commit()

    def log_event(
        self,
        round_id: int,
        event_type: str,
        participants: list[str],
        outcome: dict,
    ) -> None:
        self.conn.execute(
            "INSERT INTO events (round_id, event_type, participants, outcome) VALUES (?, ?, ?, ?)",
            (round_id, event_type, json.dumps(participants), json.dumps(outcome)),
        )
        self.conn.commit()

    def log_message(
        self,
        round_id: int,
        sender: str,
        recipient: str,
        content: str,
        private: bool,
    ) -> None:
        self.conn.execute(
            "INSERT INTO messages (round_id, sender, recipient, content, private) VALUES (?, ?, ?, ?, ?)",
            (round_id, sender, recipient, content, private),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
