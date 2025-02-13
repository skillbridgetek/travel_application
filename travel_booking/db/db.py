import psycopg2
from psycopg2 import sql
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseConnection:
    def __init__(self, host, database, user, password):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.connection = None

    def __enter__(self):
        self.connection = psycopg2.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password
        )
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        if self.connection:
            self.connection.close()
        if exc_type is not None:
            logger.error("Exception occurred: %s", exc_value)
        print("Database connection closed.")

class PlaceDetails:
    def __init__(self, place_id, name,location,description,cost,image):
        self.id = place_id
        self.name = name
        self.location = location
        self.description = description



    def __str__(self):
        return (f"place_id: {self.id}, Name: {self.name}, Description: {self.desc[:60]}..., "
                f"Location: {self.location}")


class Places:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def fetch_places(self, search_term=None):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM place"
            if search_term:
                query += " WHERE name ILIKE %s OR location ILIKE %s"
                cursor.execute(query, (f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute(query)
            places_data = cursor.fetchall()
            cursor.close()
        places = [PlaceDetails(*place_data) for place_data in places_data]
        return places

    # def get_place_by_id(self, place_id):
    #     with DatabaseConnection(*self.db_params) as conn:
    #         cursor = conn.cursor()
    #         query = "SELECT * FROM place WHERE place_id = %s"
    #         cursor.execute(query, (place_id,))
    #         place_data = cursor.fetchone()
    #         cursor.close()
    #     if place_data:
    #         return PlaceDetails(*place_data)
    #     return None

    def add_place(self,name,location,description):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO place (name,location,description)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (name,location, description))
            conn.commit()
            cursor.close()

    def remove_place(self, place_id):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "DELETE FROM place WHERE place_id = %s"
            cursor.execute(query, (place_id,))
            conn.commit()
            cursor.close()

    def get_place_by_id(self, place_id):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM place WHERE place_id = %s"
            cursor.execute(query, (place_id,))
            place_data = cursor.fetchone()
            cursor.close()
        if place_data:
            return PlaceDetails(*place_data)
        return None


class User:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def add_user(self, name, email, password):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            query = "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)"
            try:
                cursor.execute(query, (name, email, hashed_password))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("Error adding user: %s", str(e))
                raise e
            finally:
                cursor.close()

    def verify_user(self, email, password):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT password FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            cursor.close()
        if result and check_password_hash(result[0], password):
            return True
        return False

    def get_user(self, email):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT name, email, first_time_discount_used FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            cursor.close()
        if result:
            return {"name": result[0], "email": result[1], "first_time_discount_used": result[2]}
        return None

    def set_first_time_discount_used(self, email):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "UPDATE users SET first_time_discount_used = TRUE WHERE email = %s"
            cursor.execute(query, (email,))
            conn.commit()
            cursor.close()

    def update_user(self, current_email, name, email, password):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(password) if password else None
            query = "UPDATE users SET name = %s, email = %s"
            params = [name, email]
            if hashed_password:
                query += ", password = %s"
                params.append(hashed_password)
            query += " WHERE email = %s"
            params.append(current_email)
            try:
                cursor.execute(query, tuple(params))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("Error updating user: %s", str(e))
                raise e
            finally:
                cursor.close()

    def add_course_to_profile(self, user_email, course_id):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "INSERT INTO user_courses (user_email, course_id) VALUES (%s, %s)"
            try:
                cursor.execute(query, (user_email, course_id))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("Error adding course to profile: %s", str(e))
                raise e
            finally:
                cursor.close()

    def get_user_courses(self, user_email):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = """
                   SELECT courses.id, courses.name, courses.description
                   FROM courses
                   JOIN user_courses ON courses.id = user_courses.course_id
                   WHERE user_courses.user_email = %s
               """
            cursor.execute(query, (user_email,))
            result = cursor.fetchall()
            cursor.close()
        return result


class Admin:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def add_user(self, name, email, password):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            query = "INSERT INTO admin (name, email, password) VALUES (%s, %s, %s)"
            try:
                cursor.execute(query, (name, email, hashed_password))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("Error adding admin: %s", str(e))
                raise e
            finally:
                cursor.close()

    def verify_user(self, email, password):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT password FROM admin WHERE email = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            cursor.close()
        if result and check_password_hash(result[0], password):
            return True
        return False

    def get_user(self, email):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT name, email FROM admin WHERE email = %s"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            cursor.close()
        if result:
            return {"name": result[0], "email": result[1]}
        return None

    def update_user(self, current_email, name, email, password):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            hashed_password = generate_password_hash(password) if password else None
            query = "UPDATE admin SET name = %s, email = %s"
            params = [name, email]
            if hashed_password:
                query += ", password = %s"
                params.append(hashed_password)
            query += " WHERE email = %s"
            params.append(current_email)
            try:
                cursor.execute(query, tuple(params))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("Error updating admin: %s", str(e))
                raise e
            finally:
                cursor.close()


# CREATE TABLE users (
#     id SERIAL PRIMARY KEY,
#     name VARCHAR(255) NOT NULL,
#     email VARCHAR(255) UNIQUE NOT NULL,
#     password VARCHAR(255) NOT NULL,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );

class Cart:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def add_to_cart(self, user_email, hotel_id, people, days):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO cart (user_email, hotel_id, people, days) VALUES (%s, %s, %s, %s)",
                           (user_email, hotel_id, people, days))
            conn.commit()
            cursor.close()

    def get_cart_items(self, user_email):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.hotel_id, h.name, h.location, h.place, h.price_per_night, c.people,c.check_in,c.check_out, c.days
                FROM cart c
                JOIN hotels h ON c.hotel_id = h.id
                WHERE c.user_email = %s
                
            """, (user_email,))
            result = cursor.fetchall()
            cursor.close()
        return result

    def update_cart_item(self, cart_id, people, days, check_in, check_out):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = """
                UPDATE cart 
                SET people = %s, days = %s, check_in = %s, check_out = %s 
                WHERE id = %s
            """
            cursor.execute(query, (people, days, check_in, check_out, cart_id))
            conn.commit()
            cursor.close()

    def remove_from_cart(self, cart_id):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cart WHERE id = %s", (cart_id,))
            conn.commit()
            cursor.close()

    def clear_cart(self, user_email):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cart WHERE user_email = %s", (user_email,))
            conn.commit()
            cursor.close()

# class Cart:
#     def __init__(self, host, database, user, password):
#         self.db_params = (host, database, user, password)
#
#     def add_place_to_cart(self, user_email, place_id, people, days):
#         with DatabaseConnection(*self.db_params) as conn:
#             cursor = conn.cursor()
#             cursor.execute("INSERT INTO cart (user_email, place_id, people, days, type) VALUES (%s, %s, %s, %s, 'place')",
#                            (user_email, place_id, people, days))
#             conn.commit()
#             cursor.close()
#
#     def add_hotel_to_cart(self, user_email, hotel_id, people, days):
#         with DatabaseConnection(*self.db_params) as conn:
#             cursor = conn.cursor()
#             cursor.execute("INSERT INTO cart (user_email, hotel_id, people, days, type) VALUES (%s, %s, %s, %s, 'hotel')",
#                            (user_email, hotel_id, people, days))
#             conn.commit()
#             cursor.close()
#
#     def get_cart_items(self, user_email):
#         with DatabaseConnection(*self.db_params) as conn:
#             cursor = conn.cursor()
#
#             # Execute the query to get the 'type' field for the given user_email
#             cursor.execute("""SELECT type FROM cart WHERE user_email = %s LIMIT 1""", (user_email,))
#
#             # Fetch the result
#             value_type = cursor.fetchone()
#
#             # Check if any cart items were found, otherwise return an empty list or handle it
#             if value_type is None:
#                 print("No cart items found for this user.")
#                 return []  # No items in the cart
#
#             # Now check the type and retrieve the appropriate items
#             if value_type[0] == "place":
#                 cursor.execute("""
#                     SELECT c.id, c.place_id, p.name, p.location, p.description, p.cost, c.people, c.days, c.type
#                     FROM cart c
#                     LEFT JOIN place p ON c.place_id = p.place_id
#                     LEFT JOIN hotels h ON c.hotel_id = h.id
#                     WHERE c.user_email = %s
#                 """, (user_email,))
#                 result = cursor.fetchall()
#                 cursor.close()
#                 return result
#             elif value_type[0] == "hotel":
#                 cursor.execute("""
#                     SELECT c.id, c.hotel_id, h.name, h.location, h.place, h.price_per_night, c.people, c.days, c.type
#                     FROM cart c
#                     LEFT JOIN place p ON c.place_id = p.place_id
#                     LEFT JOIN hotels h ON c.hotel_id = h.id
#                     WHERE c.user_email = %s
#                 """, (user_email,))
#                 result = cursor.fetchall()
#                 cursor.close()
#                 return result
#
    # def update_cart_item(self, cart_id, people, days):
    #     with DatabaseConnection(*self.db_params) as conn:
    #         cursor = conn.cursor()
    #         cursor.execute("UPDATE cart SET people = %s, days = %s WHERE id = %s",
    #                        (people, days, cart_id))
    #         conn.commit()
    #         cursor.close()
#
#     def remove_from_cart(self, cart_id):
#         with DatabaseConnection(*self.db_params) as conn:
#             cursor = conn.cursor()
#             cursor.execute("DELETE FROM cart WHERE id = %s", (cart_id,))
#             conn.commit()
#             cursor.close()
#
#     def clear_cart(self, user_email):
#         with DatabaseConnection(*self.db_params) as conn:
#             cursor = conn.cursor()
#             cursor.execute("DELETE FROM cart WHERE user_email = %s", (user_email,))
#             conn.commit()
#             cursor.close()


class Bookings:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def add_booking(self, user_email, hotel_id, people, check_in, check_out, days, total_cost):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = """
                INSERT INTO bookings (user_email, hotel_id, people, check_in, check_out, days, total_cost)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (user_email, hotel_id, people, check_in, check_out, days, total_cost))
            conn.commit()
            cursor.close()

    def get_bookings(self, user_email):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = """
                SELECT b.id, h.name, h.location, h.place, h.price_per_night, b.people, b.days, b.total_cost
                FROM bookings b
                JOIN hotels h ON b.hotel_id = h.id
                WHERE b.user_email = %s
            """
            cursor.execute(query, (user_email,))
            result = cursor.fetchall()
            cursor.close()
        return result

    def check_availability(self, hotel_id, check_in, check_out):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = """
                SELECT * FROM bookings
                WHERE hotel_id = %s AND (
                    (%s BETWEEN check_in AND check_out) OR
                    (%s BETWEEN check_in AND check_out) OR
                    (check_in BETWEEN %s AND %s)
                )
            """
            cursor.execute(query, (hotel_id, check_in, check_out, check_in, check_out))
            bookings = cursor.fetchall()
            cursor.close()
        return len(bookings) == 0  # True if available, False if not

# class Bookings:
#     def __init__(self, host, database, user, password):
#         self.db_params = (host, database, user, password)
#
#     def add_booking(self, user_email, item_id, people, days, total_cost, booking_type):
#         with DatabaseConnection(*self.db_params) as conn:
#             cursor = conn.cursor()
#             if booking_type == 'place':
#                 cursor.execute(
#                     "INSERT INTO bookings (user_email, place_id, people, days, total_cost, type) VALUES (%s, %s, %s, %s, %s, %s)",
#                     (user_email, item_id, people, days, total_cost, 'place')
#                 )
#             elif booking_type == 'hotel':
#                 cursor.execute(
#                     "INSERT INTO bookings (user_email, hotel_id, people, days, total_cost, type) VALUES (%s, %s, %s, %s, %s, %s)",
#                     (user_email, item_id, people, days, total_cost, 'hotel')
#                 )
#             conn.commit()
#             cursor.close()
#
#     def get_bookings_by_type(self, user_email, booking_type):
#         with DatabaseConnection(*self.db_params) as conn:
#             cursor = conn.cursor()
#             if booking_type == 'place':
#                 cursor.execute(
#                     "SELECT b.id, p.name, p.location, p.description, p.cost, b.people, b.days, b.total_cost "
#                     "FROM bookings b JOIN place p ON b.place_id = p.place_id "
#                     "WHERE b.user_email = %s AND b.type = %s",
#                     (user_email, 'place')
#                 )
#             elif booking_type == 'hotel':
#                 cursor.execute(
#                     "SELECT b.id, h.name, h.location, h.place, h.price_per_night, b.people, b.days, b.total_cost "
#                     "FROM bookings b JOIN hotels h ON b.hotel_id = h.id "
#                     "WHERE b.user_email = %s AND b.type = %s",
#                     (user_email, 'hotel')
#                 )
#             result = cursor.fetchall()
#             cursor.close()
#         return result


class HotelDetails:
    def __init__(self, hotel_id, name, location, place, price_per_night):
        self.id = hotel_id
        self.name = name
        self.location = location
        self.place = place
        self.price_per_night = price_per_night

    def __str__(self):
        return (f"Hotel ID: {self.id}, Name: {self.name}, Location: {self.location}, "
                f"Place: {self.place}, Price per Night: {self.price_per_night}")


class Hotels:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def fetch_hotels(self, search_term='', check_in_date=None, check_out_date=None):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()

            # Base query to filter by search term
            query = """
                SELECT * FROM hotels h
                WHERE h.place ILIKE %s
            """
            params = [f'%{search_term}%']

            # If dates are provided, ensure the hotel is available during the given period
            if check_in_date and check_out_date:
                query += """
                    AND NOT EXISTS (
                        SELECT 1 FROM bookings b
                        WHERE b.hotel_id = h.id
                        AND (
                            (%s BETWEEN b.check_in AND b.check_out) OR
                            (%s BETWEEN b.check_in AND b.check_out) OR
                            (b.check_in BETWEEN %s AND %s)
                        )
                    )
                """
                params.extend([check_in_date, check_out_date, check_in_date, check_out_date])

            cursor.execute(query, tuple(params))
            hotels_data = cursor.fetchall()
            cursor.close()

        # Convert the result into HotelDetails objects
        return [HotelDetails(*hotel) for hotel in hotels_data]

    def add_hotel(self, name, location, place, price_per_night):
        """Add a new hotel to the database."""
        try:
            with DatabaseConnection(*self.db_params) as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO hotels (name, location, place, price_per_night)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (name, location, place, price_per_night))
                conn.commit()

        except Exception as e:
            print(f"Error adding hotel: {e}")

    def remove_hotel(self, hotel_id):
        """Remove a hotel from the database by ID."""
        try:
            with DatabaseConnection(*self.db_params) as conn:
                cursor = conn.cursor()
                query = "DELETE FROM hotels WHERE id = %s"
                cursor.execute(query, (hotel_id,))
                conn.commit()

        except Exception as e:
            print(f"Error removing hotel: {e}")


#TICKETS


class Ticket:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def create_ticket(self, user_name, user_email, complaint):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "INSERT INTO tickets (user_name, user_email, complaint, status) VALUES (%s, %s, %s, %s) RETURNING id"
            cursor.execute(query, (user_name, user_email, complaint, "open"))
            ticket_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
        return ticket_id

    def get_user_tickets(self, user_email):
        """ Fetch all tickets created by a specific user """
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT id, complaint, status FROM tickets WHERE user_email = %s ORDER BY id DESC"
            cursor.execute(query, (user_email,))
            tickets = cursor.fetchall()
            cursor.close()

        # Convert the result from tuples to dictionaries
        return [{"id": t[0], "complaint": t[1], "status": t[2]} for t in tickets]

    def get_tickets(self):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT id, user_name, complaint, status FROM tickets ORDER BY id DESC"
            cursor.execute(query)
            tickets = cursor.fetchall()
            cursor.close()

        # Convert the result from tuples to dictionaries
        return [{"id": t[0], "user_name": t[1], "complaint": t[2], "status": t[3]} for t in tickets]

    def update_ticket_status(self, ticket_id, new_status):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "UPDATE tickets SET status = %s WHERE id = %s"
            cursor.execute(query, (new_status, ticket_id))
            conn.commit()
            cursor.close()

    def get_ticket_status(self, ticket_id):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT status FROM tickets WHERE id = %s"
            cursor.execute(query, (ticket_id,))
            status = cursor.fetchone()
            cursor.close()
        return status[0] if status else None

class TicketMessage:
    def __init__(self, host, database, user, password):
        self.db_params = (host, database, user, password)

    def add_message(self, ticket_id, sender, message):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "INSERT INTO ticket_messages (ticket_id, sender, message) VALUES (%s, %s, %s)"
            cursor.execute(query, (ticket_id, sender, message))
            conn.commit()
            cursor.close()

    def get_messages(self, ticket_id):
        with DatabaseConnection(*self.db_params) as conn:
            cursor = conn.cursor()
            query = "SELECT sender, message, timestamp FROM ticket_messages WHERE ticket_id = %s ORDER BY timestamp"
            cursor.execute(query, (ticket_id,))
            messages = cursor.fetchall()
            cursor.close()
        return messages




#TO ADD THE ADMIN USER WE HAVE TO RUN THE BELOW LINES
#
# host = "localhost"
# database = "travel_planning"
# user = "user"
# password = "5001"
#
# run=Admin(host, database, user, password)
# name="suresh"
# email="vikas@gmail.com"
# password="1234"
# run.add_user(name, email, password)
# print("completed")