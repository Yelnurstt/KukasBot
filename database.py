import aiosqlite

DB_NAME = "akimat_appointments.db"

async def init_db():
    """Создает таблицу в базе данных, если её нет."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                reason TEXT,
                datetime TEXT,
                name TEXT,
                phone TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        await db.commit()

async def add_appointment(user_id: int, username: str, reason: str, dt: str, name: str, phone: str):
    """Сохраняет новую заявку в базу данных."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            INSERT INTO appointments (user_id, username, reason, datetime, name, phone)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, reason, dt, name, phone))
        await db.commit()