from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session

from campusconnect import engagement_score, get_db_connection, post_epoch
from campusconnect.datastructures.max_heap import MaxHeap

posts_bp = Blueprint("posts", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Not authenticated"), 401
        return view(*args, **kwargs)
    return wrapped


def _post_public(post):
    return {
        "id": post["id"],
        "author_id": post["author_id"],
        "author_name": post["author_name"],
        "group_id": post.get("group_id"),
        "content": post["content"],
        "likes": post["likes"],
        "comment_count": post["comment_count"],
        "created_at": post["created_at"],
    }


@posts_bp.route("/api/posts", methods=["POST"])
@login_required
def create_post():
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    group_id = data.get("group_id")
    if not content:
        return jsonify(error="Post content cannot be empty."), 400
    if len(content) > 2000:
        return jsonify(error="Post is too long (max 2000 characters)."), 400

    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    author = conn.execute("SELECT full_name FROM users WHERE id = ?", (me,)).fetchone()

    if group_id is not None:
        member = conn.execute(
            "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, me),
        ).fetchone()
        if member is None:
            conn.close()
            return jsonify(error="Join the group before posting in it."), 403

    cursor = conn.execute(
        "INSERT INTO posts (author_id, group_id, content) VALUES (?, ?, ?)", (me, group_id, content),
    )
    post_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    conn.commit()
    conn.close()

    post = {
        "id": post_id,
        "author_id": me,
        "author_name": author["full_name"],
        "group_id": group_id,
        "content": content,
        "likes": 0,
        "comment_count": 0,
        "created_at": row["created_at"],
    }

    # Keep the in-memory cache + AVL Tree (chronological order) in sync.
    current_app.post_store[post_id] = post
    current_app.comment_arrays[post_id] = []
    current_app.post_tree.insert((post_epoch(row["created_at"]), post_id), post_id)

    return jsonify(post=_post_public(post)), 201


@posts_bp.route("/api/posts/feed")
@login_required
def feed():
    """Chronological feed, newest first — an in-order traversal of the AVL Tree."""
    limit = min(int(request.args.get("limit", 20)), 50)
    ordered_ids = current_app.post_tree.inorder_desc()
    posts = [
        current_app.post_store[pid] for pid in ordered_ids
        if pid in current_app.post_store and current_app.post_store[pid].get("group_id") is None
    ][:limit]
    return jsonify(posts=[_post_public(p) for p in posts])


@posts_bp.route("/api/posts/trending")
@login_required
def trending():
    """Trending feed — build a Max Heap from current engagement scores and
    pop the top N. Rebuilt per-request since likes/comments change often;
    this is O(n) heapify + O(k log n) extraction, not a full re-sort.
    """
    limit = min(int(request.args.get("limit", 10)), 50)
    scored = [
        (engagement_score(p), p["id"]) for p in current_app.post_store.values()
        if p.get("group_id") is None
    ]
    heap = MaxHeap.build(scored)
    top_ids = heap.top_k(limit)
    posts = [current_app.post_store[pid] for pid in top_ids if pid in current_app.post_store]
    return jsonify(posts=[_post_public(p) for p in posts])


@posts_bp.route("/api/posts/<int:post_id>/like", methods=["POST"])
@login_required
def like_post(post_id):
    post = current_app.post_store.get(post_id)
    if post is None:
        return jsonify(error="Post not found."), 404

    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    conn.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

    post["likes"] += 1
    return jsonify(post=_post_public(post))


@posts_bp.route("/api/posts/<int:post_id>/comments", methods=["GET"])
@login_required
def list_comments(post_id):
    if post_id not in current_app.post_store:
        return jsonify(error="Post not found."), 404
    # Sequential read of the comments Array for this post.
    return jsonify(comments=current_app.comment_arrays.get(post_id, []))


@posts_bp.route("/api/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def add_comment(post_id):
    post = current_app.post_store.get(post_id)
    if post is None:
        return jsonify(error="Post not found."), 404

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify(error="Comment cannot be empty."), 400

    me = session["user_id"]
    conn = get_db_connection(current_app.config["DATABASE_PATH"])
    cursor = conn.execute(
        "INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
        (post_id, me, content),
    )
    comment_id = cursor.lastrowid
    row = conn.execute("SELECT created_at FROM comments WHERE id = ?", (comment_id,)).fetchone()
    conn.commit()
    conn.close()

    comment = {"id": comment_id, "author_id": me, "content": content, "created_at": row["created_at"]}

    # Append to this post's comments Array and bump the cached count used by
    # the trending Max Heap.
    current_app.comment_arrays.setdefault(post_id, []).append(comment)
    post["comment_count"] += 1

    return jsonify(comment=comment), 201
