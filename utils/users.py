import sqlite3
import os
from telegram import User

# Определяем корневой каталог проекта: поднимаемся на один уровень от каталога utils
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(PROJECT_ROOT, "database")
DB_PATH = os.path.join(DB_DIR, "users.db")


def init_db():
    """
    Инициализирует базу данных и создаёт таблицу пользователей, если она не существует.
    Также включает WAL-режим для улучшения конкурентного доступа.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # Включаем WAL-режим для повышения производительности при многопоточном доступе
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_bot BOOLEAN
            )
        """)
        conn.commit()


def register_user(user: User):
    """
    Регистрирует пользователя или обновляет его данные в базе.
    """
    if not user:
        return
    with sqlite3.connect(DB_PATH) as conn:
        # Приводим username к нижнему регистру для единообразия
        username = user.username.lower() if user.username else None
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, last_name, is_bot)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                is_bot=excluded.is_bot
        """, (user.id, username, user.first_name, user.last_name, user.is_bot))
        conn.commit()


def get_user_id_by_username(username: str):
    """
    Поиск и возврат user_id по username (без '@').
    Поиск производится без учёта регистра.
    Если пользователь не найден, возвращает None.
    """
    username = username.strip().lower()  # удаляем лишние пробелы и приводим к нижнему регистру
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT user_id FROM users WHERE LOWER(username) = ?", (username,))
        row = cur.fetchone()
    return row["user_id"] if row else None


def get_user_info_by_id(user_id: int):
    """
    Возвращает словарь с данными пользователя по его ID.
    Если пользователь не найден, возвращает None.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT user_id, username, first_name, last_name, is_bot FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
    if row:
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "is_bot": bool(row["is_bot"])
        }
    return None


def get_all_users():
    """
    Возвращает список всех пользователей из базы данных.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT * FROM users")
        rows = cur.fetchall()
    return rows
