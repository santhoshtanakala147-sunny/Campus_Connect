from datetime import date, datetime
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from campusconnect import get_db_connection

events_bp = Blueprint("events", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Not authenticated"), 401
        return view(*args, **kwargs)
    return wrapped


def _event_public(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "college": row["college"],
        "event_date": row["event_date"],
        "created_by": row["created_by"],
    }


@events_bp.route("/api/events", methods=["POST"])
@login_required
def create_event():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    event_date = (data.get("event_date") or "").strip()

    if not title or not event_date:
        return jsonify(error="Title and event date are required."), 400

    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        return jsonify(error="event_date must be in YYYY-MM-DD format."), 400

    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    user = conn.execute("SELECT college FROM users WHERE id = ?", (me,)).fetchone()
    cursor = conn.execute(
        "INSERT INTO events (title, description, college, event_date, created_by) VALUES (?, ?, ?, ?, ?)",
        (title, description, user["college"], event_date, me),
    )
    event_id = cursor.lastrowid
    conn.commit()
    row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()

    return jsonify(event=_event_public(row)), 201


@events_bp.route("/api/events")
@login_required
def list_events():
    """Upcoming events, soonest first. `scope=college` (default) restricts to
    the caller's own college; `scope=all` shows every institution's events —
    CampusConnect spans multiple colleges, so both views matter.
    """
    scope = request.args.get("scope", "college")
    conn = get_db_connection(current_app.config["DATABASE_PATH"])

    if scope == "college":
        me = session["user_id"]
        user = conn.execute("SELECT college FROM users WHERE id = ?", (me,)).fetchone()
        rows = conn.execute(
            "SELECT * FROM events WHERE college = ? AND event_date >= ? ORDER BY event_date ASC",
            (user["college"], date.today().isoformat()),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM events WHERE event_date >= ? ORDER BY event_date ASC",
            (date.today().isoformat(),),
        ).fetchall()
    conn.close()

    return jsonify(events=[_event_public(r) for r in rows])
