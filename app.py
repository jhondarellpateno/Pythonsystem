import sqlite3
import uuid
import datetime
import os
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__)
DATABASE = 'titan_gym.db'

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db():
    """Opens a new database connection if there is none yet for the current application context."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = dict_factory 
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database schema and seeds initial data."""
    if os.path.exists(DATABASE):
        print(f"\n[INFO] Database '{DATABASE}' found. Not re-initializing.")
        print("[INFO] DELETE the database file to apply changes from schema.sql.\n")
    
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


def get_current_bookings_count(class_id):
    """Calculates the number of confirmed bookings for a class."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM bookings WHERE classId = ? AND status = 'confirmed'",
        (class_id,)
    )
    return cursor.fetchone()['COUNT(*)']

def authenticate_user_from_header():
    """Mocks authentication by retrieving user ID and role from headers."""
    user_id = request.headers.get('X-User-Id')
    user_role = request.headers.get('X-User-Role')
    
    if user_id and user_role:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "SELECT id, username, role FROM users WHERE id = ? AND role = ?",
            (user_id, user_role)
        )
        return cursor.fetchone()
    return None


@app.route('/')
def index():
    """Serves the main landing page template."""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """Handles user login and returns user details for client-side state."""
    credentials = request.json
    username = credentials.get('username')
    password = credentials.get('password')

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, username, role FROM users WHERE username = ? AND password = ?",
        (username, password)
    )
    user = cursor.fetchone()

    if user:
        return jsonify({'message': f"Welcome back, {user['username']}!", 'user': user}), 200
    else:
        return jsonify({'message': 'Login failed: Invalid username or password.'}), 401

@app.route('/api/register', methods=['POST'])
def api_register():
    """Registers a new user."""
    details = request.json
    username = details.get('username')
    password = details.get('password')

    if not username or not password or len(password) < 6:
        return jsonify({'message': 'Registration failed: Invalid input or password too short.'}), 400

    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return jsonify({'message': 'Registration failed: Username already exists.'}), 409

    new_id = str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO users (id, username, password, role) VALUES (?, ?, ?, 'user')",
            (new_id, username, password)
        )
        db.commit()
        return jsonify({'message': 'Registration successful! You can now log in.'}), 201
    except sqlite3.Error:
        return jsonify({'message': 'Registration failed due to database error.'}), 500


@app.route('/api/data', methods=['GET'])
def get_all_data():
    """Retrieves classes and the current user's bookings."""
    user = authenticate_user_from_header()
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM classes")
    classes = cursor.fetchall()

    classes_with_counts = []
    for cls in classes:
        count = get_current_bookings_count(cls['id'])
        classes_with_counts.append({
            **cls,
            'currentBookings': count
        })
    
    all_bookings = []
    users_list = []

    if user:
        if user['role'] == 'admin':
            cursor.execute("SELECT * FROM bookings")
            all_bookings = cursor.fetchall()
            cursor.execute("SELECT id, username FROM users")
            users_list = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM bookings WHERE userId = ?", (user['id'],))
            all_bookings = cursor.fetchall()
            users_list = [{'id': user['id'], 'username': user['username']}]
    

    return jsonify({
        'classes': classes_with_counts,
        'bookings': all_bookings,
        'users': users_list
    }), 200


@app.route('/api/book', methods=['POST'])
def api_book():
    """Creates a PENDING booking."""
    user = authenticate_user_from_header()
    if not user or user['role'] != 'user':
        return jsonify({'message': 'Unauthorized. Must be a user to book.'}), 403

    class_id = request.json.get('classId')
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM classes WHERE id = ?", (class_id,))
    class_to_book = cursor.fetchone()

    if not class_to_book:
        return jsonify({'message': 'Class not found.'}), 404

    cursor.execute(
        "SELECT id FROM bookings WHERE userId = ? AND classId = ? AND status IN ('confirmed', 'pending')",
        (user['id'], class_id)
    )
    if cursor.fetchone():
        return jsonify({'message': 'You already have an active booking for this class.'}), 409

    if get_current_bookings_count(class_id) >= class_to_book['capacity']:
        return jsonify({'message': f"Class is full ({class_to_book['capacity']})."}), 409
    
    new_id = str(uuid.uuid4())
    timestamp = str(datetime.datetime.now())

    try:
        cursor.execute(
            "INSERT INTO bookings (id, userId, classId, timestamp, status) VALUES (?, ?, ?, ?, 'pending')",
            (new_id, user['id'], class_id, timestamp)
        )
        db.commit()
        return jsonify({'message': f"Booking for {class_to_book['name']} is PENDING ADMIN APPROVAL."}), 201
    except sqlite3.Error:
        return jsonify({'message': 'Booking failed due to database error.'}), 500


@app.route('/api/booking/<booking_id>/<action>', methods=['POST'])
def manage_booking(booking_id, action):
    """Admin endpoint to approve or reject a booking."""
    user = authenticate_user_from_header()
    if not user or user['role'] != 'admin':
        return jsonify({'message': 'Admin access required.'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT b.*, c.name FROM bookings b JOIN classes c ON b.classId = c.id WHERE b.id = ? AND b.status = 'pending'", 
        (booking_id,)
    )
    booking = cursor.fetchone()

    if not booking:
        return jsonify({'message': 'Pending booking not found.'}), 404

    class_name = booking['name']

    if action == 'approve':
        cursor.execute("SELECT capacity FROM classes WHERE id = ?", (booking['classId'],))
        class_capacity = cursor.fetchone()['capacity']

        if get_current_bookings_count(booking['classId']) >= class_capacity:
            return jsonify({'message': f"Cannot approve: {class_name} is already full."}), 409
        
        new_status = 'confirmed'
        
    elif action == 'reject':
        new_status = 'rejected'
    
    else:
        return jsonify({'message': 'Invalid action.'}), 400

    try:
        cursor.execute(
            "UPDATE bookings SET status = ? WHERE id = ?",
            (new_status, booking_id)
        )
        db.commit()
        return jsonify({'message': f"Booking for {class_name} {new_status}."}), 200
    except sqlite3.Error:
        return jsonify({'message': 'Database error during update.'}), 500


@app.route('/api/booking/<booking_id>', methods=['DELETE'])
def api_cancel_booking(booking_id):
    """User endpoint to cancel a confirmed or pending booking."""
    user = authenticate_user_from_header()
    if not user or user['role'] != 'user':
        return jsonify({'message': 'Unauthorized to cancel.'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id FROM bookings WHERE id = ? AND userId = ? AND status IN ('confirmed', 'pending')",
        (booking_id, user['id'])
    )
    if not cursor.fetchone():
        return jsonify({'message': 'Active booking not found or unauthorized.'}), 404
        
    try:
        cursor.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
            (booking_id,)
        )
        db.commit()
        return jsonify({'message': 'Booking successfully cancelled.'}), 200
    except sqlite3.Error:
        return jsonify({'message': 'Cancellation failed due to database error.'}), 500



@app.route('/api/class', methods=['POST'])
def api_add_class():
    """Adds a new class."""
    user = authenticate_user_from_header()
    if not user or user['role'] != 'admin':
        return jsonify({'message': 'Admin access required.'}), 403

    details = request.json
    db = get_db()
    cursor = db.cursor()

    try:
        new_class = {
            'id': str(uuid.uuid4()),
            'name': details['name'].strip(),
            'time': details['time'].strip(),
            'capacity': int(details['capacity']),
            'price': float(details['price']),
            'trainer': details['trainer'].strip(),
        }
        
        cursor.execute(
            "INSERT INTO classes (id, name, time, capacity, price, trainer) VALUES (?, ?, ?, ?, ?, ?)",
            (new_class['id'], new_class['name'], new_class['time'], new_class['capacity'], new_class['price'], new_class['trainer'])
        )
        db.commit()
        return jsonify({'message': f"Class '{new_class['name']}' added successfully."}), 201
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'message': f'Invalid class details: {e}'}), 400
    except sqlite3.Error:
        return jsonify({'message': 'Class creation failed due to database error.'}), 500


@app.route('/api/class/<class_id>', methods=['DELETE'])
def api_remove_class(class_id):
    """Removes a class and cancels all associated bookings."""
    user = authenticate_user_from_header()
    if not user or user['role'] != 'admin':
        return jsonify({'message': 'Admin access required.'}), 403

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM classes WHERE id = ?", (class_id,))
    if not cursor.fetchone():
        return jsonify({'message': 'Class not found.'}), 404

    try:
        cursor.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE classId = ?",
            (class_id,)
        )
        
        cursor.execute(
            "DELETE FROM classes WHERE id = ?",
            (class_id,)
        )
        db.commit()
        return jsonify({'message': 'Class and associated bookings removed successfully.'}), 200
    except sqlite3.Error:
        return jsonify({'message': 'Removal failed due to database error.'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
