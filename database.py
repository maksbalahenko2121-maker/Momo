import sqlite3

import json

import time

 

DB_NAME = "tsundere.db"

 

def init_db():

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("""

        CREATE TABLE IF NOT EXISTS users (

            user_id INTEGER PRIMARY KEY,

            affection INTEGER DEFAULT 10,

            coins INTEGER DEFAULT 20,

            history TEXT DEFAULT '[]',

            last_active INTEGER DEFAULT 0

        )

    """)

    c.execute("""

        CREATE TABLE IF NOT EXISTS groups (

            chat_id INTEGER PRIMARY KEY,

            title TEXT

        )

    """)

    c.execute("""

        CREATE TABLE IF NOT EXISTS settings (

            key TEXT PRIMARY KEY,

            value TEXT

        )

    """)

    # Настройки по умолчанию

    defaults = [

        ("start_photo", ""),

        ("sub_required", "0"),

        ("sub_channel", ""),

        ("sub_link", "")

    ]

    for k, v in defaults:

        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()

    conn.close()

 

def get_setting(key: str) -> str:

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("SELECT value FROM settings WHERE key = ?", (key,))

    row = c.fetchone()

    conn.close()

    return row if row else ""

 

def set_setting(key: str, value: str):

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

    conn.commit()

    conn.close()

 

def get_user(user_id: int):

    now = int(time.time())

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("SELECT affection, coins, history FROM users WHERE user_id = ?", (user_id,))

    row = c.fetchone()

    if not row:

        c.execute(

            "INSERT INTO users (user_id, affection, coins, history, last_active) VALUES (?, 10, 20, '[]', ?)",

            (user_id, now)

        )

        conn.commit()

        affection, coins, history = 10, 20, []

    else:

        affection, coins, history = row, row, json.loads(row)

        c.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id))

        conn.commit()

    conn.close()

    return affection, coins, history

 

def update_user(user_id: int, affection: int, coins: int, history: list):

    now = int(time.time())

    affection = max(0, min(500, affection))

    coins = max(0, coins)

    history = history[-15:]

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute(

        "UPDATE users SET affection = ?, coins = ?, history = ?, last_active = ? WHERE user_id = ?",

        (affection, coins, json.dumps(history, ensure_ascii=False), now, user_id)

    )

    conn.commit()

    conn.close()

 

def register_group(chat_id: int, title: str):

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("INSERT OR REPLACE INTO groups (chat_id, title) VALUES (?, ?)", (chat_id, title))

    conn.commit()

    conn.close()

 

def get_all_users():

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("SELECT user_id FROM users")

    rows = [r for r in c.fetchall()]

    conn.close()

    return rows

 

def get_all_groups():

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("SELECT chat_id FROM groups")

    rows = [r for r in c.fetchall()]

    conn.close()

    return rows

 

def get_stats_data():

    now = int(time.time())

    conn = sqlite3.connect(DB_NAME)

    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")

    total_users = c.fetchone()

    c.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (now - 86400,))

    active_24h = c.fetchone()

    c.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (now - 604800,))

    active_7d = c.fetchone()

    c.execute("SELECT COUNT(*) FROM groups")

    total_groups = c.fetchone()

    conn.close()

    return total_users, active_24h, active_7d, total_groups
