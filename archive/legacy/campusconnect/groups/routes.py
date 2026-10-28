from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from campusconnect import get_db_connection

groups_bp = Blueprint("groups", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Not authenticated"), 401
        return view(*args, **kwargs)
    return wrapped


def _group_public(row, member_count, is_member):
    return {
        "id": row["id"],
        "name": row["name"],
        "topic": row["topic"],
        "created_by": row["created_by"],
        "member_count": member_count,
        "is_member": is_member,
    }


@groups_bp.route("/api/groups", methods=["GET"])
@login_required
def list_groups():
    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    rows = conn.execute("SELECT * FROM groups ORDER BY created_at DESC").fetchall()
    result = []
    for row in rows:
        member_count = conn.execute(
            "SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?", (row["id"],)
        ).fetchone()["c"]
        is_member = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (row["id"], me)
        ).fetchone() is not None
        result.append(_group_public(row, member_count, is_member))
    conn.close()
    return jsonify(groups=result)


@groups_bp.route("/api/groups", methods=["POST"])
@login_required
def create_group():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    topic = (data.get("topic") or "").strip()
    if not name or not topic:
        return jsonify(error="Group name and topic are required."), 400

    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    cursor = conn.execute(
        "INSERT INTO groups (name, topic, created_by) VALUES (?, ?, ?)", (name, topic, me),
    )
    group_id = cursor.lastrowid
    conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)", (group_id, me))
    conn.commit()
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    conn.close()

    return jsonify(group=_group_public(row, 1, True)), 201


@groups_bp.route("/api/groups/<int:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id):
    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    exists = conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone()
    if exists is None:
        conn.close()
        return jsonify(error="Group not found."), 404
    conn.execute(
        "INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)", (group_id, me),
    )
    conn.commit()
    conn.close()
    return jsonify(message="Joined group.")


@groups_bp.route("/api/groups/<int:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id):
    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, me))
    conn.commit()
    conn.close()
    return jsonify(message="Left group.")


@groups_bp.route("/api/groups/<int:group_id>")
@login_required
def get_group(group_id):
    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify(error="Group not found."), 404
    member_count = conn.execute(
        "SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?", (group_id,)
    ).fetchone()["c"]
    is_member = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, me)
    ).fetchone() is not None
    conn.close()
    return jsonify(group=_group_public(row, member_count, is_member))


@groups_bp.route("/api/groups/<int:group_id>/posts")
@login_required
def group_posts(group_id):
    """Posts scoped to a group, newest first — filtered from the same
    AVL-Tree-ordered id sequence used by the main feed.
    """
    ordered_ids = current_app.post_tree.inorder_desc()
    posts = [
        current_app.post_store[pid] for pid in ordered_ids
        if pid in current_app.post_store and current_app.post_store[pid].get("group_id") == group_id
    ]
    from campusconnect.posts.routes import _post_public
    return jsonify(posts=[_post_public(p) for p in posts])
