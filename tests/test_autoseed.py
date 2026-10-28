"""Sample classmates appear by themselves: no manual script run needed."""
import sqlite3

import seed_demo
from conftest import Client, login, signup


def test_fresh_install_has_content_for_any_college(make_app):
    app = make_app(DEMO_DATA=True)
    c = Client(app)
    signup(c, "New Student", "new@college.edu", college="Some Other College")
    login(c, "new@college.edu")
    assert c.get("/api/dashboard").json["friend_count"] == len(seed_demo.DIRECT)
    assert len(c.get("/api/friends").json["friends"]) == len(seed_demo.DIRECT)
    assert len(c.get("/api/posts/feed").json["posts"]) >= 15
    assert any(p["video"] for p in c.get("/api/posts/feed?limit=50").json["posts"])
    assert len(c.get("/api/groups").json["groups"]) == len(seed_demo.GROUPS)
    assert len(c.get("/api/events").json["events"]) >= 3                                # copied to this student's college
    assert len(c.get("/api/events?scope=all").json["events"]) > len(c.get("/api/events").json["events"])
    assert len(c.get("/api/announcements").json["announcements"]) >= 1
    assert c.get("/api/friends/suggestions").json["suggestions"]
    assert c.get("/api/network").json["edges"]


def test_account_created_before_seeding_is_introduced_at_login(make_app, tmp_path):
    db = str(tmp_path / "pre.db")
    old = Client(make_app(DATABASE_PATH=db))
    signup(old, "Old Timer", "old@college.edu", college="BMS")
    app = make_app(DATABASE_PATH=db, DEMO_DATA=True)             # restart with sample data switched on
    c = Client(app)
    login(c, "old@college.edu")
    assert c.get("/api/dashboard").json["friend_count"] == len(seed_demo.DIRECT)
    c.post("/api/auth/logout"); login(c, "old@college.edu")      # only once
    assert c.get("/api/dashboard").json["friend_count"] == len(seed_demo.DIRECT)


def test_reset_stays_reset_and_switch_off(make_app, tmp_path):
    db = str(tmp_path / "r.db")
    make_app(DATABASE_PATH=db, DEMO_DATA=True)
    conn = seed_demo.connect(db); seed_demo.reset(conn); conn.close()
    app = make_app(DATABASE_PATH=db, DEMO_DATA=True)             # not re-added
    c = Client(app); signup(c, "A B", "ab@college.edu"); login(c, "ab@college.edu")
    assert c.get("/api/dashboard").json["friend_count"] == 0 and c.get("/api/posts/feed").json["posts"] == []
    off = make_app(DATABASE_PATH=str(tmp_path / "off.db"))        # DEMO_DATA False by default in tests
    d = Client(off); signup(d, "C D", "cd@college.edu"); login(d, "cd@college.edu")
    assert d.get("/api/posts/feed").json["posts"] == []


def test_classmates_come_from_many_colleges(make_app):
    app = make_app(DEMO_DATA=True)
    c = Client(app); signup(c, "New S", "ns@college.edu", college="Some College"); login(c, "ns@college.edu")
    colleges = {f["college"] for f in c.get("/api/friends").json["friends"]}
    assert len(colleges) >= 3                                       # the five introduced classmates are from different colleges
    conn = seed_demo.connect(app.config["DATABASE_PATH"])
    names = {r[0] for r in conn.execute("SELECT DISTINCT college FROM users WHERE id IN (SELECT user_id FROM demo_users)")}
    assert {"Amrita Vishwa Vidyapeetham", "SRM Institute of Science and Technology", "Vellore Institute of Technology",
            "IIT Madras", "IIT Bombay", "BITS Pilani"} <= names
    # each college shows its own sample events
    ev = c.get("/api/events?scope=all").json["events"]
    assert {"Amrita Vishwa Vidyapeetham", "SRM Institute of Science and Technology", "IIT Madras"} <= {e["college"] for e in ev}


def test_sample_emails_use_the_colleges_own_domain(make_app):
    app = make_app(DEMO_DATA=True)
    c = Client(app); signup(c, "New S", "ns@college.edu", college="Some College"); login(c, "ns@college.edu")
    for f in c.get("/api/friends").json["friends"]:
        domain = seed_demo.COLLEGE_DOMAIN[f["college"]]
        assert f["email"].endswith("@" + domain) and "demo" not in f["email"], f
    assert "aarav.menon@amrita.edu" in {f["email"] for f in c.get("/api/friends").json["friends"]}
    # nobody can log in as a sample student
    assert c.post("/api/auth/login", email="aarav.menon@amrita.edu", password="password1").status_code == 401


def test_old_style_sample_accounts_are_upgraded(make_app, tmp_path):
    db = str(tmp_path / "old.db")
    make_app(DATABASE_PATH=db, DEMO_DATA=True)
    conn = seed_demo.connect(db)                      # pretend this database came from the earlier version
    conn.execute("UPDATE users SET email = lower(replace(full_name, ' ', '.')) || '@demo.campusconnect.edu', college = 'BMS' "
                 "WHERE id IN (SELECT user_id FROM demo_users)")
    conn.execute("DROP TABLE demo_users"); conn.commit(); conn.close()
    app = make_app(DATABASE_PATH=db, DEMO_DATA=True)
    conn = seed_demo.connect(db)
    rows = conn.execute("SELECT email, college FROM users WHERE id IN (SELECT user_id FROM demo_users)").fetchall()
    assert len(rows) == len(seed_demo.STUDENTS) and not any("demo.campusconnect" in r["email"] for r in rows)
    assert len({r["college"] for r in rows}) == len(set(seed_demo.COLLEGE_OF))
