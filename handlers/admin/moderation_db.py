import sqlite3
import os
from datetime import datetime

# Путь к SQLite базе данных
DB_PATH = "database/moderation.db"


# 📌 Получение всех кастомных ролей пользователей в группе
def get_all_user_roles(chat_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, role FROM user_roles WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchall()
    conn.close()
    return result


# 📌 Инициализация таблиц в БД
def init_moderation_db():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Таблица кастомных ролей
    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_admins (
            group_id INTEGER,
            title TEXT,
            created_by INTEGER,
            created_at TEXT,
            level INTEGER DEFAULT 99,
            PRIMARY KEY (group_id, title)
        )
    """)

    # Таблица прав ролей (по командам)
    c.execute("""
        CREATE TABLE IF NOT EXISTS admin_permissions (
            chat_id INTEGER,
            role TEXT,
            command TEXT,
            PRIMARY KEY (chat_id, role, command)
        )
    """)

    conn.commit()
    conn.close()


# 📌 Создание кастомной роли
def create_custom_admin(group_id: int, title: str, created_by: int, level: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO custom_admins (group_id, title, created_by, created_at, level)
            VALUES (?, ?, ?, ?, ?)
        """, (group_id, title, created_by, datetime.utcnow().isoformat(), level))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Уже существует
    finally:
        conn.close()


# 📌 Проверка наличия кастомной роли
def custom_admin_exists(group_id: int, title: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM custom_admins WHERE group_id = ? AND title = ?", (group_id, title))
    exists = c.fetchone() is not None
    conn.close()
    return exists


# 📌 Инициализация таблицы user_roles
def init_user_roles_db():
    os.makedirs("database", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
        chat_id INTEGER,
        user_id INTEGER,
        role TEXT,
        PRIMARY KEY (chat_id, user_id, role)
        )
    """)
    conn.commit()
    conn.close()


# 📌 Назначение кастомной роли пользователю
def assign_user_to_role(chat_id: int, user_id: int, role: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO user_roles (chat_id, user_id, role)
        VALUES (?, ?, ?)
    """, (chat_id, user_id, role))
    conn.commit()
    conn.close()


# 📌 Проверка существования роли
def role_exists(chat_id: int, role: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM custom_admins WHERE group_id = ? AND title = ?", (chat_id, role))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


# 📌 Удаление кастомной роли
def delete_custom_admin_role(chat_id: int, role: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_admins WHERE group_id = ? AND title = ?", (chat_id, role))
    conn.commit()
    conn.close()


# 📌 Удаление роли у всех пользователей
def remove_role_from_all_users(chat_id: int, role: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_roles WHERE chat_id = ? AND role = ?", (chat_id, role))
    conn.commit()
    conn.close()


# 📌 Получение всех разрешённых команд для роли
def get_admin_permissions_for_role(chat_id: int, role: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Гарантия наличия таблицы
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_permissions (
            chat_id INTEGER,
            role TEXT,
            command TEXT,
            PRIMARY KEY (chat_id, role, command)
        )
    """)

    cursor.execute(
        "SELECT command FROM admin_permissions WHERE chat_id = ? AND role = ?",
        (chat_id, role)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


# 📌 Переключение права команды (вкл/выкл)
def toggle_admin_permission(chat_id: int, role: str, command: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Проверяем, разрешено ли уже право
    cursor.execute("""
        SELECT 1 FROM admin_permissions
        WHERE chat_id = ? AND role = ? AND command = ?
    """, (chat_id, role, command))
    exists = cursor.fetchone()

    if exists:
        # Если есть — удаляем (запрещаем)
        cursor.execute("""
            DELETE FROM admin_permissions
            WHERE chat_id = ? AND role = ? AND command = ?
        """, (chat_id, role, command))
    else:
        # Если нет — добавляем (разрешаем)
        cursor.execute("""
            INSERT INTO admin_permissions (chat_id, role, command)
            VALUES (?, ?, ?)
        """, (chat_id, role, command))

    conn.commit()
    conn.close()


# Эта функция возвращает минимальный числовой уровень (например, 1, 2, 3...), где 1 — самый высокий (по иерархии, как в Discord).
def get_user_max_role_level(chat_id: int, user_id: int) -> int:
    """
    Возвращает минимальный (высший) уровень роли пользователя.
    Если ролей нет — возвращает 100 по умолчанию.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем список всех ролей пользователя
    cursor.execute("""
        SELECT ur.role, ca.level
        FROM user_roles ur
        JOIN custom_admins ca ON ur.role = ca.title AND ur.chat_id = ca.group_id
        WHERE ur.chat_id = ? AND ur.user_id = ?
    """, (chat_id, user_id))
    results = cursor.fetchall()
    conn.close()

    if not results:
        return 100  # значение по умолчанию, если нет ролей

    # выбираем минимальный уровень (наивысший приоритет)
    return min(level for _, level in results)


def get_all_roles_with_levels(chat_id: int) -> dict:
    """
    Возвращает словарь {название_роли: уровень} для всех ролей в группе.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, level FROM custom_admins WHERE group_id = ?", (chat_id,))
    results = cursor.fetchall()
    conn.close()
    return {title: level for title, level in results}


def get_user_roles(chat_id: int, user_id: int) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM user_roles WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    roles = [row[0] for row in cursor.fetchall()]
    conn.close()
    return roles


def get_role_level(chat_id: int, role: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT level FROM custom_admins WHERE group_id = ? AND title = ?", (chat_id, role))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 99  # если роль не найдена — возвращаем уровень по умолчанию


def get_highest_admin_level(chat_id: int, user_id: int) -> int:
    roles = get_user_roles(chat_id, user_id)
    levels = [get_role_level(chat_id, role) for role in roles]
    return min(levels) if levels else 99  # чем меньше уровень, тем он выше


def rename_custom_admin(chat_id: int, old_title: str, new_title: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE custom_admins SET title = ?
        WHERE group_id = ? AND title = ?
    """, (new_title, chat_id, old_title))

    cursor.execute("""
        UPDATE user_roles SET role = ?
        WHERE chat_id = ? AND role = ?
    """, (new_title, chat_id, old_title))

    cursor.execute("""
        UPDATE admin_permissions SET role = ?
        WHERE chat_id = ? AND role = ?
    """, (new_title, chat_id, old_title))
    conn.commit()
    conn.close()


def update_role_level(chat_id: int, role: str, level: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE custom_admins SET level = ?
        WHERE group_id = ? AND title = ?
    """, (level, chat_id, role))
    conn.commit()
    conn.close()

