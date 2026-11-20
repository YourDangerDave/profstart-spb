import sqlite3
from pathlib import Path
from typing import Dict, Any, List

DB_PATH = Path(__file__).resolve().parent / "profstart.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Создаёт таблицу результатов, если её ещё нет."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                grade TEXT NOT NULL,
                open_answer TEXT,
                top_profile_title TEXT NOT NULL,
                top_percent INTEGER NOT NULL,
                summary TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def save_assessment(
    student_name: str,
    grade: str,
    open_answer: str,
    analysis: Dict[str, Any],
) -> int:
    """Сохраняет результат анализа и возвращает ID записи."""
    top = analysis["top_profile"]
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO assessments (
                student_name, grade, open_answer,
                top_profile_title, top_percent, summary
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_name.strip() or "Ученик СПб",
                grade.strip() or "9 класс",
                (open_answer or "").strip(),
                top["title"],
                int(top["percent"]),
                analysis["summary"],
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_recent_assessments(limit: int = 8) -> List[Dict[str, Any]]:
    """Возвращает последние прохождения для блока истории на странице."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, student_name, grade, top_profile_title, top_percent, created_at
            FROM assessments
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def clear_assessments() -> None:
    """Удаляет все записи из таблицы результатов и сбрасывает автоинкремент."""
    with get_connection() as conn:
        conn.execute("DELETE FROM assessments")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'assessments'")
        conn.commit()