from datetime import date, timedelta
from functools import wraps

from flask import Blueprint, current_app, jsonify, session

from campusconnect import get_db_connection

notifications_bp = Blueprint("notifications", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Not authenticated"), 401
        return view(*args, **kwargs)
    return wrapped


@notifications_bp.route("/api/notifications")
@login_required
def notifications():
    """Aggregates the things a student would want a badge for: pending
    incoming friend requests and events in their college within the next
    7 days. Kept as a light read-only rollup rather than a stored table.
    """
    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])

    incoming_requests = conn.execute(
        """SELECT fr.id, u.full_name FROM friend_requests fr
           JOIN users u ON u.id = fr.sender_id
           WHERE fr.receiver_id = ? AND fr.status = 'pending'
           ORDER BY fr.created_at DESC""",
        (me,),
    ).fetchall()

    user = conn.execute("SELECT college FROM users WHERE id = ?", (me,)).fetchone()
    week_out = (date.today() + timedelta(days=7)).isoformat()
    upcoming_events = conn.execute(
        """SELECT id, title, event_date FROM events
           WHERE college = ? AND event_date BETWEEN ? AND ?
           ORDER BY event_date ASC""",
        (user["college"], date.today().isoformat(), week_out),
    ).fetchall()
    conn.close()

    items = []
    for r in incoming_requests:
        items.append({
            "type": "friend_request",
            "message": f"{r['full_name']} sent you a friend request.",
            "ref_id": r["id"],
        })
    for e in upcoming_events:
        items.append({
            "type": "event",
            "message": f"{e['title']} is coming up on {e['event_date']}.",
            "ref_id": e["id"],
        })

    return jsonify(count=len(items), items=items)
