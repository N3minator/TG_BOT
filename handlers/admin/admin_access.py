import sqlite3

DB_PATH = "database/moderation.db"


# Проверка на доступ к созданию кастомных ролей
def has_permission_to_create_admin(chat_id: int, user_id: int) -> bool:
    return has_access(chat_id, user_id, "!new-role")


# Проверка: есть ли у пользователя доступ к конкретной команде
def has_access(chat_id: int, user_id: int, command: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем роли пользователя
    cursor.execute("SELECT role FROM user_roles WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    roles = [row[0] for row in cursor.fetchall()]

    # Проверка владельца
    try:
        cursor.execute("SELECT status FROM chat_members WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        status = cursor.fetchone()
        if status and status[0] == "creator":
            conn.close()
            return True
    except:
        pass

    # Проверка наличия разрешения хотя бы у одной из ролей
    for role in roles:
        cursor.execute("SELECT 1 FROM admin_permissions WHERE chat_id = ? AND role = ? AND command = ?",
                       (chat_id, role, command))
        if cursor.fetchone():
            conn.close()
            return True

    conn.close()
    return False
