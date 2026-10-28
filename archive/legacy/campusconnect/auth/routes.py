from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from campusconnect import get_db_connection, index_user_in_trie

# REST API blueprint — every route here returns JSON only. The frontend
# (plain HTML/CSS/JS under frontend/) calls these via fetch().
auth_bp = Blueprint("auth", __name__)


def _is_allowed_college_email(email):
    """Suffix match: "iitb.ac.in" is allowed by the ".ac.in" entry, and an
    entry can also be a full domain (e.g. "vit.ac.in") for institutions that
    don't fall under a broader suffix.
    """
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if not domain:
        return False
    return any(domain.endswith(d.lower()) for d in current_app.config["ALLOWED_COLLEGE_EMAIL_DOMAINS"])


def _payload():
    return request.get_json(silent=True) or request.form


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = _payload()
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    college = (data.get("college") or "").strip()
    password = data.get("password") or ""
    confirm_password = data.get("confirm_password") or ""

    if not full_name or not email or not college or not password:
        return jsonify(error="All fields are required."), 400

    if not _is_allowed_college_email(email):
        return jsonify(
            error="Please register with an official college email (.edu, .ac.in, .edu.in, or your institution's official domain)."
        ), 400

    if password != confirm_password:
        return jsonify(error="Passwords do not match."), 400

    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400

    # Hash Table gives us an O(1) existence check before touching SQLite.
    if current_app.user_table.contains(email):
        return jsonify(error="An account with this email already exists."), 409

    password_hash = generate_password_hash(password)

    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, full_name, college) VALUES (?, ?, ?, ?)",
            (email, password_hash, full_name, college),
        )
        user_id = cursor.lastrowid
        conn.execute("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        return jsonify(error="Something went wrong creating your account. Please try again."), 500
    finally:
        conn.close()

    # Keep the in-memory Hash Table in sync with the new SQLite row.
    current_app.user_table.put(email, {
        "id": user_id,
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "college": college,
    })

    # Register the new student as a node in the friend Graph.
    current_app.friend_graph.add_node(user_id)

    # Index the new student's name/college tokens in the search Trie.
    index_user_in_trie(current_app.student_trie, user_id, full_name, college)

    return jsonify(message="Account created."), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = _payload()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    # O(1) lookup via the Hash Table instead of a SQLite query.
    user = current_app.user_table.get(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Invalid email or password."), 401

    session["user_id"] = user["id"]
    session["full_name"] = user["full_name"]
    return jsonify(message="Logged in.", user={
        "id": user["id"], "full_name": user["full_name"], "email": user["email"],
    })


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify(message="Logged out.")


@auth_bp.route("/api/auth/me")
def me():
    if not session.get("user_id"):
        return jsonify(error="Not authenticated"), 401
    return jsonify(user_id=session["user_id"], full_name=session.get("full_name"))
