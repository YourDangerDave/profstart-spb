import hashlib
import json
import os
import random
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional

DB_PATH = Path(__file__).resolve().parent / "profstart.db"

AVATAR_ANIMALS = [
    {"id": "fox", "label": "Лиса", "emoji": "🦊"},
    {"id": "owl", "label": "Сова", "emoji": "🦉"},
    {"id": "wolf", "label": "Волк", "emoji": "🐺"},
    {"id": "cat", "label": "Кот", "emoji": "🐱"},
    {"id": "panda", "label": "Панда", "emoji": "🐼"},
    {"id": "dolphin", "label": "Дельфин", "emoji": "🐬"},
]


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    clean_pw = password or "1234"
    use_salt = salt or os.urandom(8).hex()
    digest = hashlib.pbkdf2_hmac("sha256", clean_pw.encode("utf-8"), use_salt.encode("utf-8"), 100_000).hex()
    return f"{use_salt}${digest}"


def _verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored or "$" not in stored:
        return True
    salt, expected = stored.split("$", 1)
    actual = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return actual == expected


def normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    return f"+{digits}" if digits else ""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'teacher')),
                full_name TEXT NOT NULL,
                email TEXT DEFAULT '',
                grade TEXT DEFAULT '9 класс',
                track_goal TEXT DEFAULT 'пока изучаю варианты',
                avatar_id TEXT DEFAULT 'owl',
                notify_updates INTEGER DEFAULT 1,
                classroom_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS classrooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                teacher_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_guidance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                classroom_code TEXT NOT NULL,
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                requirement_text TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(classroom_code, student_id),
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (teacher_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                classroom_code TEXT,
                student_name TEXT NOT NULL,
                grade TEXT NOT NULL,
                open_answer TEXT,
                top_profile_title TEXT NOT NULL,
                top_percent INTEGER NOT NULL,
                summary TEXT NOT NULL,
                full_report_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def get_user_by_id(user_id: Optional[int]) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    clean_phone = normalize_phone(phone)
    if not clean_phone:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (clean_phone,)).fetchone()
    return dict(row) if row else None


def register_user(phone: str, password: str, role: str, full_name: str) -> Dict[str, Any]:
    clean_phone = normalize_phone(phone)
    clean_role = "teacher" if role == "teacher" else "student"
    clean_name = (full_name or "").strip() or (
        "Классный руководитель" if clean_role == "teacher" else "Ученик СПб"
    )
    default_avatar = "owl" if clean_role == "teacher" else "fox"
    pw_hash = _hash_password(password)

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (phone, password_hash, role, full_name, avatar_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (clean_phone, pw_hash, clean_role, clean_name, default_avatar),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)


def authenticate_user(phone: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_phone(phone)
    if not user:
        return None
    if not _verify_password(password, user.get("password_hash")):
        return None
    return user


def update_user_settings(
    user_id: int,
    full_name: str,
    email: str,
    grade: str,
    track_goal: str,
    avatar_id: str,
    notify_updates: bool,
) -> None:
    valid_avatars = {item["id"] for item in AVATAR_ANIMALS}
    safe_avatar = avatar_id if avatar_id in valid_avatars else "owl"
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET full_name = ?, email = ?, grade = ?, track_goal = ?, avatar_id = ?, notify_updates = ?
            WHERE id = ?
            """,
            (
                (full_name or "").strip() or "Пользователь СПб",
                (email or "").strip(),
                (grade or "9 класс").strip(),
                (track_goal or "пока изучаю варианты").strip(),
                safe_avatar,
                1 if notify_updates else 0,
                user_id,
            ),
        )
        conn.commit()


def create_classroom(teacher_id: int, title: str) -> Dict[str, Any]:
    clean_title = (title or "").strip() or "Класс СПб"
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM classrooms WHERE teacher_id = ? ORDER BY id DESC LIMIT 1",
            (teacher_id,),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE classrooms SET title = ? WHERE id = ?",
                (clean_title, existing["id"]),
            )
            conn.execute(
                "UPDATE users SET classroom_code = ? WHERE id = ?",
                (existing["code"], teacher_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM classrooms WHERE id = ?", (existing["id"],)).fetchone()
            return dict(row)

        while True:
            code = f"SPB-{random.randint(100, 999)}-{random.choice(['A', 'B', 'K', 'T', 'M'])}"
            taken = conn.execute("SELECT 1 FROM classrooms WHERE code = ?", (code,)).fetchone()
            if not taken:
                break

        cursor = conn.execute(
            "INSERT INTO classrooms (code, title, teacher_id) VALUES (?, ?, ?)",
            (code, clean_title, teacher_id),
        )
        conn.execute("UPDATE users SET classroom_code = ? WHERE id = ?", (code, teacher_id))
        conn.commit()
        row = conn.execute("SELECT * FROM classrooms WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)


def get_teacher_classroom(teacher_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM classrooms WHERE teacher_id = ? ORDER BY id DESC LIMIT 1",
            (teacher_id,),
        ).fetchone()
    return dict(row) if row else None


def get_classroom_by_code(code: Optional[str]) -> Optional[Dict[str, Any]]:
    clean_code = (code or "").strip().upper()
    if not clean_code:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM classrooms WHERE code = ?", (clean_code,)).fetchone()
    return dict(row) if row else None


def join_or_leave_classroom(student_id: int, code: Optional[str]) -> bool:
    clean_code = (code or "").strip().upper()
    with get_connection() as conn:
        if not clean_code:
            conn.execute("UPDATE users SET classroom_code = NULL WHERE id = ?", (student_id,))
            conn.commit()
            return True
        room = conn.execute("SELECT * FROM classrooms WHERE code = ?", (clean_code,)).fetchone()
        if not room:
            return False
        conn.execute(
            "UPDATE users SET classroom_code = ? WHERE id = ?",
            (clean_code, student_id),
        )
        conn.commit()
        return True


def set_student_guidance(
    classroom_code: str,
    student_id: int,
    teacher_id: int,
    requirement_text: str,
) -> None:
    clean_text = (requirement_text or "").strip()
    with get_connection() as conn:
        if not clean_text:
            conn.execute(
                "DELETE FROM student_guidance WHERE classroom_code = ? AND student_id = ?",
                (classroom_code, student_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO student_guidance (classroom_code, student_id, teacher_id, requirement_text, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(classroom_code, student_id)
                DO UPDATE SET
                    teacher_id = excluded.teacher_id,
                    requirement_text = excluded.requirement_text,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (classroom_code, student_id, teacher_id, clean_text),
            )
        conn.commit()


def get_guidance_for_student(student_id: int, classroom_code: Optional[str]) -> Optional[Dict[str, Any]]:
    if not classroom_code:
        return None
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT g.*, u.full_name AS teacher_name
            FROM student_guidance g
            LEFT JOIN users u ON u.id = g.teacher_id
            WHERE g.student_id = ? AND g.classroom_code = ?
            """,
            (student_id, classroom_code),
        ).fetchone()
    return dict(row) if row else None


def get_classroom_students_overview(classroom_code: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        students = conn.execute(
            """
            SELECT u.*, g.requirement_text, g.updated_at AS guidance_updated_at
            FROM users u
            LEFT JOIN student_guidance g
              ON g.student_id = u.id AND g.classroom_code = ?
            WHERE u.role = 'student' AND u.classroom_code = ?
            ORDER BY u.full_name ASC
            """,
            (classroom_code, classroom_code),
        ).fetchall()

        result: List[Dict[str, Any]] = []
        for st in students:
            st_dict = dict(st)
            latest = conn.execute(
                """
                SELECT * FROM assessments
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (st["id"],),
            ).fetchone()
            st_dict["latest_assessment"] = _hydrate_assessment(dict(latest)) if latest else None
            result.append(st_dict)
    return result


def save_assessment(
    student_name: str,
    grade: str,
    open_answer: str,
    analysis: Dict[str, Any],
    user_id: Optional[int] = None,
    classroom_code: Optional[str] = None,
) -> int:
    top = analysis["top_profile"]
    payload = {
        "open_answer": (open_answer or "").strip(),
        "top_profile": top,
        "secondary_profile": analysis.get("secondary_profile"),
        "personality_portrait": analysis.get("personality_portrait", ""),
        "full_advice": analysis.get("full_advice", []),
        "breakdown": analysis.get("breakdown", []),
        "matched_keywords": analysis.get("matched_keywords", []),
        "track_goal": analysis.get("track_goal", "пока изучаю варианты"),
        "summary": analysis.get("summary", ""),
    }
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO assessments (
                user_id, classroom_code, student_name, grade, open_answer,
                top_profile_title, top_percent, summary, full_report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                classroom_code,
                (student_name or "").strip() or "Гость из СПб",
                (grade or "9 класс").strip(),
                (open_answer or "").strip(),
                top["title"],
                int(top["percent"]),
                analysis["summary"],
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def _hydrate_assessment(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    raw_json = row_dict.get("full_report_json") or "{}"
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        parsed = {}
    row_dict["report"] = parsed
    return row_dict


def get_assessment_by_id(assessment_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
    return _hydrate_assessment(dict(row)) if row else None


def get_user_assessments(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM assessments
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [_hydrate_assessment(dict(r)) for r in rows]


def get_recent_assessments(limit: int = 10) -> List[Dict[str, Any]]:
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
    with get_connection() as conn:
        conn.execute("DELETE FROM assessments")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'assessments'")
        conn.commit()
