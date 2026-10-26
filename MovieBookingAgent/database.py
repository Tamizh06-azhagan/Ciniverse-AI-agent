
import sqlite3

connection = sqlite3.connect("movies.db")
cursor = connection.cursor()

# Create movies table
cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    language TEXT,
    price INTEGER
)
""")

# Insert movies if table is empty
cursor.execute("SELECT COUNT(*) FROM movies")

if cursor.fetchone()[0] == 0:
    cursor.executemany(
        "INSERT INTO movies (name, language, price) VALUES (?, ?, ?)",
        [
            ("Leo", "Tamil", 150),
            ("Vikram", "Tamil", 180),
            ("Jailer", "Tamil", 160),
            ("Beast", "Tamil", 140)
        ]
    )

# Create showtimes table
cursor.execute("""
CREATE TABLE IF NOT EXISTS showtimes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_name TEXT NOT NULL,
    show_time TEXT NOT NULL
)
""")

# Insert showtimes
cursor.execute("DELETE FROM showtimes")

cursor.executemany(
    "INSERT INTO showtimes (movie_name, show_time) VALUES (?, ?)",
    [
        ("Leo", "10:00 AM"),
        ("Leo", "2:00 PM"),
        ("Leo", "6:00 PM"),
        ("Vikram", "11:00 AM"),
        ("Vikram", "3:00 PM"),
        ("Vikram", "7:00 PM"),
        ("Jailer", "10:30 AM"),
        ("Jailer", "2:30 PM"),
        ("Jailer", "6:30 PM"),
        ("Beast", "11:00 AM"),
        ("Beast", "4:00 PM"),
        ("Beast", "8:00 PM")
    ]
)

# Save database changes
connection.commit()

# Verify data
cursor.execute("SELECT COUNT(*) FROM movies")
movie_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM showtimes")
showtime_count = cursor.fetchone()[0]

print("Movie database created successfully!")
print("Total movies:", movie_count)
print("Total showtimes:", showtime_count)


# Create bookings table
cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    movie_name TEXT NOT NULL,
    show_time TEXT NOT NULL,
    ticket_count INTEGER NOT NULL,
    selected_seats TEXT NOT NULL,
    total_price INTEGER NOT NULL,
    booking_status TEXT NOT NULL DEFAULT 'CONFIRMED'
)
""")

connection.close()
