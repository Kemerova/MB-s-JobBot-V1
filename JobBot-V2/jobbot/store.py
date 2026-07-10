"""SQLite storage: dedupe across runs, scores, application status tracking."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

STATUSES = [
    "new",
    "interested",
    "applied",
    "phone_screen",
    "interviewing",
    "offer",
    "accepted",
    "rejected",
    "hidden",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    source TEXT,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    description TEXT,
    url TEXT,
    salary_min REAL,
    salary_max REAL,
    is_remote INTEGER DEFAULT 0,
    date_posted TEXT,
    search_term TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    score INTEGER,
    fit_summary TEXT,
    strengths TEXT,
    gaps TEXT,
    bullets TEXT,
    status TEXT DEFAULT 'new',
    status_updated TEXT,
    notes TEXT
);
"""


def job_id(job: dict) -> str:
    key = f"{job.get('title', '')}|{job.get('company', '')}|{job.get('location', '')}"
    return hashlib.md5(key.lower().encode("utf-8")).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(jobs)")}
        if "cover_letter" not in cols:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN cover_letter TEXT")
            self.conn.commit()

    def upsert_jobs(self, jobs: list[dict]) -> int:
        """Insert new jobs; refresh last_seen on known ones. Returns # new."""
        new_count = 0
        now = _now()
        for job in jobs:
            jid = job_id(job)
            row = self.conn.execute(
                "SELECT id FROM jobs WHERE id = ?", (jid,)
            ).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE jobs SET last_seen = ? WHERE id = ?", (now, jid)
                )
            else:
                self.conn.execute(
                    """INSERT INTO jobs (id, source, title, company, location,
                       description, url, salary_min, salary_max, is_remote,
                       date_posted, search_term, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        jid,
                        job.get("source"),
                        job.get("title"),
                        job.get("company"),
                        job.get("location"),
                        job.get("description"),
                        job.get("url"),
                        job.get("salary_min"),
                        job.get("salary_max"),
                        1 if job.get("is_remote") else 0,
                        job.get("date_posted"),
                        job.get("search_term"),
                        now,
                        now,
                    ),
                )
                new_count += 1
        self.conn.commit()
        return new_count

    def unscored_jobs(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM jobs WHERE score IS NULL AND status != 'hidden'"
        ).fetchall()

    def save_score(
        self, jid: str, score: int, fit_summary: str, strengths: list, gaps: list
    ) -> None:
        self.conn.execute(
            """UPDATE jobs SET score = ?, fit_summary = ?, strengths = ?, gaps = ?
               WHERE id = ?""",
            (score, fit_summary, json.dumps(strengths), json.dumps(gaps), jid),
        )
        self.conn.commit()

    def save_bullets(self, jid: str, bullets: list[str]) -> None:
        self.conn.execute(
            "UPDATE jobs SET bullets = ? WHERE id = ?", (json.dumps(bullets), jid)
        )
        self.conn.commit()

    def save_cover_letter(self, jid: str, letter: str) -> None:
        self.conn.execute(
            "UPDATE jobs SET cover_letter = ? WHERE id = ?", (letter, jid)
        )
        self.conn.commit()

    def set_status(self, jid: str, status: str, notes: str | None = None) -> bool:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        cur = self.conn.execute(
            "UPDATE jobs SET status = ?, status_updated = ?, "
            "notes = COALESCE(?, notes) WHERE id = ?",
            (status, _now(), notes, jid),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_job(self, jid: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone()

    def all_jobs(self, include_hidden: bool = False) -> list[dict]:
        query = "SELECT * FROM jobs"
        if not include_hidden:
            query += " WHERE status != 'hidden'"
        query += " ORDER BY score DESC NULLS LAST, first_seen DESC"
        rows = self.conn.execute(query).fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            job["strengths"] = json.loads(job["strengths"]) if job["strengths"] else []
            job["gaps"] = json.loads(job["gaps"]) if job["gaps"] else []
            job["bullets"] = json.loads(job["bullets"]) if job["bullets"] else []
            jobs.append(job)
        return jobs

    def stats(self) -> dict:
        row = self.conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) AS high,
                      SUM(CASE WHEN status NOT IN ('new', 'hidden') THEN 1 ELSE 0 END)
                          AS tracked
               FROM jobs WHERE status != 'hidden'"""
        ).fetchone()
        return dict(row)

    def close(self) -> None:
        self.conn.close()
