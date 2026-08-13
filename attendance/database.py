from __future__ import annotations

from pathlib import Path
import sqlite3

from .students import Student


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            student_index TEXT PRIMARY KEY,
            title TEXT,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            image_file TEXT NOT NULL,
            student_index TEXT NOT NULL,
            present INTEGER NOT NULL,
            ink_pixels INTEGER NOT NULL,
            ink_ratio REAL NOT NULL,
            confidence REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, student_index),
            FOREIGN KEY(student_index) REFERENCES students(student_index)
        );
        """
    )
    conn.commit()


def upsert_students(conn: sqlite3.Connection, students: list[Student]) -> None:
    conn.executemany(
        """
        INSERT INTO students(student_index, title, name)
        VALUES(?, ?, ?)
        ON CONFLICT(student_index) DO UPDATE SET
            title = excluded.title,
            name = excluded.name
        """,
        [(s.index, s.title, s.name) for s in students],
    )
    conn.commit()


def save_attendance(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO attendance(
            session_id, image_file, student_index, present,
            ink_pixels, ink_ratio, confidence
        )
        VALUES(
            :session_id, :image_file, :student_index, :present,
            :ink_pixels, :ink_ratio, :confidence
        )
        ON CONFLICT(session_id, student_index) DO UPDATE SET
            image_file = excluded.image_file,
            present = excluded.present,
            ink_pixels = excluded.ink_pixels,
            ink_ratio = excluded.ink_ratio,
            confidence = excluded.confidence,
            created_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    conn.commit()


def attendance_for_student(conn: sqlite3.Connection, student_index: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT a.session_id, a.image_file, a.present, a.ink_pixels,
               a.ink_ratio, a.confidence, a.created_at,
               s.name, s.title
        FROM attendance a
        JOIN students s ON s.student_index = a.student_index
        WHERE a.student_index = ?
        ORDER BY a.session_id
        """,
        (student_index,),
    ).fetchall()


def summary(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.student_index, s.name,
               COUNT(a.id) AS sessions,
               SUM(a.present) AS present_count,
               COUNT(a.id) - SUM(a.present) AS absent_count,
               ROUND(100.0 * SUM(a.present) / NULLIF(COUNT(a.id), 0), 2) AS percentage
        FROM students s
        LEFT JOIN attendance a ON a.student_index = s.student_index
        GROUP BY s.student_index, s.name
        ORDER BY s.student_index
        """
    ).fetchall()
