from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from campusconnect import get_db_connection

profile_bp = Blueprint("profile", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Not authenticated"), 401
        return view(*args, **kwargs)
    return wrapped


@profile_bp.route("/api/dashboard")
@login_required
def dashboard():
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    friend_count = conn.execute(
        "SELECT COUNT(*) AS c FROM friendships WHERE user_id = ?", (session["user_id"],)
    ).fetchone()["c"]
    conn.close()
    return jsonify(
        user={
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "college": user["college"],
        },
        friend_count=friend_count,
    )


@profile_bp.route("/api/profile", methods=["GET"])
@login_required
def get_profile():
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    profile = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return jsonify(
        user={
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "college": user["college"],
        },
        profile={
            "bio": profile["bio"],
            "major": profile["major"],
            "year": profile["year"],
            "interests": profile["interests"],
        },
    )


@profile_bp.route("/api/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    bio = (data.get("bio") or "").strip()
    major = (data.get("major") or "").strip()
    year = (data.get("year") or "").strip()
    interests = (data.get("interests") or "").strip()

    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    conn.execute(
        "UPDATE profiles SET bio = ?, major = ?, year = ?, interests = ? WHERE user_id = ?",
        (bio, major, year, interests, session["user_id"]),
    )
    conn.commit()
    conn.close()
    return jsonify(message="Profile updated.")
