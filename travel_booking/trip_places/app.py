from flask import Flask, render_template, request, redirect, url_for, session, flash,jsonify
import sys
import os
from functools import wraps
import logging
import time
import re
from twilio.rest import Client
from send_email import send_email
from datetime import datetime
import stripe
from flask_socketio import SocketIO, emit, join_room


# Add the db_module folder to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../db')))
# Ensure the logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

from db import Places, User, Admin,Cart,Bookings, Hotels, Ticket, TicketMessage

# Configure logging

# Ensure the logs directory exists
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

# Configure logging with absolute file path
log_file = os.path.join(log_dir, 'admin_signin.log')

app = Flask(__name__, static_url_path='/static')

# Set the secret key
app.secret_key = 'Suresh@1234'
socketio = SocketIO(app, cors_allowed_origins="*")

# Rate limiting variables
MAX_ATTEMPTS = 3
ATTEMPT_WINDOW = 300  # 5 minutes
attempts = {}

# Database connection parameters
db_host = "localhost"
db_database = "travel_planning"
db_user = "user"
db_password = "5001"


stripe.api_key = 'sk_test_51Q61oeP39GVLqL7wjik324YjojpallFBTGRedJMbrLO5NEo46eJ662dfN7IUZtjETb67EDiJF0FQ8s0lMJWtdmcZ005cuJycsX'

#hotel page

@app.route('/hotel_search', methods=['GET', 'POST'])
def hotel_search():
    hotel_instance = Hotels(db_host, db_database, db_user, db_password)
    hotels = hotel_instance.fetch_hotels()

    if request.method == 'POST':
        search_term = request.form.get('search')
        return redirect(url_for('hotel_results', search_term=search_term))
    return render_template('hotels/hotels.html', hotels=hotels)

@app.route('/hotel_results', methods=['GET'])
def hotel_results():
    search_term = request.args.get('search_term', '')
    check_in_str = request.args.get('check_in')
    check_out_str = request.args.get('check_out')

    # Convert string dates to datetime objects
    check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date() if check_in_str else None
    check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date() if check_out_str else None

    hotel_instance = Hotels(db_host, db_database, db_user, db_password)
    booking_instance = Bookings(db_host, db_database, db_user, db_password)

    all_hotels = hotel_instance.fetch_hotels(search_term)
    available_hotels = []

    # Check availability for each hotel
    for hotel in all_hotels:
        if check_in and check_out:
            is_available = booking_instance.check_availability(hotel.id, check_in, check_out)
        else:
            is_available = True  # No date filtering if dates are not provided

        if is_available:
            available_hotels.append(hotel)

    # Convert available hotels to JSON and return
    hotels_json = [
        {
            'id': h.id,
            'name': h.name,
            'location': h.location,
            'place': h.place,
            'price_per_night': h.price_per_night
        }
        for h in available_hotels
    ]

    return jsonify({'hotels': hotels_json})



@app.route('/hotels_display')
def hotels():
    if 'user' in session:
        user_email = session['user']
        hotel_instance = Hotels(db_host, db_database, db_user, db_password)
        hotels = hotel_instance.fetch_hotels()
        return render_template('hotels/hotels_display.html', hotels=hotels, user_email=user_email)
    return redirect(url_for('signin'))


#ADD OR REMOVE hotels

@app.route('/hotels/add', methods=['GET', 'POST'])
def add_hotel():
    if 'user' in session and session['role'] == 'admin':
        if request.method == 'POST':
            name = request.form['name']
            location = request.form['location']
            place = request.form['place']
            price_per_night = request.form['price_per_night']
            hotel_instance = Hotels(db_host, db_database, db_user, db_password)
            try:
                hotel_instance.add_hotel(name,location,place,price_per_night)
                flash('Hotel added successfully')
                return redirect(url_for('hotels'))
            except Exception as e:
                flash('Failed to add place: ' + str(e))
        return render_template('hotels/update_hotels.html')
    flash('Unauthorized access')
    return redirect(url_for('signin'))

@app.route('/hotels/remove/<int:hotel_id>', methods=['POST'])
def remove_hotel(hotel_id):
    if 'user' in session and session['role'] == 'admin':
        hotel_instance = Hotels(db_host, db_database, db_user, db_password)
        try:
            hotel_instance.remove_hotel(hotel_id)
            flash('Hotel removed successfully')
        except Exception as e:
            flash('Failed to remove hotel: ' + str(e))
    else:
        flash('Unauthorized access')
    return redirect(url_for('hotels'))



# @app.route('/destinations/<int:place_id>', methods=['GET', 'POST'])
# def place_details(place_id):
#     if 'user' in session:
#     if 'user' in session:
#         place_instance = Places
#         (db_host, db_database, db_user, db_password)
#         place = place_instance.get_place_by_id(place_id)
#
#         return render_template('place_details.html', place=place)
#     return redirect(url_for('signin'))


# hotel page ends

@app.route('/', methods=['GET', 'POST'])
def search():
    place_instance = Places(db_host, db_database, db_user, db_password)
    places = place_instance.fetch_places()

    if request.method == 'POST':
        search_term = request.form.get('search')
        return redirect(url_for('results', search_term=search_term))
    return render_template('index.html', places=places)


@app.route('/results', methods=['GET'])
def results():
    search_term = request.args.get('search_term')
    place_instance = Places(db_host, db_database, db_user, db_password)
    places = place_instance.fetch_places(search_term)
    return render_template('search_results.html', places=places, search_term=search_term)


#using decorators
def verify_credentials(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            if email and password:  # Ensure email and password are provided
                if not valid_email(email):
                    flash('Invalid email format')
                    return redirect(url_for('admin_signin'))

                if rate_limited(email):
                    flash('Too many login attempts. Please try again later.')
                    return redirect(url_for('admin_signin'))
                user_instance = User(db_host, db_database, db_user, db_password)
                if user_instance.verify_user(email, password):
                    session['user'] = email
                    session['role'] = 'user'
                    return redirect(url_for('home'))
                else:
                    flash('Invalid email, password, or role')
                    return redirect(url_for('signin'))
            else:
                flash('Email and password are required')
                return redirect(url_for('signin'))
        return f(*args, **kwargs)  # Call the original function for GET requests
    return decorated_function

@app.route('/signin', methods=['GET', 'POST'])
@verify_credentials
def signin():
    return render_template('signin.html')


# @app.route('/signin', methods=['GET', 'POST'])
# def signin():
#     if request.method == 'POST':
#         email = request.form['email']
#         password = request.form['password']
#         user_instance = User(db_host, db_database, db_user, db_password)
#         if user_instance.verify_user(email, password):
#             session['user'] = email
#             session['role'] = 'user'
#             return redirect(url_for('home'))
#
#         flash('Invalid email, password, or role')
#         return redirect(url_for('signin'))
#     return render_template('signin.html')



def rate_limited(email):
    now = time.time()
    if email not in attempts:
        attempts[email] = []
    attempts[email] = [timestamp for timestamp in attempts[email] if now - timestamp < ATTEMPT_WINDOW]
    return len(attempts[email]) >= MAX_ATTEMPTS


def valid_email(email):
    regex = '^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w+$'
    if re.search(regex, email):
        return True
    else:
        return False

@app.route('/admin_signin', methods=['GET', 'POST'])
def admin_signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if not valid_email(email):
            flash('Invalid email format')
            return redirect(url_for('admin_signin'))

        if rate_limited(email):
            flash('Too many login attempts. Please try again later.')
            return redirect(url_for('admin_signin'))

        admin_instance = Admin(db_host, db_database, db_user, db_password)  # Replace with your Admin class initialization
        if admin_instance.verify_user(email, password):
            session['user'] = email
            session['role'] = 'admin'
            logging.info(f"Successful login for {email} at {time.ctime()}")
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password')
            logging.warning(f"Failed login attempt for {email} at {time.ctime()}")
            return redirect(url_for('admin_signin'))
    return render_template('admin_signin.html')



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        user_instance = User(db_host, db_database, db_user, db_password)
        try:
            print("Adding user: ", name, email)
            user_instance.add_user(name, email, password)
            flash('User registered successfully')
            print("User registered successfully")
            return redirect(url_for('signin'))
        except Exception as e:
            print("Error: ", str(e))
            flash('User registration failed: ' + str(e))
            return redirect(url_for('signup'))
    return render_template('signup.html')




@app.route('/home')
def home():
    if 'user' in session:
        user_email = session['user']
        role = session['role']
        return render_template('index.html', user_email=user_email, role=role)
    return redirect(url_for('signin'))


@app.route('/destinations')
def place():
    if 'user' in session:
        user_email = session['user']
        place_instance = Places(db_host, db_database, db_user, db_password)
        places = place_instance.fetch_places()
        return render_template('destinations.html', places=places, user_email=user_email)
    return redirect(url_for('signin'))


@app.route('/result', methods=['GET'])
def result():
    if 'user' in session:
        user_email = session['user']
        search_term = request.args.get('search_term')
        place_instance = Places(db_host, db_database, db_user, db_password)
        places = place_instance.fetch_places(search_term)
        return render_template('search_result.html', courses=places, search_term=search_term, user_email=user_email)
    return redirect(url_for('signin'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect(url_for('signin'))
    user_email = session['user']

    user_instance = User(db_host, db_database, db_user, db_password)

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        bio = request.form['bio']
        try:
            user_instance.update_user(session['user'], name, email, password, bio)
            flash('Profile updated successfully')
        except Exception as e:
            flash('Profile update failed: ' + str(e))

    user_data = user_instance.get_user(session['user'])
    booking_instance = Bookings(db_host, db_database, db_user, db_password)
    bookings = booking_instance.get_bookings(user_email)
    # places_bookings = booking_instance.get_bookings_by_type(user_email, 'place')
    # hotels_bookings = booking_instance.get_bookings_by_type(user_email, 'hotel')
    return render_template('profile.html', user=user_data, hotels_bookings=bookings)
    # return render_template('profile.html', user=user_data,places_bookings=places_bookings,
    #                            hotels_bookings=hotels_bookings)




@app.route('/signout')
def signout():
    session.pop('user', None)
    session.pop('role', None)
    return redirect(url_for('signin'))



#ADD OR REMOVE PLACES

@app.route('/destinations/add', methods=['GET', 'POST'])
def add_place():
    if 'user' in session and session['role'] == 'admin':
        if request.method == 'POST':
            name = request.form['name']
            location = request.form['location']
            description = request.form['description']
            # cost = request.form['cost']

            place_instance = Places(db_host, db_database, db_user, db_password)
            try:
                place_instance.add_place(name, location, description)
                flash('Place added successfully')
                return redirect(url_for('place'))
            except Exception as e:
                flash('Failed to add place: ' + str(e))
        return render_template('add_places.html')
    flash('Unauthorized access')
    return redirect(url_for('signin'))

@app.route('/destinations/remove/<int:place_id>', methods=['POST'])
def remove_place(place_id):
    if 'user' in session and session['role'] == 'admin':
        place_instance = Places(db_host, db_database, db_user, db_password)
        try:
            place_instance.remove_place(place_id)
            flash('Place removed successfully')
        except Exception as e:
            flash('Failed to remove place: ' + str(e))
    else:
        flash('Unauthorized access')
    return redirect(url_for('place'))



@app.route('/destinations/<int:place_id>', methods=['GET', 'POST'])
def place_details(place_id):
    if 'user' in session:
        place_instance = Places(db_host, db_database, db_user, db_password)
        place = place_instance.get_place_by_id(place_id)

        return render_template('place_details.html', place=place)
    return redirect(url_for('signin'))




#Cart
@app.route('/cart')
def cart():
    if 'user' in session:
        user_email = session['user']
        cart_instance = Cart(db_host, db_database, db_user, db_password)
        user_instance = User(db_host, db_database, db_user, db_password)

        cart_items = cart_instance.get_cart_items(user_email)
        user_data = user_instance.get_user(user_email)
        first_time_discount = not user_data["first_time_discount_used"]  # Check eligibility

        # Calculate total cost
        total_cost = 0
        for item in cart_items:
            hotel_id = item[1]
            people = item[6]
            days = int(item[9])
            cost_per_person = item[5]
            total_cost += cost_per_person * people * days

        # Convert total_cost to float to avoid Decimal errors
        total_cost = float(total_cost)

        # Apply 10% discount for first-time users
        discount = 0
        final_price = total_cost
        if first_time_discount:
            discount = total_cost * 0.10
            final_price = total_cost - discount

        return render_template('cart.html', cart_items=cart_items, total_cost=total_cost, discount=discount, final_price=final_price)

    else:
        return redirect(url_for('signin'))


@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    if 'user' in session:
        user_email = session['user']
        hotel_id = request.form.get('hotel_id')
        cart_instance = Cart(db_host, db_database, db_user, db_password)
        cart_instance.add_to_cart(user_email, hotel_id, 0, 0)  # Initial values for people and days
        return redirect(url_for('cart'))
    else:
        return redirect(url_for('signin'))

@app.route('/cart/update', methods=['POST'])
def update_cart():
    if 'user' in session:
        user_email = session['user']
        cart_instance = Cart(db_host, db_database, db_user, db_password)
        cart_items = cart_instance.get_cart_items(user_email)

        for item in cart_items:
            # Get form inputs
            people = int(request.form.get(f'people_{item[0]}', 1))
            days = int(request.form.get(f'days_{item[0]}', 1))

            # Retrieve and validate check-in and check-out dates
            check_in_str = request.form.get(f'check_in_{item[0]}')
            check_out_str = request.form.get(f'check_out_{item[0]}')

            print(f"Check-in: {check_in_str}, Check-out: {check_out_str}")  # Debugging

            if check_in_str and check_out_str:
                try:
                    check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                    check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                except ValueError as e:
                    flash(f"Invalid date format: {e}")
                    return redirect(url_for('cart'))
            else:
                flash("Check-in and Check-out dates are required.")
                return redirect(url_for('cart'))

            # Update the cart item in the database
            cart_instance.update_cart_item(item[0], people, days, check_in, check_out)

        flash("Cart updated successfully!")
        return redirect(url_for('cart'))
    else:
        flash("Please sign in to update your cart.")
        return redirect(url_for('signin'))


@app.route('/cart/checkout', methods=['POST'])
def checkout():
    if 'user' in session:
        user_email = session['user']
        cart_instance = Cart(db_host, db_database, db_user, db_password)
        user_instance = User(db_host, db_database, db_user, db_password)
        cart_items = cart_instance.get_cart_items(user_email)

        user_data = user_instance.get_user(user_email)
        first_time_discount = not user_data["first_time_discount_used"]  # Check eligibility

        total_cost = 0
        for item in cart_items:
            hotel_id = item[1]
            people = item[6]
            days = int(item[9])
            cost_per_person = item[5]
            total_cost += cost_per_person * people * days

        # Apply 10% discount if first-time
        discount = 0
        final_price = total_cost
        if first_time_discount:
            discount = float(total_cost) * 0.10
            final_price = float(total_cost) - discount

        # Create a Stripe Checkout Session
        try:
            stripe_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {'name': 'Total Booking Cost'},
                        'unit_amount': int(final_price * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=url_for('payment_success', _external=True) + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=url_for('payment_cancel', _external=True),
            )

            # Mark discount as used
            if first_time_discount:
                user_instance.set_first_time_discount_used(user_email)

            return redirect(stripe_session.url)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    else:
        return redirect(url_for('signin'))




@app.route('/payment_success')
def payment_success():
    if 'user' in session:
        user_email = session['user']
        cart_instance = Cart(db_host, db_database, db_user, db_password)
        cart_items = cart_instance.get_cart_items(user_email)
        booking_instance = Bookings(db_host, db_database, db_user, db_password)

        # Add each item in the cart to the bookings database
        for item in cart_items:
            hotel_id = item[1]
            people = item[6]
            check_in = item[7]
            check_out = item[8]
            days = int(item[9])
            cost_per_person = item[5]
            total_cost = cost_per_person * people * days

            # Add booking to the database
            booking_instance.add_booking(
                user_email, hotel_id, people, check_in, check_out, days, total_cost
            )

            # Send confirmation notifications
            bookings = booking_instance.get_bookings(user_email)
            recent_booking = bookings[-1]
            message_matter = "Your booking at " + recent_booking[1] + ", " + recent_booking[
                2] + ", is confirmed!\nTotal amount: RS." + str(total_cost) + "."
            send_message(message_matter)
            make_call(message_matter)
            subject = 'Booking Details'
            send_email('sureshkrishnanv24@gmail.com', user_email, 'mkzrwfycjugbxmcd', subject, message_matter)

        # Clear the cart after successful checkout
        cart_instance.clear_cart(user_email)

        # Redirect to the profile page after successful booking
        return redirect(url_for('profile'))
    else:
        return redirect(url_for('signin'))


@app.route('/payment_cancel')
def payment_cancel():
    # Handle payment cancellation and redirect to the cart or an error page
    return redirect(url_for('cart'))


@app.route('/cart/remove/<int:cart_id>', methods=['POST'])
def remove_from_cart(cart_id):
    if 'user' in session:
        cart_instance = Cart(db_host, db_database, db_user, db_password)
        cart_instance.remove_from_cart(cart_id)
        return redirect(url_for('cart'))
    else:
        return redirect(url_for('signin'))

def send_message(text):
    account_sid = "ACc1955ac5e81b895e0ab6b898e64a7cf4"

    auth_token = "8799110a7b8c154183b7288b10371594"
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        body=text,
        from_="+19564771367",

        to="+918639462167",
    )

    return (message.body)

def make_call(text):
    account_sid = "ACc1955ac5e81b895e0ab6b898e64a7cf4"

    auth_token = "8799110a7b8c154183b7288b10371594"

    client = Client(account_sid, auth_token)
    call = client.calls.create(
        twiml=f'<Response><Say voice="Polly.Joanna-Neural">This call is to give information regarding to {text}</Say></Response>',
        from_="+19564771367",

        to="+918639462167",
    )
    return call.sid

#tickets
@app.route('/ticket', methods=['GET', 'POST'])
def ticket():
    # Ensure user is logged in before allowing ticket submission
    # if 'user_email' not in session or 'user' not in session:
    #     return redirect(url_for('signin'))  # Redirect to login page if user details are missing

    user_email = session.get('user', '')
    user_name = session.get('user', '')
    print(user_email)

    ticket_instance = Ticket(db_host, db_database, db_user, db_password)

    if request.method == 'POST':
        complaint = request.form['complaint']

        # Create a new ticket
        ticket_id = ticket_instance.create_ticket(user_name, user_email, complaint)

        # Store user details in session
        session['user_name'] = user_name
        session['user_email'] = user_email
        session['role'] = 'user'

        # Add the first message to the database
        message_instance = TicketMessage(db_host, db_database, db_user, db_password)
        message_instance.add_message(ticket_id, user_name, complaint)

        return redirect(url_for('chat', ticket_id=ticket_id))

    # Fetch existing tickets from the database
    tickets = ticket_instance.get_user_tickets(user_email) if user_email else []

    return render_template('ticket.html', tickets=tickets)



@app.route('/admin/tickets')
def admin_tickets():
    if 'user' not in session or session['role'] != 'admin':
        return redirect(url_for('signin'))

    ticket_instance = Ticket(db_host, db_database, db_user, db_password)
    tickets = ticket_instance.get_tickets()

    return render_template('admin_tickets.html', tickets=tickets)


@socketio.on('join_room')
def handle_join_room(data):
    ticket_id = data['ticket_id']
    role = session.get('role', 'User')  # Identify if it's a User or Admin
    room = f"ticket_{ticket_id}"

    join_room(room)

    # Customize messages based on role
    if role == 'admin':
        message = "Customer support executive joined."
    else:
        message = "We have received your request. Our customer support executive will get in touch with you within 24 hours."

    emit('message', {'sender': 'System', 'message': message}, room=room)


@socketio.on('send_message')
def handle_send_message(data):
    ticket_id = data['ticket_id']
    sender = session.get('user_name', 'User')
    message = data['message']

    # Check if the ticket is closed before allowing messages
    ticket_instance = Ticket(db_host, db_database, db_user, db_password)
    ticket_status = ticket_instance.get_ticket_status(ticket_id)

    if ticket_status == 'closed':
        emit('message', {'sender': 'System', 'message': 'This chat is closed. You can no longer send messages.'}, room=f"ticket_{ticket_id}")
        return

    # Store message in DB
    message_instance = TicketMessage(db_host, db_database, db_user, db_password)
    message_instance.add_message(ticket_id, sender, message)

    room = f"ticket_{ticket_id}"
    emit('message', {'sender': sender, 'message': message}, room=room, broadcast=True)


@app.route('/chat/<int:ticket_id>')
def chat(ticket_id):
    ticket_instance = Ticket(db_host, db_database, db_user, db_password)
    message_instance = TicketMessage(db_host, db_database, db_user, db_password)

    # Fetch ticket details
    ticket = ticket_instance.get_tickets()
    messages = message_instance.get_messages(ticket_id)  # Fetch messages from DB

    if not ticket:
        return "Ticket not found", 404

    return render_template('chat.html', ticket_id=ticket_id, messages=messages)

@app.route('/update_ticket_status/<int:ticket_id>', methods=['POST'])
def update_ticket_status(ticket_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_tickets'))

    new_status = request.form['status']
    ticket_instance = Ticket(db_host, db_database, db_user, db_password)
    ticket_instance.update_ticket_status(ticket_id, new_status)

    return redirect(url_for('admin_tickets'))


if __name__ == '__main__':
    #app.run(debug=True, port=8080)
    socketio.run(app,allow_unsafe_werkzeug=True, debug=True, port=8080)