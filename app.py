"""CampusConnect — Flask REST API.

Every request is served from in-memory data structures that are loaded from
SQLite at startup and kept in sync on every write (SQLite stays the source of
truth):

    HashTable  email -> user              login / duplicate-email check, O(1)
    Graph      user  <-> user             friends, mutual friends, BFS suggestions
    Trie       name/college/email words   student search with prefix autocomplete
    Trie       group name/topic words     topic search
    AVLTree    (timestamp, id) -> post    chronological feed, O(log n) insert/delete
    MaxHeap    (engagement, time) -> post trending feed
    list       comments per post          sequential access in posting order

The data structures themselves live in the `datastructures/` package.
"""

import hashlib
import os
import secrets
import smtplib
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from itertools import islice

from flask import Flask, current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import re
from urllib.parse import parse_qs, urlsplit

from ai import moderation, pet
from config import Config
import seed_demo
from content import images, reels_seed, youtube
from datastructures import AVLTree, Graph, HashTable, MaxHeap, Trie

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


# ============================================================================
# State: every in-memory structure, plus the lock that guards them
# ============================================================================

class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.user_table = HashTable()   # email -> user dict
        self.user_by_id = {}            # id -> user dict (same dicts as user_table)
        self.friend_graph = Graph()     # user_id <-> user_id
        self.student_trie = Trie()      # name/college/email word -> user ids
        self.group_trie = Trie()        # group name/topic word -> group ids
        self.post_store = {}            # post_id -> post dict
        self.post_keys = {}             # post_id -> AVL key
        self.post_likes = {}            # post_id -> set(user_id)
        self.post_saves = {}            # post_id -> set(user_id)  (private bookmarks)
        self.comment_arrays = {}        # post_id -> [comment, ...] oldest first
        self.post_tree = AVLTree()      # (epoch, post_id) -> post_id
        self.login_failures = {}        # (ip, email) -> [timestamps]
        self.mod_cache = moderation.new_cache()   # sha256(kind+text) -> Verdict (LRU)
        self.recent_posts = {}          # user_id -> (digest, time) for duplicate-spam checks
        self.chat_times = {}            # user_id -> [timestamps] for the pet chat rate limit
        self.dm_threads = {}            # (low_id, high_id) -> [message, ...] oldest first (array per conversation)
        self.dm_unread = {}             # (receiver_id, sender_id) -> unread count
        self.dm_times = {}              # user_id -> [timestamps] for the chat rate limit


def S():
    return current_app.extensions["cc"]


# ============================================================================
# Database helpers (one connection per request, always closed)
# ============================================================================

def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def init_db(app):
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)
    conn = connect(app.config["DATABASE_PATH"])
    with open(app.config["SCHEMA_PATH"]) as f:
        conn.executescript(f.read())
    # Migration for databases created before email verification existed:
    # those accounts are treated as already verified.
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)")]
    if "verified" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN verified INTEGER NOT NULL DEFAULT 1")
    if "image" not in [r["name"] for r in conn.execute("PRAGMA table_info(posts)")]:
        conn.execute("ALTER TABLE posts ADD COLUMN image TEXT NOT NULL DEFAULT ''")
    if "image" not in [r["name"] for r in conn.execute("PRAGMA table_info(events)")]:
        conn.execute("ALTER TABLE events ADD COLUMN image TEXT NOT NULL DEFAULT ''")
    post_cols = [r["name"] for r in conn.execute("PRAGMA table_info(posts)")]
    for col in ("video", "video_title"):
        if col not in post_cols:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
    seed_reels(conn)
    conn.commit()
    if app.config.get("DEMO_DATA"):
        seed_demo.auto_seed(conn)
    conn.close()


def seed_reels(conn):
    """Insert/refresh the curated reels (keyed by slug, so likes survive restarts)."""
    for r in reels_seed.REELS:
        conn.execute(
            """INSERT INTO reels (slug, kind, media, media_ref, title, description, topic, license, credit, source_url, code_ref)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET kind=excluded.kind, media=excluded.media, media_ref=excluded.media_ref,
                 title=excluded.title, description=excluded.description, topic=excluded.topic, license=excluded.license,
                 credit=excluded.credit, source_url=excluded.source_url, code_ref=excluded.code_ref""",
            (r["slug"], r["kind"], r["media"], r["media_ref"], r["title"], r["description"], r["topic"],
             r["license"], r["credit"], r["source_url"], r.get("code", "")))


YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
                 "youtube-nocookie.com", "www.youtube-nocookie.com", "youtu.be", "www.youtu.be"}


def parse_youtube(raw):
    """Return (video_id, start_seconds) for a YouTube link, or None. Only the 11-char id is kept,
    so nothing else from the submitted URL ever reaches the page."""
    try:
        parts = urlsplit(raw.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or (parts.hostname or "").lower() not in YOUTUBE_HOSTS:
        return None
    host, vid = parts.hostname.lower(), None
    segs = [s for s in parts.path.split("/") if s]
    qs = parse_qs(parts.query)
    if host.endswith("youtu.be"):
        vid = segs[0] if segs else None
    elif segs and segs[0] in ("shorts", "embed", "live", "v") and len(segs) > 1:
        vid = segs[1]
    elif segs and segs[0] == "watch":
        vid = (qs.get("v") or [None])[0]
    if not vid or not YOUTUBE_ID.match(vid):
        return None
    start = 0
    t = (qs.get("t") or qs.get("start") or [""])[0]
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?", t) if t else None
    if m and any(m.groups()):
        h, mi, se = (int(x or 0) for x in m.groups())
        start = min(h * 3600 + mi * 60 + se, 86400)
    return vid, start


def load_secret_key(app):
    if app.config.get("SECRET_KEY"):
        return app.config["SECRET_KEY"]
    path = os.path.join(os.path.dirname(app.config["DATABASE_PATH"]), "secret_key")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(secrets.token_hex(32))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    with open(path) as f:
        return f.read().strip()


# ============================================================================
# Cache loading / helpers shared by the routes
# ============================================================================

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def post_epoch(created_at):
    """SQLite 'YYYY-MM-DD HH:MM:SS' (UTC) -> sortable epoch seconds."""
    try:
        return datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
    except (ValueError, TypeError):
        return utc_now().timestamp()


def engagement_score(post):
    """Likes count once, comments twice; ties go to the newer post."""
    return (post["likes"] + 2 * post["comment_count"], post_epoch(post["created_at"]))


def _tokens(*texts):
    for text in texts:
        for word in (text or "").replace(",", " ").replace("-", " ").split():
            yield word


def index_student(st, user):
    for word in _tokens(user["full_name"], user["college"], user["email"].split("@")[0]):
        st.student_trie.insert(word, user["id"])


def index_group(st, group_id, name, topic):
    for word in _tokens(name, topic):
        st.group_trie.insert(word, group_id)


def search_words(trie, query):
    """Every whitespace-separated word must prefix-match something (AND)."""
    words = [w for w in query.split() if w]
    if not words:
        return set()
    result = trie.search_prefix(words[0])
    for w in words[1:]:
        result &= trie.search_prefix(w)
        if not result:
            break
    return result


def add_post_to_caches(st, post, comments=()):
    st.post_store[post["id"]] = post
    st.comment_arrays[post["id"]] = list(comments)
    key = (post_epoch(post["created_at"]), post["id"])
    st.post_keys[post["id"]] = key
    st.post_tree.insert(key, post["id"])


def thread_key(a, b):
    """One key per pair of students, whichever way round the ids come."""
    return (a, b) if a < b else (b, a)


def load_caches(app):
    st = app.extensions["cc"]
    conn = connect(app.config["DATABASE_PATH"])
    try:
        for row in conn.execute("SELECT * FROM users"):
            user = dict(row)
            st.user_table.put(user["email"], user)
            st.user_by_id[user["id"]] = user
            st.friend_graph.add_node(user["id"])
            index_student(st, user)

        for row in conn.execute("SELECT user_id, friend_id FROM friendships"):
            st.friend_graph.add_edge(row["user_id"], row["friend_id"])

        for row in conn.execute("SELECT id, name, topic FROM groups"):
            index_group(st, row["id"], row["name"], row["topic"])

        for row in conn.execute("SELECT post_id, user_id FROM post_likes"):
            st.post_likes.setdefault(row["post_id"], set()).add(row["user_id"])

        for row in conn.execute("SELECT post_id, user_id FROM post_saves"):
            st.post_saves.setdefault(row["post_id"], set()).add(row["user_id"])

        for row in conn.execute("SELECT * FROM messages ORDER BY id"):
            msg = {"id": row["id"], "sender_id": row["sender_id"], "receiver_id": row["receiver_id"],
                   "content": row["content"], "created_at": row["created_at"], "read": row["read_at"] is not None}
            st.dm_threads.setdefault(thread_key(row["sender_id"], row["receiver_id"]), []).append(msg)
            if not msg["read"]:
                k = (row["receiver_id"], row["sender_id"])
                st.dm_unread[k] = st.dm_unread.get(k, 0) + 1

        comments = {}
        for row in conn.execute(
            """SELECT c.*, u.full_name AS author_name FROM comments c
               JOIN users u ON u.id = c.author_id ORDER BY c.created_at, c.id"""
        ):
            comments.setdefault(row["post_id"], []).append({
                "id": row["id"], "author_id": row["author_id"], "author_name": row["author_name"],
                "content": row["content"], "created_at": row["created_at"],
            })

        for row in conn.execute(
            """SELECT p.*, u.full_name AS author_name FROM posts p
               JOIN users u ON u.id = p.author_id ORDER BY p.created_at, p.id"""
        ):
            cs = comments.get(row["id"], [])
            add_post_to_caches(st, {
                "id": row["id"], "author_id": row["author_id"], "author_name": row["author_name"],
                "group_id": row["group_id"], "content": row["content"], "image": row["image"] or "",
                "video": row["video"] or "", "video_title": row["video_title"] or "",
                "likes": len(st.post_likes.get(row["id"], ())),
                "comment_count": len(cs), "created_at": row["created_at"],
            }, cs)
    finally:
        conn.close()


# ============================================================================
# Small helpers
# ============================================================================

def error(message, status, **extra):
    return jsonify(error=message, **extra), status


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id") or session["user_id"] not in S().user_by_id:
            session.clear()
            return error("Not authenticated", 401)
        return view(*args, **kwargs)
    return wrapped


def int_arg(name, default, lo, hi):
    """Query-string integer clamped to [lo, hi]; bad input falls back to default."""
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def to_int(value):
    """int(value) for JSON ids, or None when it isn't a clean integer."""
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_allowed_email(email, domains):
    if email.count("@") != 1:
        return False
    local, domain = email.rsplit("@", 1)
    if not local or "." not in domain or " " in email:
        return False
    for d in domains:
        d = d.lower()
        if d.startswith("."):
            if domain.endswith(d):
                return True
        elif domain == d or domain.endswith("." + d):
            return True
    return False


def public_user(row):
    return {"id": row["id"], "full_name": row["full_name"], "email": row["email"], "college": row["college"]}


def public_post(post, me):
    return {
        "id": post["id"], "author_id": post["author_id"], "author_name": post["author_name"],
        "group_id": post["group_id"], "content": post["content"], "likes": post["likes"],
        "comment_count": post["comment_count"], "created_at": post["created_at"],
        "liked": me in S().post_likes.get(post["id"], ()),
        "saved": me in S().post_saves.get(post["id"], ()),
        "image_url": f"/api/uploads/{post['image']}" if post.get("image") else None,
        "video": {"id": post["video"], "title": post.get("video_title") or "Video"} if post.get("video") else None,
        "can_delete": post["author_id"] == me,
    }


def public_group(row, member_count, is_member):
    return {
        "id": row["id"], "name": row["name"], "topic": row["topic"],
        "created_by": row["created_by"], "member_count": member_count, "is_member": bool(is_member),
    }


def is_group_member(conn, group_id, user_id):
    return conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id)
    ).fetchone() is not None


def can_see_post(conn, post, me):
    return post["group_id"] is None or is_group_member(conn, post["group_id"], me)


def clean(data, key, limit):
    return str(data.get(key) or "").strip()[:limit]


# ============================================================================
# Email verification
# ============================================================================

def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_verification(conn, user, base_url):
    token = secrets.token_urlsafe(32)
    expires = (utc_now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("DELETE FROM email_tokens WHERE user_id = ?", (user["id"],))
    conn.execute("INSERT INTO email_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                 (_hash_token(token), user["id"], expires))
    conn.commit()
    link = f"{base_url}api/auth/verify?token={token}"
    send_mail(user["email"], "Verify your CampusConnect account",
              f"Hi {user['full_name']},\n\nConfirm your college email to activate your account:\n{link}\n\n"
              "The link works for 24 hours. If you didn't sign up, ignore this email.")


def send_mail(to, subject, body):
    cfg = current_app.config
    if not cfg.get("SMTP_HOST"):
        print(f"\n[CampusConnect] (no SMTP configured) email to {to}\n  {subject}\n  {body}\n", flush=True)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_FROM"], to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as smtp:
            smtp.starttls()
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
    except Exception as exc:  # don't fail registration because the mail server is down
        print(f"[CampusConnect] could not send email to {to}: {exc}", flush=True)


# ============================================================================
# App factory
# ============================================================================

def create_app(overrides=None):
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.config.from_object(Config)
    app.config.update(overrides or {})
    app.config.setdefault("DATABASE_PATH", os.path.join(BASE_DIR, "instance", "campusconnect.db"))
    app.config.setdefault("SCHEMA_PATH", os.path.join(BASE_DIR, "schema.sql"))
    app.config.setdefault("MAX_CONTENT_LENGTH", 4 * 1024 * 1024)   # poster uploads are <= 2 MB (base64 in JSON)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    init_db(app)
    app.config["SECRET_KEY"] = load_secret_key(app)
    app.extensions["cc"] = State()
    load_caches(app)

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.before_request
    def require_json_for_writes():
        # Cross-site <form> posts can't send application/json, so insisting on
        # it (plus SameSite=Lax cookies) blocks CSRF without tokens.
        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not request.is_json:
                return error("Requests must be sent as application/json.", 415)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    register_routes(app)
    return app


def register_routes(app):

    def moderate(kind, *texts, check_links=True, dedupe=False, context=""):
        """Run the safety checks. Returns (error_response_or_None, verdict)."""
        verdict = moderation.check(app.config, S(), get_db(), kind=kind,
                                   text="\n".join(t for t in texts if t), user_id=session["user_id"],
                                   check_links=check_links, dedupe=dedupe, context=context)
        if verdict.allowed:
            return None, verdict
        return error(verdict.reason, verdict.status, code=verdict.code, categories=verdict.categories), verdict

    # ---- Auth -----------------------------------------------------------

    @app.route("/api/auth/register", methods=["POST"])
    def register():
        st = S()
        data = request.get_json(silent=True) or {}
        full_name = clean(data, "full_name", 100)
        email = clean(data, "email", 200).lower()
        college = clean(data, "college", 120)
        password = data.get("password") or ""
        confirm = data.get("confirm_password") or ""

        if not full_name or not email or not college or not password:
            return error("All fields are required.", 400)
        if not is_allowed_email(email, app.config["ALLOWED_COLLEGE_EMAIL_DOMAINS"]):
            return error("Please register with an official college email "
                         "(.edu, .ac.in, .edu.in, or your institution's official domain).", 400)
        if password != confirm:
            return error("Passwords do not match.", 400)
        if len(password) < 8:
            return error("Password must be at least 8 characters.", 400)

        require_verification = app.config["REQUIRE_EMAIL_VERIFICATION"]
        with st.lock:
            if st.user_table.contains(email):
                return error("An account with this email already exists.", 409)
            conn = get_db()
            password_hash = generate_password_hash(password)
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash, full_name, college, verified) VALUES (?, ?, ?, ?, ?)",
                (email, password_hash, full_name, college, 0 if require_verification else 1),
            )
            user_id = cursor.lastrowid
            conn.execute("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
            conn.commit()

            user = {"id": user_id, "email": email, "password_hash": password_hash, "full_name": full_name,
                    "college": college, "verified": 0 if require_verification else 1}
            st.user_table.put(email, user)
            st.user_by_id[user_id] = user
            st.friend_graph.add_node(user_id)
            index_student(st, user)

        if require_verification:
            issue_verification(get_db(), user, request.host_url)
            return jsonify(message="Account created. Check your college email for a verification link.",
                           verification_required=True), 201
        return jsonify(message="Account created.", verification_required=False), 201

    @app.route("/api/auth/verify")
    def verify_email():
        token = request.args.get("token", "")
        conn = get_db()
        row = conn.execute("SELECT * FROM email_tokens WHERE token_hash = ?", (_hash_token(token),)).fetchone()
        now = utc_now().strftime("%Y-%m-%d %H:%M:%S")
        ok = row is not None and row["expires_at"] >= now
        if ok:
            conn.execute("UPDATE users SET verified = 1 WHERE id = ?", (row["user_id"],))
            conn.execute("DELETE FROM email_tokens WHERE user_id = ?", (row["user_id"],))
            conn.commit()
            with S().lock:
                user = S().user_by_id.get(row["user_id"])
                if user:
                    user["verified"] = 1
        msg = ("Email verified — you can now log in." if ok
               else "This verification link is invalid or has expired. Request a new one from the login page.")
        return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                f"<title>CampusConnect</title><body style='font-family:system-ui;max-width:420px;margin:15vh auto;"
                f"text-align:center'><h2>{'Verified' if ok else 'Link not valid'}</h2><p>{msg}</p>"
                f"<p><a href='/'>Go to CampusConnect</a></p></body>"), (200 if ok else 400)

    @app.route("/api/auth/resend", methods=["POST"])
    def resend_verification():
        data = request.get_json(silent=True) or {}
        email = clean(data, "email", 200).lower()
        user = S().user_table.get(email)
        if user and not user["verified"]:
            if throttled(("resend", request.remote_addr, email)):
                return error("Too many requests. Try again in a few minutes.", 429)
            record_failure(("resend", request.remote_addr, email))
            issue_verification(get_db(), user, request.host_url)
        # Same reply either way so this can't be used to discover accounts.
        return jsonify(message="If that account exists and is unverified, a new link was sent.")

    def throttled(key):
        st, cfg = S(), app.config
        now = time.time()
        with st.lock:
            recent = [t for t in st.login_failures.get(key, []) if now - t < cfg["LOGIN_WINDOW_SECONDS"]]
            st.login_failures[key] = recent
            return len(recent) >= cfg["LOGIN_MAX_FAILURES"]

    def record_failure(key):
        with S().lock:
            S().login_failures.setdefault(key, []).append(time.time())

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        email = clean(data, "email", 200).lower()
        password = data.get("password") or ""
        key = ("login", request.remote_addr, email)

        if throttled(key):
            return error("Too many failed attempts. Try again in a few minutes.", 429)

        user = S().user_table.get(email)  # O(1) hash-table lookup, no SQL
        if user is None or not check_password_hash(user["password_hash"], password):
            record_failure(key)
            return error("Invalid email or password.", 401)
        if not user["verified"]:
            return error("Please verify your college email first — check your inbox, "
                         "or use \"Resend verification email\" below.", 403, code="unverified")

        S().login_failures.pop(key, None)
        session.clear()
        session["user_id"] = user["id"]
        session.permanent = True
        if app.config.get("DEMO_DATA"):
            hubs = seed_demo.introduce(get_db(), user["id"])
            with S().lock:
                for hub in hubs:
                    S().friend_graph.add_edge(user["id"], hub)
        return jsonify(message="Logged in.", user=public_user(user))

    @app.route("/api/auth/logout", methods=["POST"])
    def logout():
        session.clear()
        return jsonify(message="Logged out.")

    @app.route("/api/auth/me")
    def me():
        uid = session.get("user_id")
        user = S().user_by_id.get(uid)
        if not user:
            return error("Not authenticated", 401)
        return jsonify(user_id=uid, full_name=user["full_name"])

    # ---- Dashboard / profile -------------------------------------------

    @app.route("/api/dashboard")
    @login_required
    def dashboard():
        me_id = session["user_id"]
        st = S()
        with st.lock:
            friend_count = st.friend_graph.degree(me_id)
        return jsonify(user=public_user(st.user_by_id[me_id]), friend_count=friend_count)

    @app.route("/api/network")
    @login_required
    def network():
        """The signed-in student's friend network for the dashboard graph.

        Level-order BFS from the student out to 2 hops over the friend Graph:
        level 1 = friends, level 2 = friends of friends (capped so the picture
        stays readable). Returns nodes plus every edge between those nodes.
        """
        me_id, st = session["user_id"], S()
        cap = int_arg("limit", 14, 1, 40)
        with st.lock:
            graph = st.friend_graph
            level = {me_id: 0}
            order = [me_id]
            for friend in sorted(graph.neighbors(me_id)):
                level[friend] = 1
                order.append(friend)
            for friend in list(order[1:]):
                for fof in sorted(graph.neighbors(friend)):
                    if fof not in level and sum(1 for v in level.values() if v == 2) < cap:
                        level[fof] = 2
                        order.append(fof)
            nodes = [{**public_user(st.user_by_id[uid]), "level": level[uid],
                      "degree": graph.degree(uid),
                      "mutual_count": len(graph.mutual_friends(me_id, uid)) if uid != me_id else 0}
                     for uid in order if uid in st.user_by_id]
            keep = {n["id"] for n in nodes}
            edges = [[a, b] for a in keep for b in graph.neighbors(a) if b in keep and a < b]
        return jsonify(me=me_id, nodes=nodes, edges=sorted(edges))

    @app.route("/api/profile", methods=["GET"])
    @login_required
    def get_profile():
        me_id = session["user_id"]
        profile = get_db().execute("SELECT * FROM profiles WHERE user_id = ?", (me_id,)).fetchone()
        return jsonify(
            user=public_user(S().user_by_id[me_id]),
            profile={"bio": profile["bio"], "major": profile["major"],
                     "year": profile["year"], "interests": profile["interests"]},
        )

    @app.route("/api/profile", methods=["PUT"])
    @login_required
    def update_profile():
        data = request.get_json(silent=True) or {}
        blocked, _ = moderate("profile bio and interests", clean(data, "bio", 500), clean(data, "interests", 300))
        if blocked:
            return blocked
        conn = get_db()
        conn.execute(
            "UPDATE profiles SET bio = ?, major = ?, year = ?, interests = ? WHERE user_id = ?",
            (clean(data, "bio", 500), clean(data, "major", 100), clean(data, "year", 30),
             clean(data, "interests", 300), session["user_id"]),
        )
        conn.commit()
        return jsonify(message="Profile updated.")

    # ---- Student search / friends ----------------------------------------

    def student_row(user, me_id):
        """public_user + relationship info derived from the friend Graph (BFS)."""
        graph = S().friend_graph
        dist = graph.distance(me_id, user["id"])
        return {**public_user(user),
                "is_friend": dist == 1,
                "distance": dist,
                "mutual_count": len(graph.mutual_friends(me_id, user["id"]))}

    @app.route("/api/students/search")
    @login_required
    def search_students():
        """Trie-backed prefix search: every word typed must prefix-match a name,
        college or email-handle word."""
        st = S()
        me_id = session["user_id"]
        query = (request.args.get("q") or "").strip()[:100]
        with st.lock:
            if query:
                ids = search_words(st.student_trie, query)
                ids.discard(me_id)
                users = sorted((st.user_by_id[i] for i in ids if i in st.user_by_id),
                               key=lambda u: u["full_name"].lower())[:20]
            else:
                users = sorted((u for i, u in st.user_by_id.items() if i != me_id),
                               key=lambda u: u["full_name"].lower())[:20]
            results = [student_row(u, me_id) for u in users]
        return jsonify(results=results)

    @app.route("/api/friends/suggestions")
    @login_required
    def friend_suggestions():
        """People you may know: BFS out to 3 hops, ranked by mutual friends."""
        st, me_id = S(), session["user_id"]
        with st.lock:
            ranked = st.friend_graph.suggestions(me_id, limit=int_arg("limit", 8, 1, 20))
            out = [{**public_user(st.user_by_id[uid]), "mutual_count": mutual, "distance": dist}
                   for uid, mutual, dist in ranked if uid in st.user_by_id]
        return jsonify(suggestions=out)

    @app.route("/api/friends/request", methods=["POST"])
    @login_required
    def send_friend_request():
        st, me_id = S(), session["user_id"]
        receiver_id = to_int((request.get_json(silent=True) or {}).get("receiver_id"))
        if receiver_id is None or receiver_id == me_id:
            return error("Invalid recipient.", 400)
        if receiver_id not in st.user_by_id:
            return error("Student not found.", 404)
        if st.friend_graph.are_friends(me_id, receiver_id):
            return error("You are already friends.", 409)

        conn = get_db()
        existing = conn.execute(
            """SELECT id, status, sender_id FROM friend_requests
               WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)""",
            (me_id, receiver_id, receiver_id, me_id),
        ).fetchone()
        if existing and existing["status"] == "pending":
            if existing["sender_id"] == receiver_id:
                return error("They already sent you a request — accept it from your requests list.", 409)
            return error("A friend request is already pending.", 409)
        if existing:
            conn.execute("UPDATE friend_requests SET status = 'pending', sender_id = ?, receiver_id = ? WHERE id = ?",
                         (me_id, receiver_id, existing["id"]))
        else:
            conn.execute("INSERT INTO friend_requests (sender_id, receiver_id, status) VALUES (?, ?, 'pending')",
                         (me_id, receiver_id))
        conn.commit()
        return jsonify(message="Friend request sent."), 201

    @app.route("/api/friends/requests")
    @login_required
    def list_friend_requests():
        me_id, conn = session["user_id"], get_db()
        incoming = conn.execute(
            """SELECT fr.id AS request_id, u.* FROM friend_requests fr
               JOIN users u ON u.id = fr.sender_id
               WHERE fr.receiver_id = ? AND fr.status = 'pending' ORDER BY fr.created_at""", (me_id,)).fetchall()
        outgoing = conn.execute(
            """SELECT fr.id AS request_id, u.* FROM friend_requests fr
               JOIN users u ON u.id = fr.receiver_id
               WHERE fr.sender_id = ? AND fr.status = 'pending' ORDER BY fr.created_at""", (me_id,)).fetchall()
        return jsonify(
            incoming=[{**public_user(r), "request_id": r["request_id"]} for r in incoming],
            outgoing=[{**public_user(r), "request_id": r["request_id"]} for r in outgoing],
        )

    @app.route("/api/friends/requests/<int:request_id>/respond", methods=["POST"])
    @login_required
    def respond_friend_request(request_id):
        action = (request.get_json(silent=True) or {}).get("action")
        if action not in ("accept", "reject"):
            return error("action must be 'accept' or 'reject'.", 400)

        me_id, conn = session["user_id"], get_db()
        req = conn.execute(
            "SELECT * FROM friend_requests WHERE id = ? AND receiver_id = ? AND status = 'pending'",
            (request_id, me_id)).fetchone()
        if req is None:
            return error("Request not found.", 404)

        new_status = "accepted" if action == "accept" else "rejected"
        conn.execute("UPDATE friend_requests SET status = ? WHERE id = ?", (new_status, request_id))
        if action == "accept":
            for a, b in ((req["sender_id"], req["receiver_id"]), (req["receiver_id"], req["sender_id"])):
                conn.execute("INSERT OR IGNORE INTO friendships (user_id, friend_id) VALUES (?, ?)", (a, b))
        conn.commit()
        if action == "accept":
            with S().lock:
                S().friend_graph.add_edge(req["sender_id"], req["receiver_id"])
        return jsonify(message=f"Request {new_status}.")

    @app.route("/api/friends/<int:other_id>/remove", methods=["POST"])
    @login_required
    def remove_friend(other_id):
        me_id, conn = session["user_id"], get_db()
        if not S().friend_graph.are_friends(me_id, other_id):
            return error("You are not friends with this student.", 404)
        conn.execute("DELETE FROM friendships WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
                     (me_id, other_id, other_id, me_id))
        conn.execute("DELETE FROM friend_requests WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)",
                     (me_id, other_id, other_id, me_id))
        conn.commit()
        with S().lock:
            S().friend_graph.remove_edge(me_id, other_id)
        return jsonify(message="Friend removed.")

    @app.route("/api/friends")
    @login_required
    def list_friends():
        st = S()
        with st.lock:
            friends = [st.user_by_id[i] for i in st.friend_graph.neighbors(session["user_id"]) if i in st.user_by_id]
        friends.sort(key=lambda u: u["full_name"].lower())
        return jsonify(friends=[public_user(u) for u in friends])

    @app.route("/api/friends/<int:other_id>/mutual")
    @login_required
    def mutual_friends(other_id):
        st = S()
        with st.lock:
            ids = st.friend_graph.mutual_friends(session["user_id"], other_id)
            users = [st.user_by_id[i] for i in ids if i in st.user_by_id]
        return jsonify(mutual=[public_user(u) for u in users])

    @app.route("/api/friends/<int:other_id>/path")
    @login_required
    def friend_path(other_id):
        """Shortest chain of friends between you and another student (BFS)."""
        st = S()
        if other_id not in st.user_by_id:
            return error("Student not found.", 404)
        with st.lock:
            path = st.friend_graph.shortest_path(session["user_id"], other_id)
            users = [public_user(st.user_by_id[i]) for i in path] if path else None
        return jsonify(path=users, degrees=None if path is None else len(path) - 1)

    # ---- Posts / feed -----------------------------------------------------

    def upload_dir():
        return os.path.join(os.path.dirname(app.config["DATABASE_PATH"]), "uploads")

    def verify_youtube(vid):
        """Education-only check on a YouTube video: its real title (from YouTube) must pass the same gate as text.
        Returns (meta_or_None, error_response_or_None). Skipped when CC_REEL_VERIFY=0 or education-only is off."""
        if not (app.config.get("EDUCATION_ONLY", True) and app.config.get("REEL_VERIFY", True)):
            return None, None
        try:
            meta = youtube.fetch_oembed(vid)
        except youtube.VideoUnavailable:
            return None, error("That video is private, removed or can't be embedded. Please pick another.", 422)
        except youtube.LookupFailed:
            return None, error("Couldn't check that video with YouTube right now. Please try again in a moment.", 503)
        blocked, _ = moderate("YouTube video title", meta["title"], check_links=False)
        return (None, blocked) if blocked else (meta, None)

    def store_image(raw_data_url, caption, me_id):
        """Validate, check and save an uploaded poster. Returns (file_name, error_response_or_None)."""
        try:
            raw, ext = images.decode(raw_data_url)
        except images.ImageError as exc:
            return "", error(str(exc), 400)
        verdict = moderation.check_image(app.config, S(), get_db(), user_id=me_id, caption=caption, data=raw, ext=ext)
        if not verdict.allowed:
            return "", error(verdict.reason, verdict.status, code=verdict.code, categories=verdict.categories)
        return images.save(upload_dir(), raw, ext), None

    @app.route("/api/uploads/<name>")
    @login_required
    def serve_upload(name):
        """Poster images. Only names this app generated are served, always with a fixed image type."""
        if not images.NAME_RE.match(name):
            return error("Not found.", 404)
        path = os.path.join(upload_dir(), name)
        if not os.path.isfile(path):
            return error("Not found.", 404)
        with open(path, "rb") as f:
            body = f.read()
        resp = app.response_class(body, mimetype=images.MIME[name.rsplit(".", 1)[1]])
        resp.headers["Cache-Control"] = "private, max-age=86400"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return resp

    @app.route("/api/posts", methods=["POST"])
    @login_required
    def create_post():
        st, me_id = S(), session["user_id"]
        data = request.get_json(silent=True) or {}
        content = clean(data, "content", 100000)
        group_id = data.get("group_id")
        if not content:
            return error("Post content cannot be empty.", 400)
        if len(content) > 2000:
            return error("Post is too long (max 2000 characters).", 400)

        conn = get_db()
        if group_id is not None:
            group_id = to_int(group_id)
            if group_id is None:
                return error("Invalid group.", 400)
            if conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone() is None:
                return error("Group not found.", 404)
            if not is_group_member(conn, group_id, me_id):
                return error("Join the group before posting in it.", 403)

        blocked, verdict = moderate("public post" if group_id is None else "study-group post", content, dedupe=True)
        if blocked:
            return blocked

        image_name, video_id, video_title = "", "", ""
        if data.get("image") and data.get("video"):
            return error("Attach either an image or a video, not both.", 400)
        if data.get("video"):
            parsed = parse_youtube(str(data.get("video")))
            if not parsed:
                return error("Please paste a YouTube link (youtube.com/watch?v=..., youtu.be/... or a Short).", 400)
            video_id = parsed[0]
            meta, err = verify_youtube(video_id)
            if err:
                return err
            video_title = (meta or {}).get("title", "")
        if data.get("image"):
            image_name, err = store_image(data.get("image"), content, me_id)
            if err:
                return err

        cursor = conn.execute("INSERT INTO posts (author_id, group_id, content, image, video, video_title) VALUES (?, ?, ?, ?, ?, ?)",
                              (me_id, group_id, content, image_name, video_id, video_title))
        post_id = cursor.lastrowid
        created_at = conn.execute("SELECT created_at FROM posts WHERE id = ?", (post_id,)).fetchone()["created_at"]
        conn.commit()

        post = {"id": post_id, "author_id": me_id, "author_name": st.user_by_id[me_id]["full_name"],
                "group_id": group_id, "content": content, "image": image_name, "video": video_id,
                "video_title": video_title, "likes": 0, "comment_count": 0,
                "created_at": created_at}
        with st.lock:
            add_post_to_caches(st, post)
        return jsonify(post=public_post(post, me_id), notice=verdict.notice), 201

    @app.route("/api/posts/<int:post_id>", methods=["DELETE"])
    @login_required
    def delete_post(post_id):
        st, me_id = S(), session["user_id"]
        post = st.post_store.get(post_id)
        if post is None:
            return error("Post not found.", 404)
        if post["author_id"] != me_id:
            return error("You can only delete your own posts.", 403)
        conn = get_db()
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))  # cascades to comments + likes
        conn.commit()
        images.remove(upload_dir(), post.get("image"))
        with st.lock:
            st.post_tree.delete(st.post_keys.pop(post_id))   # O(log n) AVL delete
            st.post_store.pop(post_id, None)
            st.comment_arrays.pop(post_id, None)
            st.post_likes.pop(post_id, None)
            st.post_saves.pop(post_id, None)
        return jsonify(message="Post deleted.")

    @app.route("/api/posts/feed")
    @login_required
    def feed():
        """Chronological feed straight off the AVL tree. The iterator is lazy,
        so only `limit` posts are visited, not the whole tree."""
        st, me_id = S(), session["user_id"]
        limit = int_arg("limit", 20, 1, 50)
        with st.lock:
            posts = list(islice(
                (st.post_store[pid] for pid in st.post_tree.iter_desc()
                 if st.post_store[pid]["group_id"] is None), limit))
            out = [public_post(p, me_id) for p in posts]
        return jsonify(posts=out)

    @app.route("/api/posts/trending")
    @login_required
    def trending():
        """Max-heap of engagement scores; pull off the top N."""
        st, me_id = S(), session["user_id"]
        limit = int_arg("limit", 10, 1, 50)
        with st.lock:
            scored = [(engagement_score(p), p["id"]) for p in st.post_store.values() if p["group_id"] is None]
            top_ids = MaxHeap.build(scored).top_k(limit)
            out = [public_post(st.post_store[pid], me_id) for pid in top_ids]
        return jsonify(posts=out)

    @app.route("/api/posts/<int:post_id>/like", methods=["POST"])
    @login_required
    def like_post(post_id):
        """Toggle: a student can like a post once, and un-like it again."""
        st, me_id = S(), session["user_id"]
        post = st.post_store.get(post_id)
        conn = get_db()
        if post is None or not can_see_post(conn, post, me_id):
            return error("Post not found.", 404)
        with st.lock:
            likers = st.post_likes.setdefault(post_id, set())
            if me_id in likers:
                likers.discard(me_id)
                conn.execute("DELETE FROM post_likes WHERE post_id = ? AND user_id = ?", (post_id, me_id))
            else:
                likers.add(me_id)
                conn.execute("INSERT OR IGNORE INTO post_likes (post_id, user_id) VALUES (?, ?)", (post_id, me_id))
            post["likes"] = len(likers)
            conn.execute("UPDATE posts SET likes = ? WHERE id = ?", (post["likes"], post_id))
            conn.commit()
            out = public_post(post, me_id)
        return jsonify(post=out)

    @app.route("/api/posts/<int:post_id>/save", methods=["POST"])
    @login_required
    def save_post(post_id):
        """Toggle a private bookmark on a post you can see."""
        st, me_id, conn = S(), session["user_id"], get_db()
        post = st.post_store.get(post_id)
        if post is None or not can_see_post(conn, post, me_id):
            return error("Post not found.", 404)
        with st.lock:
            savers = st.post_saves.setdefault(post_id, set())
            if me_id in savers:
                savers.discard(me_id)
                conn.execute("DELETE FROM post_saves WHERE post_id = ? AND user_id = ?", (post_id, me_id))
            else:
                savers.add(me_id)
                conn.execute("INSERT OR IGNORE INTO post_saves (post_id, user_id) VALUES (?, ?)", (post_id, me_id))
            conn.commit()
            out = public_post(post, me_id)
        return jsonify(post=out)

    @app.route("/api/posts/saved")
    @login_required
    def saved_posts():
        st, me_id, conn = S(), session["user_id"], get_db()
        with st.lock:
            out = [public_post(st.post_store[pid], me_id) for pid in st.post_tree.iter_desc()
                   if me_id in st.post_saves.get(pid, ()) and can_see_post(conn, st.post_store[pid], me_id)]
        return jsonify(posts=out)

    @app.route("/api/posts/<int:post_id>/comments", methods=["GET"])
    @login_required
    def list_comments(post_id):
        st = S()
        post = st.post_store.get(post_id)
        if post is None or not can_see_post(get_db(), post, session["user_id"]):
            return error("Post not found.", 404)
        return jsonify(comments=list(st.comment_arrays.get(post_id, [])))

    @app.route("/api/posts/<int:post_id>/comments", methods=["POST"])
    @login_required
    def add_comment(post_id):
        st, me_id = S(), session["user_id"]
        post = st.post_store.get(post_id)
        conn = get_db()
        if post is None or not can_see_post(conn, post, me_id):
            return error("Post not found.", 404)
        content = clean(request.get_json(silent=True) or {}, "content", 100000)
        if not content:
            return error("Comment cannot be empty.", 400)
        if len(content) > 500:
            return error("Comment is too long (max 500 characters).", 400)

        blocked, verdict = moderate("comment", content, context=post["content"] if "content" in post else "")
        if blocked:
            return blocked
        cursor = conn.execute("INSERT INTO comments (post_id, author_id, content) VALUES (?, ?, ?)",
                              (post_id, me_id, content))
        row = conn.execute("SELECT created_at FROM comments WHERE id = ?", (cursor.lastrowid,)).fetchone()
        conn.commit()
        comment = {"id": cursor.lastrowid, "author_id": me_id, "author_name": st.user_by_id[me_id]["full_name"],
                   "content": content, "created_at": row["created_at"]}
        with st.lock:
            st.comment_arrays.setdefault(post_id, []).append(comment)
            post["comment_count"] = len(st.comment_arrays[post_id])
        return jsonify(comment=comment, notice=verdict.notice), 201

    # ---- Groups ------------------------------------------------------------

    @app.route("/api/groups", methods=["GET"])
    @login_required
    def list_groups():
        """All groups, or (with ?q=) groups whose name/topic words match the
        query — found through the group Trie."""
        st, me_id, conn = S(), session["user_id"], get_db()
        rows = conn.execute(
            """SELECT g.*,
                      (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.id) AS member_count,
                      EXISTS(SELECT 1 FROM group_members gm WHERE gm.group_id = g.id AND gm.user_id = ?) AS is_member
               FROM groups g ORDER BY g.created_at DESC, g.id DESC""", (me_id,)).fetchall()
        query = (request.args.get("q") or "").strip()[:100]
        if query:
            with st.lock:
                ids = search_words(st.group_trie, query)
            rows = [r for r in rows if r["id"] in ids]
        return jsonify(groups=[public_group(r, r["member_count"], r["is_member"]) for r in rows])

    @app.route("/api/groups", methods=["POST"])
    @login_required
    def create_group():
        st, me_id, conn = S(), session["user_id"], get_db()
        data = request.get_json(silent=True) or {}
        name, topic = clean(data, "name", 80), clean(data, "topic", 120)
        if not name or not topic:
            return error("Group name and topic are required.", 400)
        blocked, _ = moderate("study group name and topic", name, topic)
        if blocked:
            return blocked
        cursor = conn.execute("INSERT INTO groups (name, topic, created_by) VALUES (?, ?, ?)", (name, topic, me_id))
        group_id = cursor.lastrowid
        conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, ?)", (group_id, me_id))
        conn.commit()
        with st.lock:
            index_group(st, group_id, name, topic)
        row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        return jsonify(group=public_group(row, 1, True)), 201

    @app.route("/api/groups/<int:group_id>/join", methods=["POST"])
    @login_required
    def join_group(group_id):
        conn = get_db()
        if conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone() is None:
            return error("Group not found.", 404)
        conn.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)",
                     (group_id, session["user_id"]))
        conn.commit()
        return jsonify(message="Joined group.")

    @app.route("/api/groups/<int:group_id>/leave", methods=["POST"])
    @login_required
    def leave_group(group_id):
        conn = get_db()
        conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, session["user_id"]))
        conn.commit()
        return jsonify(message="Left group.")

    @app.route("/api/groups/<int:group_id>")
    @login_required
    def get_group(group_id):
        me_id, conn = session["user_id"], get_db()
        row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        if row is None:
            return error("Group not found.", 404)
        count = conn.execute("SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?", (group_id,)).fetchone()["c"]
        return jsonify(group=public_group(row, count, is_group_member(conn, group_id, me_id)))

    @app.route("/api/groups/<int:group_id>/posts")
    @login_required
    def group_posts(group_id):
        st, me_id, conn = S(), session["user_id"], get_db()
        if conn.execute("SELECT 1 FROM groups WHERE id = ?", (group_id,)).fetchone() is None:
            return error("Group not found.", 404)
        if not is_group_member(conn, group_id, me_id):
            return error("Join this group to see its posts.", 403)
        with st.lock:
            out = [public_post(st.post_store[pid], me_id) for pid in st.post_tree.iter_desc()
                   if st.post_store[pid]["group_id"] == group_id]
        return jsonify(posts=out)

    # ---- Events -----------------------------------------------------------

    @app.route("/api/events", methods=["POST"])
    @login_required
    def create_event():
        data = request.get_json(silent=True) or {}
        title, event_date = clean(data, "title", 120), clean(data, "event_date", 10)
        if not title or not event_date:
            return error("Title and event date are required.", 400)
        try:
            datetime.strptime(event_date, "%Y-%m-%d")
        except ValueError:
            return error("event_date must be in YYYY-MM-DD format.", 400)

        blocked, _ = moderate("campus event", title, clean(data, "description", 1000))
        if blocked:
            return blocked
        me_id, conn = session["user_id"], get_db()
        image_name = ""
        if data.get("image"):
            image_name, err = store_image(data.get("image"), f"{title}. {clean(data, 'description', 1000)}", me_id)
            if err:
                return err
        cursor = conn.execute(
            "INSERT INTO events (title, description, college, event_date, created_by, image) VALUES (?, ?, ?, ?, ?, ?)",
            (title, clean(data, "description", 1000), S().user_by_id[me_id]["college"], event_date, me_id, image_name))
        conn.commit()
        row = conn.execute("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(event=public_event(row)), 201

    def public_event(row):
        d = dict(row)
        d["image_url"] = f"/api/uploads/{d['image']}" if d.get("image") else None
        d.pop("image", None)
        return d

    @app.route("/api/events")
    @login_required
    def list_events():
        """Upcoming events, soonest first (scope=college by default, or all)."""
        conn, today = get_db(), date.today().isoformat()
        if request.args.get("scope", "college") == "college":
            rows = conn.execute("SELECT * FROM events WHERE college = ? AND event_date >= ? ORDER BY event_date",
                                (S().user_by_id[session["user_id"]]["college"], today)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM events WHERE event_date >= ? ORDER BY event_date", (today,)).fetchall()
        return jsonify(events=[public_event(r) for r in rows])

    # ---- Resources & announcements ----------------------------------------

    @app.route("/api/resources", methods=["POST"])
    @login_required
    def create_resource():
        data = request.get_json(silent=True) or {}
        title, url = clean(data, "title", 150), clean(data, "url", 500)
        if not title or not url:
            return error("Title and URL are required.", 400)
        if not (url.startswith("http://") or url.startswith("https://")):
            return error("URL must start with http:// or https://", 400)
        if re.search(r"[\s\"'<>`\\]", url):
            return error("That link contains characters that aren't allowed (spaces, quotes or angle brackets).", 400)
        blocked, _ = moderate("shared study resource (title, description and link)", title,
                              clean(data, "description", 500), url)
        if blocked:
            return blocked
        conn = get_db()
        cursor = conn.execute("INSERT INTO resources (title, url, description, added_by) VALUES (?, ?, ?, ?)",
                              (title, url, clean(data, "description", 500), session["user_id"]))
        conn.commit()
        row = conn.execute("""SELECT r.*, u.full_name AS added_by_name FROM resources r
                              JOIN users u ON u.id = r.added_by WHERE r.id = ?""", (cursor.lastrowid,)).fetchone()
        return jsonify(resource=dict(row)), 201

    @app.route("/api/resources")
    @login_required
    def list_resources():
        rows = get_db().execute(
            """SELECT r.*, u.full_name AS added_by_name FROM resources r
               JOIN users u ON u.id = r.added_by ORDER BY r.created_at DESC, r.id DESC LIMIT 200""").fetchall()
        return jsonify(resources=[dict(r) for r in rows])

    @app.route("/api/announcements", methods=["POST"])
    @login_required
    def create_announcement():
        data = request.get_json(silent=True) or {}
        title, body = clean(data, "title", 120), clean(data, "body", 2000)
        if not title or not body:
            return error("Title and message are required.", 400)
        blocked, _ = moderate("college-wide announcement", title, body)
        if blocked:
            return blocked
        me_id, conn = session["user_id"], get_db()
        cursor = conn.execute(
            "INSERT INTO announcements (title, body, college, created_by) VALUES (?, ?, ?, ?)",
            (title, body, S().user_by_id[me_id]["college"], me_id))
        conn.commit()
        row = conn.execute("""SELECT a.*, u.full_name AS author_name FROM announcements a
                              JOIN users u ON u.id = a.created_by WHERE a.id = ?""", (cursor.lastrowid,)).fetchone()
        return jsonify(announcement=dict(row)), 201

    @app.route("/api/announcements")
    @login_required
    def list_announcements():
        """Announcements for your own college, newest first."""
        rows = get_db().execute(
            """SELECT a.*, u.full_name AS author_name FROM announcements a
               JOIN users u ON u.id = a.created_by WHERE a.college = ?
               ORDER BY a.created_at DESC, a.id DESC LIMIT 50""",
            (S().user_by_id[session["user_id"]]["college"],)).fetchall()
        return jsonify(announcements=[dict(r) for r in rows])

    # ---- Notifications ----------------------------------------------------

    @app.route("/api/notifications")
    @login_required
    def notifications():
        me_id, conn = session["user_id"], get_db()
        college = S().user_by_id[me_id]["college"]
        today = date.today()
        week_out = (today + timedelta(days=7)).isoformat()
        week_ago = (utc_now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

        incoming = conn.execute(
            """SELECT u.full_name FROM friend_requests fr JOIN users u ON u.id = fr.sender_id
               WHERE fr.receiver_id = ? AND fr.status = 'pending'""", (me_id,)).fetchall()
        events = conn.execute(
            "SELECT title, event_date FROM events WHERE college = ? AND event_date BETWEEN ? AND ? ORDER BY event_date",
            (college, today.isoformat(), week_out)).fetchall()
        news = conn.execute(
            "SELECT title FROM announcements WHERE college = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 10",
            (college, week_ago)).fetchall()

        with S().lock:
            unread_msgs = sum(n for (receiver, _s), n in S().dm_unread.items() if receiver == me_id)
        items = ([{"type": "message", "message": f"You have {unread_msgs} unread message{'' if unread_msgs == 1 else 's'}."}] if unread_msgs else [])
        items += ([{"type": "friend_request", "message": f"{r['full_name']} sent you a friend request."} for r in incoming]
                 + [{"type": "event", "message": f"{e['title']} is coming up on {e['event_date']}."} for e in events]
                 + [{"type": "announcement", "message": f"New announcement: {a['title']}"} for a in news])
        return jsonify(count=len(items), items=items)

    # ---- Chat (1:1 messages between friends) ----------------------------------
    # Each conversation is an array in st.dm_threads (O(1) append, in order), unread
    # counters live in a hash map, and SQLite stays the source of truth.

    def public_message(msg, me_id):
        return {"id": msg["id"], "mine": msg["sender_id"] == me_id, "content": msg["content"],
                "created_at": msg["created_at"], "read": msg["read"]}

    def unread_total(st, me_id):
        return sum(n for (receiver, _sender), n in st.dm_unread.items() if receiver == me_id)

    @app.route("/api/chat/conversations")
    @login_required
    def chat_conversations():
        st, me_id = S(), session["user_id"]
        with st.lock:
            friends = [st.user_by_id[i] for i in st.friend_graph.neighbors(me_id) if i in st.user_by_id]
            rows = []
            for u in friends:
                thread = st.dm_threads.get(thread_key(me_id, u["id"]), [])
                last = thread[-1] if thread else None
                rows.append({**public_user(u),
                             "unread": st.dm_unread.get((me_id, u["id"]), 0),
                             "last_message": ({"content": last["content"][:80], "mine": last["sender_id"] == me_id,
                                               "created_at": last["created_at"]} if last else None),
                             "_order": last["id"] if last else 0})
            total = unread_total(st, me_id)
        # Most recent conversation first, then friends you have not written to, A-Z.
        rows.sort(key=lambda r: (-r["_order"], r["full_name"].lower()))
        for r in rows:
            r.pop("_order")
        return jsonify(conversations=rows, unread_total=total)

    @app.route("/api/chat/unread")
    @login_required
    def chat_unread():
        st = S()
        with st.lock:
            return jsonify(unread=unread_total(st, session["user_id"]))

    @app.route("/api/chat/<int:other_id>")
    @login_required
    def chat_thread(other_id):
        """Messages with one friend. `?after=<id>` returns only newer ones (used for polling).
        Opening a thread marks the other person's messages as read."""
        st, me_id = S(), session["user_id"]
        if other_id not in st.user_by_id or other_id == me_id:
            return error("Student not found.", 404)
        after = int_arg("after", 0, 0, 2**62)
        with st.lock:
            if not st.friend_graph.are_friends(me_id, other_id):
                return error("You can only chat with your friends.", 403)
            thread = st.dm_threads.get(thread_key(me_id, other_id), [])
            if after:
                fresh = [m for m in thread if m["id"] > after]
            else:
                fresh = thread[-200:]
            mark = [m for m in fresh if m["receiver_id"] == me_id and not m["read"]]
            for m in mark:
                m["read"] = True
            if mark:
                st.dm_unread[(me_id, other_id)] = 0
            # Read receipts: tell the sender about older messages the other side has since read.
            read_upto = max((m["id"] for m in thread if m["sender_id"] == me_id and m["read"]), default=0)
            out = [public_message(m, me_id) for m in fresh]
        if mark:
            conn = get_db()
            conn.execute("UPDATE messages SET read_at = datetime('now') WHERE sender_id = ? AND receiver_id = ? AND read_at IS NULL",
                         (other_id, me_id))
            conn.commit()
        return jsonify(messages=out, read_upto=read_upto, other=public_user(st.user_by_id[other_id]))

    @app.route("/api/chat/<int:other_id>", methods=["POST"])
    @login_required
    def chat_send(other_id):
        st, me_id = S(), session["user_id"]
        if other_id not in st.user_by_id or other_id == me_id:
            return error("Student not found.", 404)
        if not st.friend_graph.are_friends(me_id, other_id):
            return error("You can only chat with your friends.", 403)
        content = clean(request.get_json(silent=True) or {}, "content", 100000)
        if not content:
            return error("Message cannot be empty.", 400)
        limit = app.config["CHAT_MAX_LENGTH"]
        if len(content) > limit:
            return error(f"Message is too long (max {limit} characters).", 400)

        now = time.time()
        with st.lock:
            times = [t for t in st.dm_times.get(me_id, []) if now - t < 60]
            if len(times) >= app.config["CHAT_MESSAGES_PER_MINUTE"]:
                st.dm_times[me_id] = times
                return error("You're sending messages very fast. Wait a moment and try again.", 429)
            times.append(now)
            st.dm_times[me_id] = times

        conn = get_db()
        # Same safety checks as posts; the education-only rule is a separate switch for chat.
        cfg = dict(app.config)
        cfg["EDUCATION_ONLY"] = app.config["CHAT_EDUCATION_ONLY"]
        verdict = moderation.check(cfg, st, conn, kind="message", text=content, user_id=me_id)
        if not verdict.allowed:
            return error(verdict.reason, verdict.status, code=verdict.code, categories=verdict.categories)

        with st.lock:
            if not st.friend_graph.are_friends(me_id, other_id):   # unfriended while we were checking
                return error("You can only chat with your friends.", 403)
            cursor = conn.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
                                  (me_id, other_id, content))
            row = conn.execute("SELECT created_at FROM messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
            conn.commit()
            msg = {"id": cursor.lastrowid, "sender_id": me_id, "receiver_id": other_id, "content": content,
                   "created_at": row["created_at"], "read": False}
            st.dm_threads.setdefault(thread_key(me_id, other_id), []).append(msg)
            k = (other_id, me_id)
            st.dm_unread[k] = st.dm_unread.get(k, 0) + 1
        return jsonify(message=public_message(msg, me_id), notice=verdict.notice), 201

    # ---- Reels ------------------------------------------------------------

    REEL_SQL = """SELECT r.*, u.full_name AS added_by_name,
                      (SELECT COUNT(*) FROM reel_likes l WHERE l.reel_id = r.id) AS likes,
                      (SELECT COUNT(*) FROM reel_comments c WHERE c.reel_id = r.id) AS comment_count,
                      EXISTS(SELECT 1 FROM reel_likes l WHERE l.reel_id = r.id AND l.user_id = ?) AS liked
               FROM reels r LEFT JOIN users u ON u.id = r.created_by"""

    def public_reel(row, me_id):
        return {
            "id": row["id"], "kind": row["kind"], "media": row["media"], "media_ref": row["media_ref"],
            "start": row["start_seconds"], "title": row["title"], "description": row["description"],
            "topic": row["topic"], "license": row["license"], "credit": row["credit"],
            "source_url": row["source_url"], "code_ref": row["code_ref"], "likes": row["likes"],
            "liked": bool(row["liked"]), "comment_count": row["comment_count"], "can_delete": row["kind"] == "community" and row["created_by"] == me_id,
            "added_by": row["added_by_name"] if row["kind"] == "community" else None,
            "created_at": row["created_at"],
        }

    @app.route("/api/reels")
    @login_required
    def list_reels():
        """?kind=all|prebuilt|open|community  ?topic=...  ?sort=curated|top|new"""
        me_id, conn = session["user_id"], get_db()
        kind, topic, sort = request.args.get("kind", "all"), request.args.get("topic", ""), request.args.get("sort", "curated")
        where, args = [], [me_id]
        if kind in ("prebuilt", "open", "community"):
            where.append("r.kind = ?"); args.append(kind)
        if topic in reels_seed.TOPICS:
            where.append("r.topic = ?"); args.append(topic)
        sql = REEL_SQL + (" WHERE " + " AND ".join(where) if where else "")
        rows = conn.execute(sql, args).fetchall()
        if sort == "top":      # max-heap on (likes, newest first): the same structure as trending posts
            heap = MaxHeap.build(((r["likes"], r["id"]), r) for r in rows)
            rows = heap.top_k(len(rows))
        elif sort == "new":
            rows = sorted(rows, key=lambda r: r["id"], reverse=True)
        else:
            rank = {"prebuilt": 0, "open": 1, "community": 2}
            rows = sorted(rows, key=lambda r: (rank[r["kind"]], r["id"] if r["kind"] != "community" else -r["id"]))
        return jsonify(reels=[public_reel(r, me_id) for r in rows], topics=reels_seed.TOPICS)

    @app.route("/api/reels", methods=["POST"])
    @login_required
    def create_reel():
        """A student shares a YouTube video. Only the video id is stored; it's embedded, never copied."""
        me_id, conn = session["user_id"], get_db()
        data = request.get_json(silent=True) or {}
        parsed = parse_youtube(str(data.get("url") or ""))
        if not parsed:
            return error("Please paste a YouTube link (youtube.com/watch?v=..., youtu.be/... or a Short).", 400)
        vid, start = parsed
        title, description = clean(data, "title", 100), clean(data, "description", 300)
        topic = clean(data, "topic", 40)
        if not title:
            return error("Give your reel a title.", 400)
        if topic not in reels_seed.TOPICS:
            topic = "Other"
        recent = conn.execute("SELECT COUNT(*) AS c FROM reels WHERE created_by = ? AND created_at >= datetime('now', '-1 day')",
                              (me_id,)).fetchone()["c"]
        if recent >= 5:
            return error("You've shared 5 reels today — come back tomorrow!", 429)
        if conn.execute("SELECT 1 FROM reels WHERE media_ref = ? AND kind IN ('community', 'open')", (vid,)).fetchone():
            return error("That video is already in Reels.", 409)
        blocked, verdict = moderate("shared video (title and description)", title, description)
        if blocked:
            return blocked
        credit = "Shared by a student"
        meta, err = verify_youtube(vid)       # judge the video's real YouTube title, not only what the student typed
        if err:
            return err
        if meta and meta["author"]:
            credit = f"{meta['author']} (shared by a student)"
        cursor = conn.execute(
            """INSERT INTO reels (kind, media, media_ref, start_seconds, title, description, topic, license, credit, source_url, created_by)
               VALUES ('community', 'youtube', ?, ?, ?, ?, ?, 'Check the video page for its licence', ?, ?, ?)""",
            (vid, start, title, description, topic, credit, f"https://www.youtube.com/watch?v={vid}", me_id))
        conn.commit()
        row = conn.execute(REEL_SQL + " WHERE r.id = ?", (me_id, cursor.lastrowid)).fetchone()
        return jsonify(reel=public_reel(row, me_id), notice=verdict.notice), 201

    @app.route("/api/reels/<int:reel_id>", methods=["DELETE"])
    @login_required
    def delete_reel(reel_id):
        me_id, conn = session["user_id"], get_db()
        row = conn.execute("SELECT kind, created_by FROM reels WHERE id = ?", (reel_id,)).fetchone()
        if row is None:
            return error("Reel not found.", 404)
        if row["kind"] != "community" or row["created_by"] != me_id:
            return error("You can only delete reels you shared.", 403)
        conn.execute("DELETE FROM reels WHERE id = ?", (reel_id,))
        conn.commit()
        return jsonify(message="Reel deleted.")

    @app.route("/api/reels/<int:reel_id>/like", methods=["POST"])
    @login_required
    def like_reel(reel_id):
        """Toggle your like on a reel."""
        me_id, conn = session["user_id"], get_db()
        if conn.execute("SELECT 1 FROM reels WHERE id = ?", (reel_id,)).fetchone() is None:
            return error("Reel not found.", 404)
        if conn.execute("SELECT 1 FROM reel_likes WHERE reel_id = ? AND user_id = ?", (reel_id, me_id)).fetchone():
            conn.execute("DELETE FROM reel_likes WHERE reel_id = ? AND user_id = ?", (reel_id, me_id))
        else:
            conn.execute("INSERT INTO reel_likes (reel_id, user_id) VALUES (?, ?)", (reel_id, me_id))
        conn.commit()
        row = conn.execute(REEL_SQL + " WHERE r.id = ?", (me_id, reel_id)).fetchone()
        return jsonify(reel=public_reel(row, me_id))

    def public_reel_comment(row, me_id):
        return {"id": row["id"], "author_id": row["author_id"], "author_name": row["author_name"],
                "content": row["content"], "created_at": row["created_at"], "can_delete": row["author_id"] == me_id}

    @app.route("/api/reels/<int:reel_id>/comments")
    @login_required
    def list_reel_comments(reel_id):
        me_id, conn = session["user_id"], get_db()
        if conn.execute("SELECT 1 FROM reels WHERE id = ?", (reel_id,)).fetchone() is None:
            return error("Reel not found.", 404)
        rows = conn.execute("""SELECT c.*, u.full_name AS author_name FROM reel_comments c
                               JOIN users u ON u.id = c.author_id WHERE c.reel_id = ? ORDER BY c.id""", (reel_id,)).fetchall()
        return jsonify(comments=[public_reel_comment(r, me_id) for r in rows])

    @app.route("/api/reels/<int:reel_id>/comments", methods=["POST"])
    @login_required
    def add_reel_comment(reel_id):
        """Comment on a reel. Same safety + education-only checks as posts; the reel gives the context."""
        me_id, conn = session["user_id"], get_db()
        reel = conn.execute("SELECT title, description FROM reels WHERE id = ?", (reel_id,)).fetchone()
        if reel is None:
            return error("Reel not found.", 404)
        content = clean(request.get_json(silent=True) or {}, "content", 100000)
        if not content:
            return error("Comment cannot be empty.", 400)
        if len(content) > 500:
            return error("Comment is too long (max 500 characters).", 400)
        blocked, verdict = moderate("reel comment", content, context=f"{reel['title']}. {reel['description']}")
        if blocked:
            return blocked
        cur = conn.execute("INSERT INTO reel_comments (reel_id, author_id, content) VALUES (?, ?, ?)", (reel_id, me_id, content))
        conn.commit()
        row = conn.execute("""SELECT c.*, u.full_name AS author_name FROM reel_comments c
                              JOIN users u ON u.id = c.author_id WHERE c.id = ?""", (cur.lastrowid,)).fetchone()
        count = conn.execute("SELECT COUNT(*) AS c FROM reel_comments WHERE reel_id = ?", (reel_id,)).fetchone()["c"]
        return jsonify(comment=public_reel_comment(row, me_id), comment_count=count, notice=verdict.notice), 201

    @app.route("/api/reels/<int:reel_id>/comments/<int:comment_id>", methods=["DELETE"])
    @login_required
    def delete_reel_comment(reel_id, comment_id):
        me_id, conn = session["user_id"], get_db()
        row = conn.execute("SELECT author_id FROM reel_comments WHERE id = ? AND reel_id = ?", (comment_id, reel_id)).fetchone()
        if row is None:
            return error("Comment not found.", 404)
        if row["author_id"] != me_id:
            return error("You can only delete your own comments.", 403)
        conn.execute("DELETE FROM reel_comments WHERE id = ?", (comment_id,))
        conn.commit()
        count = conn.execute("SELECT COUNT(*) AS c FROM reel_comments WHERE reel_id = ?", (reel_id,)).fetchone()["c"]
        return jsonify(message="Comment deleted.", comment_count=count)

    @app.route("/api/reference")
    @login_required
    def reference_library():
        """Static, curated reading list (open textbooks, free courses, docs, related papers)."""
        return jsonify(items=reels_seed.REFERENCES)

    # ---- Pet chatbot ------------------------------------------------------

    @app.route("/api/pet/config")
    def pet_config():
        """Public: lets the widget show the pet's name and whether AI chat is on."""
        from ai import gemini
        return jsonify(name=app.config["PET_NAME"], ai=gemini.is_configured(app.config),
                       moderation=bool(app.config["MODERATION_ENABLED"]))

    @app.route("/api/pet/chat", methods=["POST"])
    @login_required
    def pet_chat():
        st, me_id = S(), session["user_id"]
        data = request.get_json(silent=True) or {}
        message = str(data.get("message") or "").strip()
        if not message:
            return error("Say something and I'll answer!", 400)
        if len(message) > pet.MAX_MESSAGE:
            return error(f"Please keep it under {pet.MAX_MESSAGE} characters.", 400)

        now, window = time.time(), 60
        with st.lock:
            times = [t for t in st.chat_times.get(me_id, []) if now - t < window]
            if len(times) >= app.config["PET_CHATS_PER_MINUTE"]:
                st.chat_times[me_id] = times
                return error("Whoa, slow down — let me catch my breath for a minute.", 429)
            times.append(now)
            st.chat_times[me_id] = times

        result = pet.chat(app.config, message=message, history=data.get("history"),
                          view=str(data.get("view") or ""), user_name=st.user_by_id[me_id]["full_name"])
        return jsonify(reply=result["reply"], goto=result["goto"], source=result["source"], name=app.config["PET_NAME"])

    # ---- Frontend ---------------------------------------------------------

    @app.route("/")
    def index():
        return app.send_static_file("index.html")


app = create_app()
