import re

from conftest import Client, login, signup


# ------------------------------------------------------------------ auth
def test_register_login_and_domain_rules(client):
    signup(client, "A B", "a@college.edu")
    assert client.post("/api/auth/register", full_name="x", email="a@COLLEGE.edu", college="c",
                       password="password1", confirm_password="password1").status_code == 409
    for bad in ("x@gmail.com", "x@evil.edu.evil.com", "x@fakeedu.in", "nope", "a@b@c.edu"):
        r = client.post("/api/auth/register", full_name="x", email=bad, college="c",
                        password="password1", confirm_password="password1")
        assert r.status_code == 400, bad
    assert client.post("/api/auth/login", email="a@college.edu", password="wrong").status_code == 401
    login(client, "A@college.edu")
    assert client.get("/api/auth/me").json["full_name"] == "A B"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit(client):
    signup(client, "A B", "a@college.edu")
    codes = [client.post("/api/auth/login", email="a@college.edu", password="bad").status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    # even the right password is blocked while throttled
    assert client.post("/api/auth/login", email="a@college.edu", password="password1").status_code == 429


def test_email_verification_flow(make_app, capsys):
    app = make_app(REQUIRE_EMAIL_VERIFICATION=True)
    c = Client(app)
    assert signup(c, "A B", "a@college.edu").json["verification_required"] is True
    r = c.post("/api/auth/login", email="a@college.edu", password="password1")
    assert r.status_code == 403 and r.json["code"] == "unverified"

    link = re.search(r"http://localhost/(api/auth/verify\?token=\S+)", capsys.readouterr().out).group(1)
    assert c.get("/api/auth/verify?token=garbage").status_code == 400
    assert c.get("/" + link).status_code == 200
    assert c.get("/" + link).status_code == 400            # single use
    login(c, "a@college.edu")


def test_json_required_for_writes(client):
    r = client.c.post("/api/auth/logout", data="x=1", content_type="application/x-www-form-urlencoded")
    assert r.status_code == 415


# --------------------------------------------------------------- friends
def test_friend_flow_search_and_suggestions(users):
    a, b, c = users["alice"], users["bob"], users["carol"]
    res = a.get("/api/students/search?q=bo").json["results"]
    assert [r["full_name"] for r in res] == ["Bob Brown"] and res[0]["distance"] is None
    assert [r["full_name"] for r in a.get("/api/students/search?q=bob br").json["results"]] == ["Bob Brown"]
    assert [r["full_name"] for r in a.get("/api/students/search?q=other").json["results"]] == ["Carol Chen"]

    assert a.post("/api/friends/request", receiver_id="x").status_code == 400      # used to 500
    assert a.post("/api/friends/request", receiver_id=a.id).status_code == 400
    assert a.post("/api/friends/request", receiver_id=999).status_code == 404
    assert a.post("/api/friends/request", receiver_id=b.id).status_code == 201
    assert a.post("/api/friends/request", receiver_id=b.id).status_code == 409
    assert b.post("/api/friends/request", receiver_id=a.id).status_code == 409
    req = b.get("/api/friends/requests").json["incoming"][0]
    assert b.post(f"/api/friends/requests/{req['request_id']}/respond", action="accept").status_code == 200

    # bob -- carol, so alice should be offered carol (2 hops, 1 mutual)
    c.post("/api/friends/request", receiver_id=b.id)
    req = b.get("/api/friends/requests").json["incoming"][0]
    b.post(f"/api/friends/requests/{req['request_id']}/respond", action="accept")
    sug = a.get("/api/friends/suggestions").json["suggestions"]
    assert [(s["full_name"], s["mutual_count"], s["distance"]) for s in sug] == [("Carol Chen", 1, 2)]
    path = a.get(f"/api/friends/{c.id}/path").json
    assert path["degrees"] == 2 and [p["full_name"] for p in path["path"]] == ["Alice Archer", "Bob Brown", "Carol Chen"]
    assert [m["full_name"] for m in a.get(f"/api/friends/{c.id}/mutual").json["mutual"]] == ["Bob Brown"]

    assert a.post(f"/api/friends/{b.id}/remove").status_code == 200
    assert a.get("/api/friends").json["friends"] == []
    assert a.post("/api/friends/request", receiver_id=b.id).status_code == 201     # can re-add


# ----------------------------------------------------------------- posts
def test_posts_feed_likes_comments_delete(users):
    a, b = users["alice"], users["bob"]
    p1 = a.post("/api/posts", content="first").json["post"]
    p2 = b.post("/api/posts", content="second").json["post"]
    assert a.post("/api/posts", content="  ").status_code == 400
    assert a.post("/api/posts", content="x" * 2001).status_code == 400

    assert [p["id"] for p in a.get("/api/posts/feed").json["posts"]] == [p2["id"], p1["id"]]
    assert a.get("/api/posts/feed?limit=abc").status_code == 200                    # used to 500
    assert len(a.get("/api/posts/feed?limit=1").json["posts"]) == 1

    r = a.post(f"/api/posts/{p1['id']}/like").json["post"]
    assert r["likes"] == 1 and r["liked"] is True
    r = b.post(f"/api/posts/{p1['id']}/like").json["post"]
    assert r["likes"] == 2
    r = a.post(f"/api/posts/{p1['id']}/like").json["post"]        # toggle off — no double likes
    assert r["likes"] == 1 and r["liked"] is False

    cm = b.post(f"/api/posts/{p2['id']}/comments", content="nice").json["comment"]
    assert cm["author_name"] == "Bob Brown"
    assert a.get(f"/api/posts/{p2['id']}/comments").json["comments"][0]["content"] == "nice"

    # trending: p2 has 2 points (one comment), p1 has 1 like
    assert [p["id"] for p in a.get("/api/posts/trending").json["posts"]] == [p2["id"], p1["id"]]

    assert a.delete(f"/api/posts/{p2['id']}").status_code == 403
    assert a.get("/api/posts/feed").json["posts"][0]["can_delete"] is False
    assert b.delete(f"/api/posts/{p2['id']}").status_code == 200
    assert [p["id"] for p in a.get("/api/posts/feed").json["posts"]] == [p1["id"]]
    assert a.get(f"/api/posts/{p2['id']}/comments").status_code == 404


def test_state_survives_restart(make_app, users, app):
    a = users["alice"]
    pid = a.post("/api/posts", content="persist me").json["post"]["id"]
    a.post(f"/api/posts/{pid}/like")
    a.post(f"/api/posts/{pid}/comments", content="c1")
    a.post("/api/groups", name="Data Structures", topic="Trees and graphs")
    # boot a second app on the same database file — caches are rebuilt from SQLite
    app2 = make_app(DATABASE_PATH=app.config["DATABASE_PATH"])
    c2 = Client(app2)
    login(c2, "alice@college.edu")
    post = c2.get("/api/posts/feed").json["posts"][0]
    assert (post["content"], post["likes"], post["liked"], post["comment_count"]) == ("persist me", 1, True, 1)
    assert [g["name"] for g in c2.get("/api/groups?q=graph").json["groups"]] == ["Data Structures"]


# ---------------------------------------------------------------- groups
def test_groups_privacy_and_topic_search(users):
    a, b = users["alice"], users["bob"]
    g = a.post("/api/groups", name="Algo Club", topic="Dynamic Programming").json["group"]
    a.post("/api/groups", name="Chess", topic="Openings")
    assert [x["name"] for x in b.get("/api/groups?q=dyn").json["groups"]] == ["Algo Club"]
    assert [x["name"] for x in b.get("/api/groups?q=algo dynamic").json["groups"]] == ["Algo Club"]
    assert b.get("/api/groups?q=zzz").json["groups"] == []
    assert len(b.get("/api/groups").json["groups"]) == 2

    post = a.post("/api/posts", content="secret notes", group_id=g["id"]).json["post"]
    assert b.get(f"/api/groups/{g['id']}/posts").status_code == 403                 # was readable by anyone
    assert b.post(f"/api/posts/{post['id']}/like").status_code == 404
    assert b.post(f"/api/posts/{post['id']}/comments", content="hi").status_code == 404
    assert b.post("/api/posts", content="hi", group_id=g["id"]).status_code == 403
    assert a.post("/api/posts", content="hi", group_id="abc").status_code == 400
    assert a.post("/api/posts", content="hi", group_id=999).status_code == 404
    assert all(p["group_id"] is None for p in b.get("/api/posts/feed").json["posts"])

    b.post(f"/api/groups/{g['id']}/join")
    assert [p["content"] for p in b.get(f"/api/groups/{g['id']}/posts").json["posts"]] == ["secret notes"]
    b.post(f"/api/groups/{g['id']}/leave")
    assert b.get(f"/api/groups/{g['id']}/posts").status_code == 403


# ------------------------------------------------- events/resources/announcements
def test_events_resources_announcements_notifications(users):
    a, b, c = users["alice"], users["bob"], users["carol"]
    assert a.post("/api/events", title="Hack", event_date="2999-01-01").status_code == 201
    assert a.post("/api/events", title="Hack", event_date="01/01/2999").status_code == 400
    assert len(b.get("/api/events").json["events"]) == 1               # same college
    assert c.get("/api/events").json["events"] == []                   # other college
    assert len(c.get("/api/events?scope=all").json["events"]) == 1

    assert a.post("/api/resources", title="Notes", url="javascript:alert(1)").status_code == 400
    assert a.post("/api/resources", title="Notes", url="https://x.dev/n").status_code == 201
    assert c.get("/api/resources").json["resources"][0]["added_by_name"] == "Alice Archer"

    assert a.post("/api/announcements", title="Exam", body="Moved to Friday").status_code == 201
    assert a.post("/api/announcements", title="Exam", body="").status_code == 400
    assert b.get("/api/announcements").json["announcements"][0]["title"] == "Exam"
    assert c.get("/api/announcements").json["announcements"] == []
    notes = b.get("/api/notifications").json
    assert {"type": "announcement", "message": "New announcement: Exam"} in notes["items"]


def test_profile_and_dashboard(users):
    a = users["alice"]
    assert a.put("/api/profile", bio="hi", major="CSE", year="3", interests="ml").status_code == 200
    assert a.get("/api/profile").json["profile"]["major"] == "CSE"
    assert a.get("/api/dashboard").json["friend_count"] == 0



def test_network_bfs_levels_and_edges(users):
    """/api/network: friends are level 1, friends-of-friends level 2, edges only between listed nodes."""
    a, b, c = users["alice"], users["bob"], users["carol"]

    def befriend(x, y):
        x.post("/api/friends/request", receiver_id=y.id)
        req = y.get("/api/friends/requests").json["incoming"][0]
        y.post(f"/api/friends/requests/{req['request_id']}/respond", action="accept")

    befriend(a, b)
    befriend(b, c)
    net = a.get("/api/network").json
    assert net["me"] == a.id
    levels = {n["full_name"]: n["level"] for n in net["nodes"]}
    assert levels == {"Alice Archer": 0, "Bob Brown": 1, "Carol Chen": 2}
    assert sorted(map(sorted, net["edges"])) == sorted(map(sorted, [[a.id, b.id], [b.id, c.id]]))
    assert users["carol"].get("/api/network").json["me"] == c.id
