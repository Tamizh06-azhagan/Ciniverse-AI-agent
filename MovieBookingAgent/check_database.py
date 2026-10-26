
import sqlite3

connection = sqlite3.connect("movies.db")
cursor = connection.cursor()

cursor.execute("SELECT name FROM movies")
print("Movies:", cursor.fetchall())

cursor.execute("SELECT movie_name, show_time FROM showtimes")
print("Showtimes:", cursor.fetchall())

connection.close()
