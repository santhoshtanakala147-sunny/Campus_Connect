import os
import sqlite3
from datetime import datetime

from flask import Flask, send_from_directory

from config import Config
from campusconnect.datastructures.hash_table import HashTable
from campusconnect.datastructures.graph import Graph
from campusconnect.datastructures.trie import Trie
from campusconnect.datastructures.avl_tree import AVLTree

# The frontend lives outside the Python package, as plain static HTML/CSS/JS.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


def get_db_connection(database_path):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(app):
    """Create the SQLite file + tables if they don't exist yet."""
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)
    conn = get_db_connection(app.config["DATABASE_PATH"])
    with open(app.config["SCHEMA_PATH"], "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def load_user_hash_table(app):
    """Load every user row into the in-memory Hash Table for O(1) auth lookups.

    This is the data structure described in the project's design: the
    Hash Table indexes student accounts by email so login/auth doesn't need
    to hit SQLite for the common case.
    """
    table = HashTable()
    conn = get_db_connection(app.config["DATABASE_PATH"])
    rows = conn.execute("SELECT id, email, password_hash, full_name, college FROM users").fetchall()
    conn.close()
    for row in rows:
        table.put(row["email"], dict(row))
    return table


def load_friend_graph(app):
    """Load the friendships table into an in-memory Graph.

    Nodes are user ids, edges are confirmed friendships. This backs
    friend-of-friend / mutual-friend lookups without hitting SQLite.
    """
    graph = Graph()
    conn = get_db_connection(app.config["DATABASE_PATH"])
    users = conn.execute("SELECT id FROM users").fetchall()
    for u in users:
        graph.add_node(u["id"])
    edges = conn.execute("SELECT user_id, friend_id FROM friendships").fetchall()
    conn.close()
    for e in edges:
        graph.add_edge(e["user_id"], e["friend_id"])
    return graph


def index_user_in_trie(trie, user_id, full_name, college):
    """Index every name/college token for a user so any word-prefix finds them."""
    for token in (full_name or "").split():
        trie.insert(token, user_id)
    for token in (college or "").split():
        trie.insert(token, user_id)


def load_student_trie(app):
    """Build the Trie used for fast student/college search with autocomplete."""
    trie = Trie()
    conn = get_db_connection(app.config["DATABASE_PATH"])
    rows = conn.execute("SELECT id, full_name, college FROM users").fetchall()
    conn.close()
    for row in rows:
        index_user_in_trie(trie, row["id"], row["full_name"], row["college"])
    return trie


def post_epoch(created_at):
    """Convert a SQLite 'YYYY-MM-DD HH:MM:SS' timestamp to a sortable epoch."""
    try:
        return datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
    except (ValueError, TypeError):
        return datetime.utcnow().timestamp()


def engagement_score(post):
    """Likes count double, so an active comment thread can outrank a quiet like pile."""
    return post["likes"] + 2 * post["comment_count"]


def load_posts_state(app):
    """Build the in-memory post cache, comment Arrays, and AVL Tree.

    - app.post_store: post_id -> post dict (author, content, likes, comment_count)
    - app.comment_arrays: post_id -> list of comments, in chronological order
      (the "Arrays: store comments for quick sequential access" piece)
    - app.post_tree: AVL Tree keyed by (created_at_epoch, post_id) -> post_id,
      giving a always-sorted chronological feed without re-sorting on read
    """
    conn = get_db_connection(app.config["DATABASE_PATH"])
    posts = conn.execute(
        """SELECT p.*, u.full_name AS author_name FROM posts p
           JOIN users u ON u.id = p.author_id ORDER BY p.created_at"""
    ).fetchall()
    comments = conn.execute("SELECT * FROM comments ORDER BY created_at").fetchall()
    conn.close()

    comment_arrays = {}
    for c in comments:
        comment_arrays.setdefault(c["post_id"], []).append({
            "id": c["id"],
            "author_id": c["author_id"],
            "content": c["content"],
            "created_at": c["created_at"],
        })

    post_store = {}
    tree = AVLTree()
    for p in posts:
        comment_count = len(comment_arrays.get(p["id"], []))
        post_store[p["id"]] = {
            "id": p["id"],
            "author_id": p["author_id"],
            "author_name": p["author_name"],
            "group_id": p["group_id"],
            "content": p["content"],
            "likes": p["likes"],
            "comment_count": comment_count,
            "created_at": p["created_at"],
        }
        tree.insert((post_epoch(p["created_at"]), p["id"]), p["id"])

    return post_store, comment_arrays, tree


def create_app(config_class=Config):
    # static_folder points at the plain HTML/CSS/JS frontend. static_url_path=""
    # means e.g. frontend/login.html is served at GET /login.html.
    app = Flask(__name__, instance_relative_config=False,
                static_folder=FRONTEND_DIR, static_url_path="")
    app.config.from_object(config_class)

    init_db(app)

    # In-memory Hash Table cache of users, keyed by email. Kept in sync with
    # SQLite by every write path (see auth/routes.py).
    app.user_table = load_user_hash_table(app)

    # In-memory Graph of confirmed friendships, keyed by user id. Kept in
    # sync with SQLite by the friends API (see friends/routes.py).
    app.friend_graph = load_friend_graph(app)

    # In-memory Trie indexing name/college tokens -> user ids, for O(len(prefix))
    # search-as-you-type. Kept in sync on registration (see auth/routes.py).
    app.student_trie = load_student_trie(app)

    # Post cache + comment Arrays + AVL Tree (chronological order). Max Heap
    # for trending is built on-demand from app.post_store (see posts/routes.py).
    app.post_store, app.comment_arrays, app.post_tree = load_posts_state(app)

    from campusconnect.auth.routes import auth_bp
    from campusconnect.profile.routes import profile_bp
    from campusconnect.friends.routes import friends_bp
    from campusconnect.posts.routes import posts_bp
    from campusconnect.groups.routes import groups_bp
    from campusconnect.events.routes import events_bp
    from campusconnect.notifications.routes import notifications_bp

    # All blueprints expose JSON-only routes under /api/... — the backend
    # is a REST API, the frontend is a separate set of static files that
    # call it with fetch().
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(friends_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(notifications_bp)

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    return app
