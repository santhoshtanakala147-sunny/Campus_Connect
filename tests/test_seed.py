"""The demo-data script must be repeatable, reversible, and compatible with the app's caches."""
import os
import sqlite3
import sys

from conftest import Client, login, signup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import seed_demo  # noqa: E402


def test_seed_adds_network_and_can_be_reset(make_app, tmp_path):
    db = str(tmp_path / "seed.db")
    first = Client(make_app(DATABASE_PATH=db))
    signup(first, "Sunny Real", "sunny@college.edu", "BMS")

    conn = seed_demo.connect(db)
    seed_demo.seed(conn)
    seed_demo.seed(conn)                                   # second run is a no-op, not a duplicate
    assert conn.execute("SELECT COUNT(*) FROM demo_users").fetchone()[0] == len(seed_demo.STUDENTS)
    conn.close()

    app = make_app(DATABASE_PATH=db)                       # fresh app: caches rebuild from SQLite
    c = Client(app)
    c.id = login(c, "sunny@college.edu")
    net = c.get("/api/network").json
    levels = [n["level"] for n in net["nodes"]]
    assert levels.count(1) == len(seed_demo.DIRECT) and levels.count(2) > 0
    assert len(c.get("/api/posts/feed").json["posts"]) > 5
    assert len(c.get("/api/events?scope=college").json["events"]) >= 3          # copied to the real account's college
    assert len(c.get("/api/events?scope=all").json["events"]) >= len(seed_demo.EVENTS)
    assert c.get("/api/friends/suggestions").json["suggestions"]

    conn = seed_demo.connect(db)
    seed_demo.reset(conn)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0
    conn.close()


def seed_texts():
    for p in seed_demo.POSTS:
        yield p[2]
        for _, t in p[5]:
            yield t
    for e in seed_demo.EVENTS:
        yield e[0] + ". " + e[1]
    for a in seed_demo.ANNOUNCEMENTS:
        yield a[0] + ". " + a[1]
    for r in seed_demo.RESOURCES:
        yield r[0] + ". " + r[2]
    for _, _, t in seed_demo.REEL_COMMENTS:
        yield t


def test_sample_content_is_all_educational():
    """The demo must obey the site's own rule: nothing off-topic."""
    from ai import education
    bad = [t for t in seed_texts() if education.assess(t).label == "off"]
    assert bad == []


def test_seed_has_video_posts_and_reel_comments(make_app, tmp_path):
    db = str(tmp_path / "seed2.db")
    app = make_app(DATABASE_PATH=db)
    c = Client(app)
    signup(c, "Sunny Real", "sunny@college.edu", "BMS")
    conn = seed_demo.connect(db)
    seed_demo.seed(conn); conn.close()
    app = make_app(DATABASE_PATH=db)
    c = Client(app); login(c, "sunny@college.edu")
    posts = c.get("/api/posts/feed").json["posts"]
    vids = [p for p in posts if p["video"]]
    assert len(vids) >= 4 and all(len(p["video"]["id"]) == 11 and p["video"]["title"] for p in vids)
    reels = {r["media_ref"]: r for r in c.get("/api/reels?kind=open").json["reels"]}
    assert reels["s-CYnVz-uh4"]["comment_count"] == 2
    assert len(c.get("/api/reels/%d/comments" % reels["s-CYnVz-uh4"]["id"]).json["comments"]) == 2
    assert len(c.get("/api/groups").json["groups"]) == len(seed_demo.GROUPS) >= 8
