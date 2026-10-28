from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from campusconnect import get_db_connection

friends_bp = Blueprint("friends", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Not authenticated"), 401
        return view(*args, **kwargs)
    return wrapped


def _user_public(row):
    return {"id": row["id"], "full_name": row["full_name"], "college": row["college"], "email": row["email"]}


@friends_bp.route("/api/students/search")
@login_required
def search_students():
    """Trie-backed prefix search over student name/college tokens.

    Every word of every student's name and college is indexed in
    app.student_trie (see campusconnect/datastructures/trie.py), so a query
    like "sant" instantly matches "Santhosh" via an O(len(prefix)) walk —
    this is the autocomplete-while-searching behaviour called for in the
    project design.
    """
    q = (request.args.get("q") or "").strip()
    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])

    if q:
        matched_ids = current_app.student_trie.search_prefix(q)
        matched_ids.discard(me)
        if not matched_ids:
            conn.close()
            return jsonify(results=[])
        placeholders = ",".join("?" * len(matched_ids))
        rows = conn.execute(
            f"""SELECT id, full_name, email, college FROM users
                WHERE id IN ({placeholders}) ORDER BY full_name LIMIT 20""",
            tuple(matched_ids),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, full_name, email, college FROM users WHERE id != ? ORDER BY full_name LIMIT 20",
            (me,),
        ).fetchall()
    conn.close()

    graph = current_app.friend_graph
    results = []
    for row in rows:
        results.append({
            **_user_public(row),
            "is_friend": graph.are_friends(me, row["id"]),
        })
    return jsonify(results=results)


@friends_bp.route("/api/friends/request", methods=["POST"])
@login_required
def send_request():
    data = request.get_json(silent=True) or {}
    receiver_id = data.get("receiver_id")
    me = session["user_id"]

    if not receiver_id or int(receiver_id) == me:
        return jsonify(error="Invalid recipient."), 400
    receiver_id = int(receiver_id)

    if current_app.friend_graph.are_friends(me, receiver_id):
        return jsonify(error="You are already friends."), 409

    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    receiver = conn.execute("SELECT id FROM users WHERE id = ?", (receiver_id,)).fetchone()
    if receiver is None:
        conn.close()
        return jsonify(error="Student not found."), 404

    existing = conn.execute(
        """SELECT id, status FROM friend_requests
           WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)""",
        (me, receiver_id, receiver_id, me),
    ).fetchone()
    if existing and existing["status"] == "pending":
        conn.close()
        return jsonify(error="A friend request is already pending."), 409

    try:
        if existing:
            conn.execute(
                "UPDATE friend_requests SET status = 'pending', sender_id = ?, receiver_id = ? WHERE id = ?",
                (me, receiver_id, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO friend_requests (sender_id, receiver_id, status) VALUES (?, ?, 'pending')",
                (me, receiver_id),
            )
        conn.commit()
    finally:
        conn.close()

    return jsonify(message="Friend request sent."), 201


@friends_bp.route("/api/friends/requests")
@login_required
def list_requests():
    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    incoming = conn.execute(
        """SELECT fr.id AS request_id, u.id, u.full_name, u.email, u.college
           FROM friend_requests fr JOIN users u ON u.id = fr.sender_id
           WHERE fr.receiver_id = ? AND fr.status = 'pending'""",
        (me,),
    ).fetchall()
    outgoing = conn.execute(
        """SELECT fr.id AS request_id, u.id, u.full_name, u.email, u.college
           FROM friend_requests fr JOIN users u ON u.id = fr.receiver_id
           WHERE fr.sender_id = ? AND fr.status = 'pending'""",
        (me,),
    ).fetchall()
    conn.close()

    return jsonify(
        incoming=[{**_user_public(r), "request_id": r["request_id"]} for r in incoming],
        outgoing=[{**_user_public(r), "request_id": r["request_id"]} for r in outgoing],
    )


@friends_bp.route("/api/friends/requests/<int:request_id>/respond", methods=["POST"])
@login_required
def respond_request(request_id):
    data = request.get_json(silent=True) or {}
    action = data.get("action")  # "accept" or "reject"
    if action not in ("accept", "reject"):
        return jsonify(error="action must be 'accept' or 'reject'."), 400

    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    req = conn.execute(
        "SELECT * FROM friend_requests WHERE id = ? AND receiver_id = ? AND status = 'pending'",
        (request_id, me),
    ).fetchone()
    if req is None:
        conn.close()
        return jsonify(error="Request not found."), 404

    new_status = "accepted" if action == "accept" else "rejected"
    conn.execute("UPDATE friend_requests SET status = ? WHERE id = ?", (new_status, request_id))

    if action == "accept":
        conn.execute(
            "INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (req["sender_id"], req["receiver_id"]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)",
            (req["receiver_id"], req["sender_id"]),
        )
    conn.commit()
    conn.close()

    if action == "accept":
        # Keep the in-memory Graph in sync with the new friendship edge.
        current_app.friend_graph.add_edge(req["sender_id"], req["receiver_id"])

    return jsonify(message=f"Request {new_status}.")


@friends_bp.route("/api/friends")
@login_required
def list_friends():
    me = session["user_id"]
    friend_ids = current_app.friend_graph.neighbors(me)
    if not friend_ids:
        return jsonify(friends=[])

    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    placeholders = ",".join("?" * len(friend_ids))
    rows = conn.execute(
        f"SELECT id, full_name, email, college FROM users WHERE id IN ({placeholders}) ORDER BY full_name",
        tuple(friend_ids),
    ).fetchall()
    conn.close()

    return jsonify(friends=[_user_public(r) for r in rows])


@friends_bp.route("/api/friends/<int:other_id>/mutual")
@login_required
def mutual_friends(other_id):
    me = session["user_id"]
    mutual_ids = current_app.friend_graph.mutual_friends(me, other_id)
    if not mutual_ids:
        return jsonify(mutual=[])

    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    placeholders = ",".join("?" * len(mutual_ids))
    rows = conn.execute(
        f"SELECT id, full_name, email, college FROM users WHERE id IN ({placeholders})",
        tuple(mutual_ids),
    ).fetchall()
    conn.close()

    return jsonify(mutual=[_user_public(r) for r in rows])
