"""Poster images on posts, comments on reels, and saved posts."""
import base64
import json
import os

import pytest

from ai import gemini
from conftest import Client, login, signup

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def data_url(raw=PNG, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def uploads(app):
    d = os.path.join(os.path.dirname(app.config["DATABASE_PATH"]), "uploads")
    return os.listdir(d) if os.path.isdir(d) else []


def two(make_app, **cfg):
    app = make_app(**cfg)
    out = []
    for n in ("alice", "bob"):
        c = Client(app); signup(c, n.title() + " X", f"{n}@college.edu"); c.id = login(c, f"{n}@college.edu"); out.append(c)
    return app, out[0], out[1]


# ---------------------------------------------------------------- posters
def test_poster_upload_serve_and_delete(make_app):
    app, a, b = two(make_app)
    r = a.post("/api/posts", content="Poster for the DSA workshop this Friday", image=data_url())
    assert r.status_code == 201
    post = r.json["post"]
    assert post["image_url"].startswith("/api/uploads/") and post["image_url"].endswith(".png")
    img = b.get(post["image_url"])                                   # other students can see it
    assert img.status_code == 200 and img.content_type == "image/png" and img.data == PNG
    assert img.headers["X-Content-Type-Options"] == "nosniff" and "sandbox" in img.headers["Content-Security-Policy"]
    assert Client(app).get(post["image_url"]).status_code == 401      # not public
    assert b.get("/api/posts/feed").json["posts"][0]["image_url"] == post["image_url"]
    assert len(uploads(app)) == 1
    assert a.delete(f"/api/posts/{post['id']}").status_code == 200
    assert uploads(app) == []                                         # file removed with the post


@pytest.mark.parametrize("bad", [
    data_url(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "image/svg+xml"),
    data_url(b"<?php echo 1;", "image/png"),                          # declared PNG, isn't
    data_url(PNG + b"\0" * (2 * 1024 * 1024)),                        # too big
    "data:image/png;base64,@@@@",
    "https://example.com/x.png",
    "javascript:alert(1)",
])
def test_bad_images_rejected(make_app, bad):
    app, a, _ = two(make_app)
    r = a.post("/api/posts", content="Notes for operating systems", image=bad)
    assert r.status_code in (400, 413) and uploads(app) == []


def test_upload_name_must_be_generated_by_app(make_app):
    app, a, _ = two(make_app)
    for name in ("../config.py", "..%2fconfig.py", "x.png", "a" * 32 + ".svg"):
        assert a.get(f"/api/uploads/{name}").status_code == 404


def test_poster_needs_educational_caption(make_app):
    app, a, _ = two(make_app, EDUCATION_ONLY=True)
    assert a.post("/api/posts", content="Check out this party pic lol", image=data_url()).status_code == 422
    assert uploads(app) == []
    assert a.post("/api/posts", content="Poster: machine learning seminar on Monday", image=data_url()).status_code == 201


def test_group_post_with_image(make_app):
    app, a, b = two(make_app)
    g = a.post("/api/groups", name="Algo Club", topic="Dynamic Programming").json["group"]
    p = a.post("/api/posts", content="Cheat sheet for DP states", group_id=g["id"], image=data_url()).json["post"]
    assert a.get(f"/api/groups/{g['id']}/posts").json["posts"][0]["image_url"] == p["image_url"]


def test_gemini_judges_the_picture(make_app, monkeypatch):
    app, a, _ = two(make_app, GEMINI_API_KEY="k", EDUCATION_ONLY=True)
    seen = {}

    def fake(cfg, **kw):
        parts = kw["contents"][0]["parts"]
        if any("inline_data" in p for p in parts):
            seen["img"] = True
            v = seen.get("verdict", {"verdict": "allow"})
        else:
            v = {"verdict": "allow"}
        return {"text": json.dumps(v), "blocked": False, "block_reason": None}
    monkeypatch.setattr(gemini, "generate", fake)
    assert a.post("/api/posts", content="Workshop poster on graph algorithms", image=data_url()).status_code == 201
    assert seen["img"]
    seen["verdict"] = {"verdict": "block", "categories": ["off_topic"], "reason": "That looks like a meme, not study material."}
    n = len(uploads(app))
    r = a.post("/api/posts", content="Poster for algorithms club", image=data_url())
    assert r.status_code == 422 and r.json["code"] == "off_topic" and len(uploads(app)) == n

    def boom(cfg, **kw):
        if any("inline_data" in p for p in kw["contents"][0]["parts"]):
            raise gemini.GeminiError("down")
        return {"text": json.dumps({"verdict": "allow"}), "blocked": False, "block_reason": None}
    monkeypatch.setattr(gemini, "generate", boom)
    assert a.post("/api/posts", content="Another poster for the algorithms club", image=data_url()).status_code == 503


# ---------------------------------------------------------------- reel comments
def first_reel(c):
    return c.get("/api/reels").json["reels"][0]


def test_reel_comments_crud(make_app):
    app, a, b = two(make_app)
    reel = first_reel(a)
    assert reel["comment_count"] == 0
    r = a.post(f"/api/reels/{reel['id']}/comments", content="The balance factor part finally clicked, thanks!")
    assert r.status_code == 201 and r.json["comment_count"] == 1 and r.json["comment"]["can_delete"]
    cid = r.json["comment"]["id"]
    got = b.get(f"/api/reels/{reel['id']}/comments").json["comments"]
    assert [c["content"] for c in got] == ["The balance factor part finally clicked, thanks!"] and got[0]["can_delete"] is False
    assert first_reel(b)["comment_count"] == 1
    assert b.delete(f"/api/reels/{reel['id']}/comments/{cid}").status_code == 403
    assert a.post(f"/api/reels/{reel['id']}/comments", content="  ").status_code == 400
    assert a.post(f"/api/reels/{reel['id']}/comments", content="x" * 501).status_code == 400
    assert a.post("/api/reels/99999/comments", content="hi").status_code == 404
    assert Client(app).post(f"/api/reels/{reel['id']}/comments", content="hi").status_code == 401
    d = a.delete(f"/api/reels/{reel['id']}/comments/{cid}")
    assert d.status_code == 200 and d.json["comment_count"] == 0
    assert a.delete(f"/api/reels/{reel['id']}/comments/{cid}").status_code == 404


def test_reel_comments_are_checked(make_app):
    app, a, _ = two(make_app, EDUCATION_ONLY=True)
    rid = first_reel(a)["id"]
    assert a.post(f"/api/reels/{rid}/comments", content="lol best party movie ever").status_code == 422
    assert a.post(f"/api/reels/{rid}/comments", content="my password is hunter2").status_code == 422
    assert a.post(f"/api/reels/{rid}/comments", content="thanks, this helped a lot!").status_code == 201    # courtesy under an educational reel
    assert a.post(f"/api/reels/{rid}/comments", content="Could you show the rotation case for an unbalanced node?").status_code == 201


def test_deleting_a_reel_removes_its_comments(make_app):
    app, a, _ = two(make_app)
    rid = a.post("/api/reels", url="https://youtu.be/abcDEF12345", title="My DSA tips").json["reel"]["id"]
    a.post(f"/api/reels/{rid}/comments", content="Great tips for revising trees")
    assert a.delete(f"/api/reels/{rid}").status_code == 200
    assert a.get(f"/api/reels/{rid}/comments").status_code == 404


# ---------------------------------------------------------------- saved posts
def test_save_posts_is_private_and_toggles(make_app):
    app, a, b = two(make_app)
    pid = a.post("/api/posts", content="Notes for DBMS unit 2").json["post"]["id"]
    assert b.post(f"/api/posts/{pid}/save").json["post"]["saved"] is True
    assert [p["id"] for p in b.get("/api/posts/saved").json["posts"]] == [pid]
    assert a.get("/api/posts/saved").json["posts"] == []                    # private to Bob
    assert a.get("/api/posts/feed").json["posts"][0]["saved"] is False
    assert b.post(f"/api/posts/{pid}/save").json["post"]["saved"] is False
    assert b.get("/api/posts/saved").json["posts"] == []
    assert b.post("/api/posts/9999/save").status_code == 404


def test_saved_survive_restart(make_app):
    app, a, b = two(make_app)
    pid = a.post("/api/posts", content="Notes for DBMS unit 2").json["post"]["id"]
    b.post(f"/api/posts/{pid}/save")
    app2 = make_app()
    c = Client(app2); c.post("/api/auth/login", email="bob@college.edu", password="password1")
    assert [p["id"] for p in c.get("/api/posts/saved").json["posts"]] == [pid]


def test_event_poster(make_app):
    app, a, b = two(make_app)
    r = a.post("/api/events", title="Graph algorithms workshop", event_date="2099-01-01", description="Hands-on session", image=data_url())
    assert r.status_code == 201 and r.json["event"]["image_url"].endswith(".png") and "image" not in r.json["event"]
    ev = a.get("/api/events").json["events"][0]
    assert b.get(ev["image_url"]).data == PNG if ev["college"] == "Test Uni" else True
    assert a.post("/api/events", title="Poster test", event_date="2099-01-02", image="data:image/png;base64,AAAA").status_code == 400
    assert len(uploads(app)) == 1


# ---------------------------------------------------------------- YouTube videos on posts
def test_video_post_verified_against_youtube(make_app, monkeypatch):
    from content import youtube
    app, a, b = two(make_app, EDUCATION_ONLY=True, REEL_VERIFY=True)
    titles = {"eduvid00001": "Hashing with chaining: full lecture", "offvid00001": "Funny movie bloopers lol"}

    def fake(vid, timeout=6):
        if vid == "gone0000001":
            raise youtube.VideoUnavailable()
        if vid == "net00000001":
            raise youtube.LookupFailed("offline")
        return {"title": titles[vid], "author": "Some Prof"}
    monkeypatch.setattr(youtube, "fetch_oembed", fake)

    ok = a.post("/api/posts", content="Watch this before tomorrow's DSA quiz", video="https://youtu.be/eduvid00001?t=5")
    assert ok.status_code == 201
    assert ok.json["post"]["video"] == {"id": "eduvid00001", "title": "Hashing with chaining: full lecture"}
    assert b.get("/api/posts/feed").json["posts"][0]["video"]["id"] == "eduvid00001"
    for i, (url, status) in enumerate((("https://youtu.be/offvid00001", 422), ("https://youtu.be/gone0000001", 422),
                        ("https://youtu.be/net00000001", 503), ("https://vimeo.com/1", 400), ("javascript:alert(1)", 400))):
        assert a.post("/api/posts", content=f"Notes video {i} for the algorithms exam", video=url).status_code == status, url
    assert a.post("/api/posts", content="Algorithms lecture and poster", video="https://youtu.be/eduvid00001", image=data_url()).status_code == 400
    assert a.post("/api/posts", content="Party video lol", video="https://youtu.be/eduvid00001").status_code == 422   # caption is checked too
    assert a.get("/api/posts/feed").json["posts"][0]["video"]["id"] == "eduvid00001"                               # nothing else saved


def test_video_post_without_verification_and_in_group(make_app):
    app, a, _ = two(make_app)            # verification off in tests: id is kept, title blank -> "Video"
    g = a.post("/api/groups", name="Algo Club", topic="Dynamic Programming").json["group"]
    p = a.post("/api/posts", content="Lecture on DP states", group_id=g["id"], video="https://www.youtube.com/watch?v=abcDEF12345").json["post"]
    assert p["video"] == {"id": "abcDEF12345", "title": "Video"}
    assert a.get(f"/api/groups/{g['id']}/posts").json["posts"][0]["video"]["id"] == "abcDEF12345"
