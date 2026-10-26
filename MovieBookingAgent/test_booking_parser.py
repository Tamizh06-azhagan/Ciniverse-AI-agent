
import re

def parse_booking_request(user_message):
    message = user_message.lower()

    movies = [
        {"name": "Leo"},
        {"name": "Jailer"},
        {"name": "Vikram"},
        {"name": "Beast"}
    ]

    movie_name = next(
        (
            movie["name"]
            for movie in movies
            if movie["name"].lower() in message
        ),
        None
    )

    showtime = next(
        (
            time
            for time in ["10:00 AM", "2:00 PM", "6:00 PM"]
            if time.lower() in message
        ),
        None
    )

    seats = re.findall(r"\b([A-Da-d][1-6])\b", user_message)
    seats = list(dict.fromkeys(seat.upper() for seat in seats))

    if not movie_name and not showtime and not seats:
        return None

    return {
        "movie_name": movie_name,
        "showtime": showtime,
        "seats": seats,
        "ticket_count": len(seats) if seats else None
    }


request = "Leo movie, 2:00 PM show, A1, A2 book now"
print(parse_booking_request(request))
