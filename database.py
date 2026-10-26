import sqlite3
from contextlib import closing

MOVIES = [
    ("Leo", "Tamil", 150),
    ("Vikram", "Tamil", 180),
    ("Jailer", "Tamil", 160),
    ("Beast", "Tamil", 140),
]

SHOWTIMES = [
    ("Leo", "10:00 AM"), ("Leo", "2:00 PM"), ("Leo", "6:00 PM"),
    ("Vikram", "11:00 AM"), ("Vikram", "3:00 PM"), ("Vikram", "7:00 PM"),
    ("Jailer", "10:30 AM"), ("Jailer", "2:30 PM"), ("Jailer", "6:30 PM"),
    ("Beast", "11:00 AM"), ("Beast", "4:00 PM"), ("Beast", "8:00 PM"),
]


def init_db(db_path):
    """Create and seed the catalogue tables. Safe to call on every run."""
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                language TEXT,
                price INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS showtimes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_name TEXT NOT NULL,
                show_time TEXT NOT NULL
            )
        """)
        if conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO movies (name, language, price) VALUES (?, ?, ?)", MOVIES)
        if conn.execute("SELECT COUNT(*) FROM showtimes").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO showtimes (movie_name, show_time) VALUES (?, ?)", SHOWTIMES)
        conn.commit()