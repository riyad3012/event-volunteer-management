
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from flask import send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.colors import HexColor
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__),".env"))
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is missing from .env")

CORS(
    app,
    supports_credentials=True,
    origins=["http://127.0.0.1:5500"]
)


# DATABASE CONNECTION
def get_db_connection():
        db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
        )
        return db


# HOME
@app.route("/")
def home():
    return "Event Volunteer Management Backend Running!"


# USER REGISTRATION
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    phone = data.get("phone")

    roles = data.get("roles") or [data.get("role", "volunteer")]

    if not all([name, email, password, phone]):
        return jsonify({"message": "All fields are required"}), 400

    if isinstance(roles, str):
        roles = [roles]

    if not isinstance(roles, list) or not roles:
        return jsonify({"message": "Select at least one role"}), 400

    roles = list(set(roles))

    if any(role not in ["volunteer", "organizer"] for role in roles):
        return jsonify({"message": "Invalid role selection"}), 400

    organization_name = (data.get("organization_name") or "").strip()

    if "organizer" in roles and not organization_name:
        return jsonify({"message": "Organization name is required"}), 400

    hashed_password = generate_password_hash(password)

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO users
            (name, email, password_hash, phone, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, hashed_password, phone, roles[0]))

        user_id = cursor.lastrowid

        for role in roles:
            cursor.execute("""
                INSERT INTO user_roles (user_id, role)
                VALUES (%s, %s)
            """, (user_id, role))

        if "organizer" in roles:
            cursor.execute("""
                INSERT INTO organizations
                (organization_name, description, contact_email, admin_id)
                VALUES (%s, %s, %s, %s)
            """, (
                organization_name,
                "Organization registered on VolunteerHub",
                email,
                user_id
            ))

        db.commit()

        return jsonify({
            "message": "Registration successful!",
            "roles": roles
        }), 201

    except mysql.connector.IntegrityError:
        db.rollback()
        return jsonify({"message": "Email already registered"}), 409

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# TEMPORARY ADMIN CREATION ROUTE
@app.route("/create-admin", methods=["GET"])
def create_admin():
    db = get_db_connection()
    cursor = db.cursor()

    name = "Admin"
    email = "admin@volunteerhub.com"
    password = "Admin@123"
    phone = "9999999999"
    role = "admin"

    hashed_password = generate_password_hash(password)

    try:
        cursor.execute("""
            INSERT INTO users
            (name, email, password_hash, phone, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, hashed_password, phone, role))

        user_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO user_roles (user_id, role)
            VALUES (%s, 'admin')
        """, (user_id,))

        db.commit()
        return "Admin created successfully!"

    except Exception as e:
        db.rollback()
        return str(e)

    finally:
        cursor.close()
        db.close()


# USER LOGIN
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT user_id, name, email, password_hash
            FROM users
            WHERE email = %s
        """, (email,))

        user = cursor.fetchone()

        if not user or not check_password_hash(
            user["password_hash"], password
        ):
            return jsonify({"message": "Invalid email or password"}), 401

        cursor.execute("""
            SELECT role FROM user_roles
            WHERE user_id = %s
        """, (user["user_id"],))

        roles = [row["role"] for row in cursor.fetchall()]

        # Migrate existing users who do not yet have user_roles entries
        if not roles:
            cursor.execute("""
                INSERT IGNORE INTO user_roles (user_id, role)
                SELECT user_id, role
                FROM users
                WHERE user_id = %s
            """, (user["user_id"],))

            db.commit()

            cursor.execute("""
                SELECT role FROM user_roles
                WHERE user_id = %s
            """, (user["user_id"],))

            roles = [row["role"] for row in cursor.fetchall()]

        session["user_id"] = user["user_id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["user_roles"] = roles
        session["user_role"] = roles[0]

        return jsonify({
            "message": "Login successful",
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "roles": roles,
            "role": roles[0]
        }), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# SWITCH BETWEEN VOLUNTEER AND ORGANIZER
@app.route("/api/select-role", methods=["POST"])
def select_role():
    if "user_id" not in session:
        return jsonify({"error": "Please login first"}), 401

    data = request.get_json() or {}
    selected_role = data.get("role")
    available_roles = session.get("user_roles", [])

    if selected_role not in available_roles:
        return jsonify({"error": "You do not have this role"}), 403

    session["user_role"] = selected_role

    return jsonify({
        "message": "Role changed successfully",
        "role": selected_role
    }), 200


# VOLUNTEER REGISTERS FOR AN EVENT
@app.route("/api/register-event", methods=["POST"])
def register_event():
    if "user_id" not in session:
        return jsonify({"message": "Please login first"}), 401

    if session.get("user_role") != "volunteer":
        return jsonify({"message": "Volunteer access required"}), 403

    data = request.get_json() or {}
    event_id = data.get("event_id")
    user_id = session["user_id"]

    if not event_id:
        return jsonify({"message": "Event ID is required"}), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "SELECT event_id FROM events WHERE event_id = %s",
            (event_id,)
        )

        if not cursor.fetchone():
            return jsonify({"message": "Event not found"}), 404

        cursor.execute("""
            SELECT registration_id
            FROM registrations
            WHERE user_id = %s AND event_id = %s
        """, (user_id, event_id))

        if cursor.fetchone():
            return jsonify({"message": "Already registered"}), 409

        cursor.execute("""
            INSERT INTO registrations
            (user_id, event_id, application_status)
            VALUES (%s, %s, 'pending')
        """, (user_id, event_id))

        db.commit()

        return jsonify({"message": "Registration successful!"}), 201

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# ==========================================
# ADMIN DASHBOARD API ROUTES
# ==========================================

def is_admin():
    return (
        session.get("user_id") is not None
        and session.get("user_role") == "admin"
    )


# ADMIN DASHBOARD STATISTICS
@app.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                (SELECT COUNT(*) FROM users) AS total_users,
                (SELECT COUNT(*) FROM users
                 WHERE role = 'volunteer') AS total_volunteers,
                (SELECT COUNT(*) FROM users
                 WHERE role = 'organizer') AS total_organizers,
                (SELECT COUNT(*) FROM events) AS total_events,
                (SELECT COUNT(*) FROM registrations) AS total_registrations
        """)

        return jsonify(cursor.fetchone()), 200

    finally:
        cursor.close()
        db.close()


# VIEW ALL USERS
@app.route("/api/admin/users", methods=["GET"])
def admin_users():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT user_id, name, email, phone, role
            FROM users
            ORDER BY user_id DESC
        """)

        return jsonify({"users": cursor.fetchall()}), 200

    finally:
        cursor.close()
        db.close()


# VIEW ALL EVENTS
@app.route("/api/admin/events", methods=["GET"])
def admin_events():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                event_id,
                event_name AS title,
                description,
                event_date,
                location,
                volunteer_limit,
                registration_deadline,
                status,
                category_id,
                organization_id
            FROM events
            ORDER BY event_date DESC
        """)

        return jsonify({"events": cursor.fetchall()}), 200

    finally:
        cursor.close()
        db.close()


# VIEW ALL EVENT REGISTRATIONS
@app.route("/api/admin/registrations", methods=["GET"])
def admin_registrations():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                r.registration_id,
                u.name AS user_name,
                e.event_name,
                r.registration_date,
                r.application_status
            FROM registrations r
            JOIN users u ON r.user_id = u.user_id
            JOIN events e ON r.event_id = e.event_id
            ORDER BY r.registration_date DESC
        """)

        return jsonify({"registrations": cursor.fetchall()}), 200

    finally:
        cursor.close()
        db.close()


# CANCEL AN EVENT (DO NOT DELETE ITS RECORDS)
@app.route("/api/admin/events/<int:event_id>", methods=["DELETE"])
def admin_delete_event(event_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "SELECT event_id FROM events WHERE event_id = %s",
            (event_id,)
        )

        if not cursor.fetchone():
            return jsonify({"message": "Event not found"}), 404

        cursor.execute("""
            UPDATE events
            SET status = 'canceled'
            WHERE event_id = %s
        """, (event_id,))

        db.commit()

        return jsonify({"message": "Event canceled successfully"}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# LOGOUT
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


# GET EVENT CATEGORIES AND ORGANIZATIONS
@app.route("/api/admin/event-options", methods=["GET"])
def admin_event_options():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT category_id, category_name
            FROM event_categories
            ORDER BY category_name
        """)
        categories = cursor.fetchall()

        cursor.execute("""
            SELECT organization_id, organization_name
            FROM organizations
            ORDER BY organization_name
        """)
        organizations = cursor.fetchall()

        return jsonify({
            "categories": categories,
            "organizations": organizations
        }), 200

    finally:
        cursor.close()
        db.close()


# CREATE EVENT (ADMIN)
@app.route("/api/admin/events", methods=["POST"])
def admin_create_event():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data = request.get_json() or {}

    required = [
        "event_name", "description", "event_date",
        "location", "volunteer_limit", "registration_deadline",
        "category_id", "organization_id"
    ]

    if not all(data.get(field) for field in required):
        return jsonify({"message": "Please fill in all event fields"}), 400

    try:
        volunteer_limit = int(data["volunteer_limit"])
        category_id = int(data["category_id"])
        organization_id = int(data["organization_id"])

        if volunteer_limit <= 0:
            return jsonify({
                "message": "Volunteer limit must be greater than zero"
            }), 400

    except (ValueError, TypeError):
        return jsonify({"message": "Please enter valid numbers"}), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO events (
                organization_id, category_id, event_name,
                description, event_date, location,
                volunteer_limit, registration_deadline, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'upcoming')
        """, (
            organization_id,
            category_id,
            data["event_name"].strip(),
            data["description"].strip(),
            data["event_date"],
            data["location"].strip(),
            volunteer_limit,
            data["registration_deadline"]
        ))

        db.commit()
        return jsonify({"message": "Event created successfully!"}), 201

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# EDIT EVENT (ADMIN)
@app.route("/api/admin/events/<int:event_id>", methods=["PUT"])
def admin_update_event(event_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data = request.get_json() or {}

    required = [
        "event_name", "description", "event_date",
        "location", "volunteer_limit", "registration_deadline",
        "category_id", "organization_id"
    ]

    if not all(data.get(field) for field in required):
        return jsonify({"message": "Please fill in all event fields"}), 400

    try:
        volunteer_limit = int(data["volunteer_limit"])
        category_id = int(data["category_id"])
        organization_id = int(data["organization_id"])

        if volunteer_limit <= 0:
            return jsonify({
                "message": "Volunteer limit must be greater than zero"
            }), 400

    except (ValueError, TypeError):
        return jsonify({"message": "Please enter valid numbers"}), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "SELECT event_id FROM events WHERE event_id = %s",
            (event_id,)
        )

        if not cursor.fetchone():
            return jsonify({"message": "Event not found"}), 404

        cursor.execute("""
            UPDATE events
            SET organization_id = %s,
                category_id = %s,
                event_name = %s,
                description = %s,
                event_date = %s,
                location = %s,
                volunteer_limit = %s,
                registration_deadline = %s
            WHERE event_id = %s
        """, (
            organization_id,
            category_id,
            data["event_name"].strip(),
            data["description"].strip(),
            data["event_date"],
            data["location"].strip(),
            volunteer_limit,
            data["registration_deadline"],
            event_id
        ))

        db.commit()
        return jsonify({"message": "Event updated successfully!"}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# APPROVE OR REJECT REGISTRATION (ADMIN)
@app.route("/api/admin/registrations/<int:registration_id>/status", methods=["PUT"])
def admin_update_registration(registration_id):
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    data = request.get_json() or {}
    status = data.get("status")

    if status not in ["approved", "rejected"]:
        return jsonify({"message": "Invalid registration status"}), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT registration_id
            FROM registrations
            WHERE registration_id = %s
        """, (registration_id,))

        if not cursor.fetchone():
            return jsonify({"message": "Registration not found"}), 404

        cursor.execute("""
            UPDATE registrations
            SET application_status = %s
            WHERE registration_id = %s
        """, (status, registration_id))

        db.commit()

        return jsonify({
            "message": f"Registration {status} successfully!"
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# ADMIN ANALYTICS
@app.route("/api/admin/analytics", methods=["GET"])
def admin_analytics():
    if not is_admin():
        return jsonify({"message": "Admin access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                application_status AS status,
                COUNT(*) AS total
            FROM registrations
            GROUP BY application_status
        """)
        registration_data = cursor.fetchall()

        cursor.execute("""
            SELECT
                e.event_name,
                COUNT(r.registration_id) AS total
            FROM events e
            LEFT JOIN registrations r ON e.event_id = r.event_id
            GROUP BY e.event_id, e.event_name
            ORDER BY total DESC
        """)
        event_data = cursor.fetchall()

        return jsonify({
            "registrations": registration_data,
            "events": event_data
        }), 200

    finally:
        cursor.close()
        db.close()

# ==========================================
# ORGANIZER DASHBOARD API ROUTES
# ==========================================

def get_organizer_organization(cursor):
    if (
        session.get("user_id") is None
        or session.get("user_role") != "organizer"
    ):
        return None

    cursor.execute("""
        SELECT organization_id
        FROM organizations
        WHERE admin_id = %s
    """, (session["user_id"],))

    result = cursor.fetchone()

    if not result:
        return None

    return result["organization_id"]


# ORGANIZER DASHBOARD STATISTICS
@app.route("/api/organizer/stats", methods=["GET"])
def organizer_stats():
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        organization_id = get_organizer_organization(cursor)

        if organization_id is None:
            return jsonify({
                "message": "No organization linked to this account"
            }), 404

        cursor.execute("""
            SELECT
                COUNT(DISTINCT e.event_id) AS total_events,
                COUNT(r.registration_id) AS total_registrations,
                COALESCE(SUM(
                    CASE WHEN r.application_status = 'pending'
                    THEN 1 ELSE 0 END
                ), 0) AS pending_registrations,
                COALESCE(SUM(
                    CASE WHEN r.application_status = 'approved'
                    THEN 1 ELSE 0 END
                ), 0) AS approved_registrations
            FROM events e
            LEFT JOIN registrations r
                ON e.event_id = r.event_id
            WHERE e.organization_id = %s
        """, (organization_id,))

        return jsonify(cursor.fetchone()), 200

    finally:
        cursor.close()
        db.close()


# VIEW ORGANIZER'S EVENTS
@app.route("/api/organizer/events", methods=["GET"])
def organizer_events():
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        organization_id = get_organizer_organization(cursor)

        if organization_id is None:
            return jsonify({"message": "No organization linked"}), 404

        cursor.execute("""
            SELECT
                event_id,
                event_name,
                description,
                event_date,
                location,
                volunteer_limit,
                registration_deadline,
                status,
                category_id
            FROM events
            WHERE organization_id = %s
            ORDER BY event_date DESC
        """, (organization_id,))

        return jsonify({"events": cursor.fetchall()}), 200

    finally:
        cursor.close()
        db.close()


# GET EVENT CATEGORIES FOR ORGANIZER
@app.route("/api/organizer/event-options", methods=["GET"])
def organizer_event_options():
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT category_id, category_name
            FROM event_categories
            ORDER BY category_name
        """)

        return jsonify({"categories": cursor.fetchall()}), 200

    finally:
        cursor.close()
        db.close()


# CREATE EVENT (ORGANIZER)
@app.route("/api/organizer/events", methods=["POST"])
def organizer_create_event():
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    data = request.get_json() or {}

    required = [
        "event_name",
        "description",
        "event_date",
        "location",
        "volunteer_limit",
        "registration_deadline",
        "category_id"
    ]

    if not all(data.get(field) for field in required):
        return jsonify({"message": "Please fill in all fields"}), 400

    try:
        volunteer_limit = int(data["volunteer_limit"])
        category_id = int(data["category_id"])

        if volunteer_limit <= 0:
            return jsonify({"message": "Volunteer limit must be positive"}), 400

    except (ValueError, TypeError):
        return jsonify({"message": "Invalid number entered"}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        organization_id = get_organizer_organization(cursor)

        if organization_id is None:
            return jsonify({"message": "No organization linked"}), 404

        cursor.execute("""
            SELECT category_id
            FROM event_categories
            WHERE category_id = %s
        """, (category_id,))

        if not cursor.fetchone():
            return jsonify({"message": "Invalid event category"}), 400

        cursor.execute("""
            INSERT INTO events (
                organization_id,
                category_id,
                event_name,
                description,
                event_date,
                location,
                volunteer_limit,
                registration_deadline,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'upcoming')
        """, (
            organization_id,
            category_id,
            data["event_name"].strip(),
            data["description"].strip(),
            data["event_date"],
            data["location"].strip(),
            volunteer_limit,
            data["registration_deadline"]
        ))

        db.commit()

        return jsonify({
            "message": "Event created successfully!"
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# EDIT ORGANIZER'S EVENT
@app.route("/api/organizer/events/<int:event_id>", methods=["PUT"])
def organizer_update_event(event_id):
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    data = request.get_json() or {}

    required = [
        "event_name",
        "description",
        "event_date",
        "location",
        "volunteer_limit",
        "registration_deadline",
        "category_id"
    ]

    if not all(data.get(field) for field in required):
        return jsonify({"message": "Please fill in all fields"}), 400

    try:
        volunteer_limit = int(data["volunteer_limit"])
        category_id = int(data["category_id"])

        if volunteer_limit <= 0:
            return jsonify({"message": "Volunteer limit must be positive"}), 400

    except (ValueError, TypeError):
        return jsonify({"message": "Invalid number entered"}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        organization_id = get_organizer_organization(cursor)

        if organization_id is None:
            return jsonify({"message": "No organization linked"}), 404

        cursor.execute("""
            SELECT event_id
            FROM events
            WHERE event_id = %s AND organization_id = %s
        """, (event_id, organization_id))

        if not cursor.fetchone():
            return jsonify({"message": "Event not found"}), 404

        cursor.execute("""
            SELECT category_id
            FROM event_categories
            WHERE category_id = %s
        """, (category_id,))

        if not cursor.fetchone():
            return jsonify({"message": "Invalid event category"}), 400

        cursor.execute("""
            UPDATE events
            SET
                category_id = %s,
                event_name = %s,
                description = %s,
                event_date = %s,
                location = %s,
                volunteer_limit = %s,
                registration_deadline = %s
            WHERE event_id = %s
              AND organization_id = %s
        """, (
            category_id,
            data["event_name"].strip(),
            data["description"].strip(),
            data["event_date"],
            data["location"].strip(),
            volunteer_limit,
            data["registration_deadline"],
            event_id,
            organization_id
        ))

        db.commit()

        return jsonify({"message": "Event updated successfully!"}), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# VIEW ORGANIZER'S REGISTRATIONS
@app.route("/api/organizer/registrations", methods=["GET"])
def organizer_registrations():
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        organization_id = get_organizer_organization(cursor)

        if organization_id is None:
            return jsonify({"message": "No organization linked"}), 404

        cursor.execute("""
            SELECT
                r.registration_id,
                u.name AS volunteer_name,
                u.email,
                e.event_name,
                r.registration_date,
                r.application_status
            FROM registrations r
            JOIN users u ON r.user_id = u.user_id
            JOIN events e ON r.event_id = e.event_id
            WHERE e.organization_id = %s
            ORDER BY r.registration_date DESC
        """, (organization_id,))

        return jsonify({"registrations": cursor.fetchall()}), 200

    finally:
        cursor.close()
        db.close()


# APPROVE OR REJECT VOLUNTEER (ORGANIZER)
@app.route(
    "/api/organizer/registrations/<int:registration_id>/status",
    methods=["PUT"]
)
def organizer_update_registration(registration_id):
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    data = request.get_json() or {}
    status = data.get("status")

    if status not in ["approved", "rejected"]:
        return jsonify({"message": "Invalid status"}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        organization_id = get_organizer_organization(cursor)

        if organization_id is None:
            return jsonify({"message": "No organization linked"}), 404

        cursor.execute("""
            SELECT r.registration_id
            FROM registrations r
            JOIN events e ON r.event_id = e.event_id
            WHERE r.registration_id = %s
              AND e.organization_id = %s
        """, (registration_id, organization_id))

        if not cursor.fetchone():
            return jsonify({"message": "Registration not found"}), 404

        cursor.execute("""
            UPDATE registrations
            SET application_status = %s
            WHERE registration_id = %s
        """, (status, registration_id))

        db.commit()

        return jsonify({
            "message": f"Volunteer {status} successfully!"
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        db.close()


# ORGANIZER ANALYTICS
@app.route("/api/organizer/analytics", methods=["GET"])
def organizer_analytics():
    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        organization_id = get_organizer_organization(cursor)

        if organization_id is None:
            return jsonify({"message": "No organization linked"}), 404

        cursor.execute("""
            SELECT
                r.application_status AS status,
                COUNT(*) AS total
            FROM registrations r
            JOIN events e ON r.event_id = e.event_id
            WHERE e.organization_id = %s
            GROUP BY r.application_status
        """, (organization_id,))

        registration_data = cursor.fetchall()

        cursor.execute("""
            SELECT
                e.event_name,
                COUNT(r.registration_id) AS total
            FROM events e
            LEFT JOIN registrations r ON e.event_id = r.event_id
            WHERE e.organization_id = %s
            GROUP BY e.event_id, e.event_name
            ORDER BY total DESC
        """, (organization_id,))

        event_data = cursor.fetchall()

        return jsonify({
            "registrations": registration_data,
            "events": event_data
        }), 200

    finally:
        cursor.close()
        db.close()

# ==========================================
# VOLUNTEER DASHBOARD APIs
# ==========================================

def is_volunteer():
    return (
        "user_id" in session
        and session.get("user_role") == "volunteer"
    )


# GET ALL UPCOMING EVENTS
@app.route("/api/events", methods=["GET"])
def get_events():
    if not is_volunteer():
        return jsonify({"error": "Volunteer login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                e.event_id,
                e.event_name,
                e.description,
                e.event_date,
                e.location,
                e.volunteer_limit,
                e.registration_deadline,
                e.status,
                e.category_id,
                c.category_name,
                CASE
                    WHEN r.registration_id IS NULL THEN FALSE
                    ELSE TRUE
                END AS is_registered
            FROM events e
            LEFT JOIN event_categories c
                ON e.category_id = c.category_id
            LEFT JOIN registrations r
                ON e.event_id = r.event_id
                AND r.user_id = %s
            WHERE e.status = 'upcoming'
            ORDER BY e.event_date ASC
        """, (session["user_id"],))

        events = cursor.fetchall()

        for event in events:
            event["is_registered"] = bool(event["is_registered"])

        return jsonify(events)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# GET EVENT CATEGORIES
@app.route("/api/event-categories", methods=["GET"])
def get_event_categories():
    if not is_volunteer():
        return jsonify({"error": "Volunteer login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT category_id, category_name
            FROM event_categories
            ORDER BY category_name
        """)

        return jsonify({"categories": cursor.fetchall()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# VOLUNTEER DASHBOARD STATISTICS
@app.route("/api/volunteer/stats", methods=["GET"])
def volunteer_stats():
    if not is_volunteer():
        return jsonify({"error": "Volunteer login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        user_id = session["user_id"]

        cursor.execute("""
            SELECT
                COUNT(*) AS total_registrations,
                SUM(application_status = 'pending') AS pending_applications,
                SUM(application_status = 'approved') AS approved_applications
            FROM registrations
            WHERE user_id = %s
        """, (user_id,))

        stats = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS total_certificates
            FROM certificates
            WHERE user_id = %s
        """, (user_id,))

        certificate_stats = cursor.fetchone()

        return jsonify({
            "total_registrations": stats["total_registrations"] or 0,
            "pending_applications": stats["pending_applications"] or 0,
            "approved_applications": stats["approved_applications"] or 0,
            "total_certificates": certificate_stats["total_certificates"] or 0
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# VOLUNTEER REGISTRATIONS
@app.route("/api/volunteer/registrations", methods=["GET"])
def volunteer_registrations():
    if not is_volunteer():
        return jsonify({"error": "Volunteer login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                r.registration_id,
                e.event_name,
                r.registration_date,
                r.application_status
            FROM registrations r
            JOIN events e ON r.event_id = e.event_id
            WHERE r.user_id = %s
            ORDER BY r.registration_date DESC
        """, (session["user_id"],))

        return jsonify(cursor.fetchall())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# VOLUNTEER ATTENDANCE
@app.route("/api/volunteer/attendance", methods=["GET"])
def volunteer_attendance():
    if not is_volunteer():
        return jsonify({"error": "Volunteer login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                a.attendance_id,
                e.event_name,
                DATE(a.check_in_time) AS attendance_date,
                a.attendance_status
            FROM attendance a
            JOIN assignments ass
                ON a.assignment_id = ass.assignment_id
            JOIN registrations r
                ON ass.registration_id = r.registration_id
            JOIN events e
                ON r.event_id = e.event_id
            WHERE r.user_id = %s
            ORDER BY a.check_in_time DESC
        """, (session["user_id"],))

        return jsonify(cursor.fetchall())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# VOLUNTEER CERTIFICATES
@app.route("/api/volunteer/certificates", methods=["GET"])
def volunteer_certificates():
    if not is_volunteer():
        return jsonify({"error": "Volunteer login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                c.certificate_id,
                e.event_name,
                c.certificate_code AS certificate_number,
                c.issue_date
            FROM certificates c
            JOIN events e ON c.event_id = e.event_id
            WHERE c.user_id = %s
            ORDER BY c.issue_date DESC
        """, (session["user_id"],))

        return jsonify(cursor.fetchall())

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# GET INDIVIDUAL CERTIFICATE DETAILS
@app.route(
    "/api/volunteer/certificates/<certificate_number>",
    methods=["GET"]
)
def get_volunteer_certificate(certificate_number):
    if not is_volunteer():
        return jsonify({"error": "Volunteer login required"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                c.certificate_id,
                c.certificate_code AS certificate_number,
                c.issue_date,
                e.event_name,
                u.name AS volunteer_name
            FROM certificates c
            JOIN events e ON c.event_id = e.event_id
            JOIN users u ON c.user_id = u.user_id
            WHERE c.certificate_code = %s
              AND c.user_id = %s
        """, (certificate_number, session["user_id"]))

        certificate = cursor.fetchone()

        if not certificate:
            return jsonify({"error": "Certificate not found"}), 404

        return jsonify(certificate)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


# ==========================================
# ATTENDANCE AND CERTIFICATE MANAGEMENT
# ==========================================

import secrets


# ------------------------------------------
# ORGANIZER AUTHORIZATION HELPER
# ------------------------------------------

def get_organizer_org_for_feature(cursor):

    if (
        "user_id" not in session
        or session.get("user_role") != "organizer"
    ):
        return None

    cursor.execute("""
        SELECT organization_id
        FROM organizations
        WHERE admin_id = %s
    """, (session["user_id"],))

    result = cursor.fetchone()

    return result["organization_id"] if result else None


# ------------------------------------------
# GET APPROVED VOLUNTEERS FOR ATTENDANCE
# ------------------------------------------

@app.route("/api/organizer/attendance", methods=["GET"])
def get_organizer_attendance():

    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        organization_id = get_organizer_org_for_feature(cursor)

        if organization_id is None:
            return jsonify({"message": "Organization not found"}), 404

        cursor.execute("""
            SELECT
                r.registration_id,
                u.name AS volunteer_name,
                e.event_name,
                vr.role_name,
                a.attendance_status,
                a.check_in_time
            FROM registrations r
            JOIN users u
                ON r.user_id = u.user_id
            JOIN events e
                ON r.event_id = e.event_id
            LEFT JOIN assignments ass
                ON r.registration_id = ass.registration_id
            LEFT JOIN volunteer_roles vr
                ON ass.role_id = vr.role_id
            LEFT JOIN attendance a
                ON ass.assignment_id = a.assignment_id
            WHERE e.organization_id = %s
              AND r.application_status = 'approved'
            ORDER BY e.event_date DESC, u.name
        """, (organization_id,))

        return jsonify({
            "attendance": cursor.fetchall()
        }), 200

    finally:
        cursor.close()
        db.close()


# ------------------------------------------
# MARK ATTENDANCE
# AUTOMATICALLY ASSIGN AN AVAILABLE ROLE
# ------------------------------------------

@app.route(
    "/api/organizer/attendance/<int:registration_id>",
    methods=["PUT"]
)
def mark_organizer_attendance(registration_id):

    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    data = request.get_json() or {}

    attendance_status = data.get("attendance_status")

    if attendance_status not in ["present", "absent", "late"]:
        return jsonify({"message": "Invalid attendance status"}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        organization_id = get_organizer_org_for_feature(cursor)

        if organization_id is None:
            return jsonify({"message": "Organization not found"}), 404

        # Check registration belongs to this organizer
        cursor.execute("""
            SELECT
                r.registration_id,
                r.event_id
            FROM registrations r
            JOIN events e
                ON r.event_id = e.event_id
            WHERE r.registration_id = %s
              AND e.organization_id = %s
              AND r.application_status = 'approved'
        """, (registration_id, organization_id))

        registration = cursor.fetchone()

        if not registration:
            return jsonify({
                "message": "Approved registration not found"
            }), 404

        # Check whether volunteer already has an assignment
        cursor.execute("""
            SELECT assignment_id, role_id
            FROM assignments
            WHERE registration_id = %s
        """, (registration_id,))

        assignment = cursor.fetchone()

        # Automatically assign an available event role
        if not assignment:

            cursor.execute("""
                SELECT
                    vr.role_id,
                    vr.role_name,
                    vr.required_volunteers,
                    COUNT(ass.assignment_id) AS assigned_count
                FROM volunteer_roles vr
                LEFT JOIN assignments ass
                    ON vr.role_id = ass.role_id
                WHERE vr.event_id = %s
                GROUP BY
                    vr.role_id,
                    vr.role_name,
                    vr.required_volunteers
                HAVING assigned_count < vr.required_volunteers
                ORDER BY assigned_count ASC, vr.role_id ASC
                LIMIT 1
            """, (registration["event_id"],))

            role = cursor.fetchone()

            if not role:
                return jsonify({
                    "message": "No available volunteer role for this event. Please add a role first."
                }), 400

            cursor.execute("""
                INSERT INTO assignments (
                    registration_id,
                    role_id
                )
                VALUES (%s, %s)
            """, (
                registration_id,
                role["role_id"]
            ))

            assignment_id = cursor.lastrowid

        else:

            assignment_id = assignment["assignment_id"]

        # Save or update attendance
        if attendance_status in ["present", "late"]:

            cursor.execute("""
                INSERT INTO attendance (
                    assignment_id,
                    check_in_time,
                    attendance_status
                )
                VALUES (%s, NOW(), %s)
                ON DUPLICATE KEY UPDATE
                    check_in_time = NOW(),
                    attendance_status = %s
            """, (
                assignment_id,
                attendance_status,
                attendance_status
            ))

        else:

            cursor.execute("""
                INSERT INTO attendance (
                    assignment_id,
                    check_in_time,
                    attendance_status
                )
                VALUES (%s, NULL, 'absent')
                ON DUPLICATE KEY UPDATE
                    check_in_time = NULL,
                    attendance_status = 'absent'
            """, (assignment_id,))

        db.commit()

        return jsonify({
            "message": "Attendance saved successfully!"
        }), 200

    except Exception as e:

        db.rollback()

        return jsonify({
            "message": str(e)
        }), 500

    finally:
        cursor.close()
        db.close()


# ------------------------------------------
# GET VOLUNTEERS ELIGIBLE FOR CERTIFICATES
# ------------------------------------------

@app.route(
    "/api/organizer/certificates/eligible",
    methods=["GET"]
)
def get_eligible_certificates():

    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        organization_id = get_organizer_org_for_feature(cursor)

        if organization_id is None:
            return jsonify({"message": "Organization not found"}), 404

        cursor.execute("""
            SELECT
                r.registration_id,
                u.name AS volunteer_name,
                e.event_name,
                a.attendance_status,
                c.certificate_code
            FROM registrations r
            JOIN users u
                ON r.user_id = u.user_id
            JOIN events e
                ON r.event_id = e.event_id
            JOIN assignments ass
                ON r.registration_id = ass.registration_id
            JOIN attendance a
                ON ass.assignment_id = a.assignment_id
            LEFT JOIN certificates c
                ON c.user_id = r.user_id
                AND c.event_id = r.event_id
            WHERE e.organization_id = %s
              AND r.application_status = 'approved'
              AND a.attendance_status = 'present'
            ORDER BY e.event_date DESC, u.name
        """, (organization_id,))

        return jsonify({
            "certificates": cursor.fetchall()
        }), 200

    finally:
        cursor.close()
        db.close()


# ------------------------------------------
# GENERATE CERTIFICATE
# ------------------------------------------

@app.route(
    "/api/organizer/certificates/<int:registration_id>",
    methods=["POST"]
)
def generate_organizer_certificate(registration_id):

    if "user_id" not in session or session.get("user_role") != "organizer":
        return jsonify({"message": "Organizer access required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        organization_id = get_organizer_org_for_feature(cursor)

        if organization_id is None:
            return jsonify({"message": "Organization not found"}), 404

        # Check volunteer is approved and marked present
        cursor.execute("""
            SELECT
                r.user_id,
                r.event_id,
                a.attendance_status
            FROM registrations r
            JOIN events e
                ON r.event_id = e.event_id
            JOIN assignments ass
                ON r.registration_id = ass.registration_id
            JOIN attendance a
                ON ass.assignment_id = a.assignment_id
            WHERE r.registration_id = %s
              AND e.organization_id = %s
              AND r.application_status = 'approved'
              AND a.attendance_status = 'present'
        """, (registration_id, organization_id))

        eligible = cursor.fetchone()

        if not eligible:
            return jsonify({
                "message": "Only approved volunteers marked Present can receive certificates."
            }), 400

        user_id = eligible["user_id"]
        event_id = eligible["event_id"]

        # Prevent duplicate certificates
        cursor.execute("""
            SELECT certificate_code
            FROM certificates
            WHERE user_id = %s
              AND event_id = %s
        """, (user_id, event_id))

        existing = cursor.fetchone()

        if existing:
            return jsonify({
                "message": "Certificate already generated.",
                "certificate_code": existing["certificate_code"]
            }), 200

        # Generate unique certificate code
        certificate_code = (
            "VH-" + secrets.token_hex(6).upper()
        )

        cursor.execute("""
            INSERT INTO certificates (
                user_id,
                event_id,
                certificate_code,
                issue_date
            )
            VALUES (%s, %s, %s, CURDATE())
        """, (
            user_id,
            event_id,
            certificate_code
        ))

        db.commit()

        return jsonify({
            "message": "Certificate generated successfully!",
            "certificate_code": certificate_code
        }), 201

    except Exception as e:

        db.rollback()

        return jsonify({
            "message": str(e)
        }), 500

    finally:
        cursor.close()
        db.close()


# ==========================================
# VOLUNTEER CERTIFICATE PDF DOWNLOAD
# ==========================================

@app.route(
    "/api/volunteer/certificates/<certificate_number>/download",
    methods=["GET"]
)
def download_volunteer_certificate(certificate_number):

    if "user_id" not in session or session.get("user_role") != "volunteer":
        return jsonify({"message": "Volunteer login required"}), 403

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:

        cursor.execute("""
            SELECT
                c.certificate_code,
                c.issue_date,
                u.name AS volunteer_name,
                e.event_name,
                e.event_date,
                e.location
            FROM certificates c
            JOIN users u
                ON c.user_id = u.user_id
            JOIN events e
                ON c.event_id = e.event_id
            WHERE c.certificate_code = %s
              AND c.user_id = %s
        """, (
            certificate_number,
            session["user_id"]
        ))

        certificate = cursor.fetchone()

        if not certificate:
            return jsonify({
                "message": "Certificate not found."
            }), 404

        # Create PDF in memory
        buffer = BytesIO()

        page_size = landscape(A4)

        pdf = canvas.Canvas(
            buffer,
            pagesize=page_size
        )

        width, height = page_size

        # Background
        pdf.setFillColor(HexColor("#F7FAFF"))
        pdf.rect(0, 0, width, height, fill=1, stroke=0)

        # Outer border
        pdf.setStrokeColor(HexColor("#183153"))
        pdf.setLineWidth(5)
        pdf.rect(25, 25, width - 50, height - 50)

        # Inner border
        pdf.setStrokeColor(HexColor("#27AEBB"))
        pdf.setLineWidth(2)
        pdf.rect(35, 35, width - 70, height - 70)

        # Heading
        pdf.setFillColor(HexColor("#183153"))
        pdf.setFont("Helvetica-Bold", 17)
        pdf.drawCentredString(
            width / 2,
            height - 85,
            "VOLUNTEERHUB"
        )

        pdf.setFillColor(HexColor("#D19B35"))
        pdf.setFont("Helvetica-Bold", 29)
        pdf.drawCentredString(
            width / 2,
            height - 145,
            "CERTIFICATE OF APPRECIATION"
        )

        # Main text
        pdf.setFillColor(HexColor("#52647A"))
        pdf.setFont("Helvetica", 16)
        pdf.drawCentredString(
            width / 2,
            height - 205,
            "This certificate is proudly presented to"
        )

        pdf.setFillColor(HexColor("#183153"))
        pdf.setFont("Helvetica-Bold", 30)
        pdf.drawCentredString(
            width / 2,
            height - 260,
            certificate["volunteer_name"]
        )

        pdf.setFillColor(HexColor("#52647A"))
        pdf.setFont("Helvetica", 15)
        pdf.drawCentredString(
            width / 2,
            height - 310,
            "For successfully participating as a volunteer in"
        )

        pdf.setFillColor(HexColor("#159EAB"))
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawCentredString(
            width / 2,
            height - 350,
            certificate["event_name"]
        )

        pdf.setFillColor(HexColor("#52647A"))
        pdf.setFont("Helvetica", 12)

        issue_date = certificate["issue_date"].strftime("%d-%m-%Y")

        pdf.drawCentredString(
            width / 2,
            105,
            f"Issue Date: {issue_date}"
        )

        pdf.drawCentredString(
            width / 2,
            82,
            f"Certificate Number: {certificate['certificate_code']}"
        )

        pdf.setFillColor(HexColor("#183153"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(
            width / 2,
            55,
            "Thank you for making a difference!"
        )

        pdf.save()

        buffer.seek(0)

        filename = f"VolunteerHub_{certificate_number}.pdf"

        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:

        return jsonify({
            "message": str(e)
        }), 500

    finally:
        cursor.close()
        db.close()

# START FLASK SERVER
if __name__ == "__main__":
    app.run(debug=True)
