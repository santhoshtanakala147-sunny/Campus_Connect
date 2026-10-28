import pytest

from app import parse_youtube
from content import reels_seed
from conftest import Client, login, signup


# ---------------------------------------------------------------- parser
@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=FNeL18KsWPc", ("FNeL18KsWPc", 0)),
    ("https://youtu.be/FNeL18KsWPc?t=90", ("FNeL18KsWPc", 90)),
    ("https://youtu.be/FNeL18KsWPc?t=1m30s", ("FNeL18KsWPc", 90)),
    ("https://www.youtube.com/watch?v=FNeL18KsWPc&start=15&list=x", ("FNeL18KsWPc", 15)),
    ("https://www.youtube.com/shorts/abcDEF12345", ("abcDEF12345", 0)),
    ("https://m.youtube.com/embed/abcDEF12345", ("abcDEF12345", 0)),
    ("https://www.youtube-nocookie.com/embed/abcDEF12345", ("abcDEF12345", 0)),
])
def test_parse_youtube_accepts(url, expected):
    assert parse_youtube(url) == expected


@pytest.mark.parametrize("url", [
    "", "nope", "https://vimeo.com/123456789", "https://youtube.com.evil.example/watch?v=FNeL18KsWPc",
    "https://evil.example/?u=youtube.com/watch?v=FNeL18KsWPc", "javascript:alert(1)",
    "https://www.youtube.com/watch?v=short", "https://www.youtube.com/watch?v=FNeL18KsWPc%22onload%3D1",
    "https://www.youtube.com/watch", "ftp://www.youtube.com/watch?v=FNeL18KsWPc",
])
def test_parse_youtube_rejects(url):
    assert parse_youtube(url) is None


def test_seed_content_is_well_formed():
    slugs = [r["slug"] for r in reels_seed.REELS]
    assert len(slugs) == len(set(slugs))
    kinds = {r["kind"] for r in reels_seed.REELS}
    assert kinds == {"prebuilt", "open"}
    for r in reels_seed.REELS:
        assert r["topic"] in reels_seed.TOPICS and r["license"] and r["credit"] and r["title"]
        if r["media"] == "youtube":
            assert len(r["media_ref"]) == 11 and r["source_url"].startswith("https://ocw.mit.edu/")
            assert r["license"] == "CC BY-NC-SA 4.0"          # every embedded lecture was verified as CC BY-NC-SA
    assert {r["media_ref"] for r in reels_seed.REELS if r["media"] == "animation"} == {"hash", "bfs", "trie", "avl", "heap", "safety"}
    assert all(i["url"].startswith("https://") and i["license"] for i in reels_seed.REFERENCES)


# ------------------------------------------------------------------ API
def test_reels_list_filters_and_sorting(users):
    a = users["alice"]
    reels = a.get("/api/reels").json["reels"]
    assert [r["kind"] for r in reels] == ["prebuilt"] * 6 + ["open"] * 6        # curated order
    assert a.get("/api/reels?kind=open").json["reels"][0]["media"] == "youtube"
    ds = a.get("/api/reels?topic=Data Structures").json["reels"]
    assert ds and all(r["topic"] == "Data Structures" for r in ds)
    assert a.get("/api/reels?topic=bogus").json["reels"] == reels                # unknown filter ignored
    assert "Quantum" in a.get("/api/reels").json["topics"]
    heap_id = next(r["id"] for r in reels if r["media_ref"] == "heap")
    a.post(f"/api/reels/{heap_id}/like")
    assert a.get("/api/reels?sort=top").json["reels"][0]["id"] == heap_id        # max-heap puts the liked reel first


def test_like_toggle_and_auth(users, client):
    a, b = users["alice"], users["bob"]
    rid = a.get("/api/reels").json["reels"][0]["id"]
    assert a.post(f"/api/reels/{rid}/like").json["reel"] == {**a.get(f"/api/reels?kind=prebuilt").json["reels"][0]}
    assert b.post(f"/api/reels/{rid}/like").json["reel"]["likes"] == 2
    r = a.post(f"/api/reels/{rid}/like").json["reel"]                              # toggle off
    assert r["likes"] == 1 and r["liked"] is False
    assert a.post("/api/reels/99999/like").status_code == 404
    assert client.get("/api/reels").status_code == 401 and client.get("/api/reference").status_code == 401


def test_share_community_reel(users):
    a, b = users["alice"], users["bob"]
    body = dict(url="https://youtu.be/abcDEF12345?t=42", title="My DSA tips", description="Short and sweet", topic="Study Tips")
    r = a.post("/api/reels", **body)
    assert r.status_code == 201
    reel = r.json["reel"]
    assert (reel["kind"], reel["media_ref"], reel["start"], reel["can_delete"], reel["added_by"]) == ("community", "abcDEF12345", 42, True, "Alice Archer")
    assert reel["source_url"] == "https://www.youtube.com/watch?v=abcDEF12345"      # rebuilt from the id, never copied from input
    assert a.post("/api/reels", **body).status_code == 409                          # duplicate video
    assert a.post("/api/reels", url="https://youtu.be/FNeL18KsWPc", title="dup of a curated one").status_code == 409
    assert a.post("/api/reels", url="https://vimeo.com/1", title="x").status_code == 400
    assert a.post("/api/reels", url="https://youtu.be/zzzzzzzzzzz", title="  ").status_code == 400
    assert a.post("/api/reels", url="https://youtu.be/zzzzzzzzzzz", title="odd topic", topic="Hax").json["reel"]["topic"] == "Other"

    assert [x["title"] for x in b.get("/api/reels?kind=community").json["reels"]] == ["odd topic", "My DSA tips"]
    assert b.get("/api/reels?kind=community").json["reels"][1]["can_delete"] is False
    assert b.delete(f"/api/reels/{reel['id']}").status_code == 403
    curated = a.get("/api/reels?kind=prebuilt").json["reels"][0]["id"]
    assert a.delete(f"/api/reels/{curated}").status_code == 403                     # curated reels can't be deleted
    assert a.delete(f"/api/reels/{reel['id']}").status_code == 200
    assert a.delete(f"/api/reels/{reel['id']}").status_code == 404


def test_share_limits_and_moderation(users):
    a = users["alice"]
    for i in range(5):
        assert a.post("/api/reels", url=f"https://youtu.be/aaaaaaaaa{i:02d}", title=f"vid {i}").status_code == 201
    assert a.post("/api/reels", url="https://youtu.be/bbbbbbbbbbb", title="one more").status_code == 429
    b = users["bob"]
    assert b.post("/api/reels", url="https://youtu.be/ccccccccccc", title="my password is hunter2").status_code == 422   # safety checks apply
    assert b.post("/api/reels", url="https://youtu.be/ddddddddddd", title="free stuff", description="see bit.ly/xyz").status_code == 422


def test_reference_library(users):
    items = users["alice"].get("/api/reference").json["items"]
    groups = {i["group"] for i in items}
    assert {"Open textbooks", "Free courses", "Related papers (from our project deck)"} <= groups
    assert any(i["title"] == "Open Data Structures" and i["license"].startswith("CC BY") for i in items)


def test_seed_is_idempotent_and_keeps_likes(make_app, users, app):
    a = users["alice"]
    rid = a.get("/api/reels").json["reels"][0]["id"]
    a.post(f"/api/reels/{rid}/like")
    app2 = make_app(DATABASE_PATH=app.config["DATABASE_PATH"])           # restart: seed runs again
    c = Client(app2)
    login(c, "alice@college.edu")
    reels = c.get("/api/reels").json["reels"]
    assert len(reels) == 12 and next(r for r in reels if r["id"] == rid)["liked"] is True


def test_pet_knows_about_reels(users):
    r = users["alice"].post("/api/pet/chat", message="any good lecture videos to watch?", view="feed").json
    assert r["goto"] == "reels"


def test_resource_urls_with_quotes_rejected(users):
    a = users["alice"]
    assert a.post("/api/resources", title="x", url='https://a.example/" onmouseover="alert(1)').status_code == 400
    assert a.post("/api/resources", title="x", url="https://a.example/ok?a=1&b=2").status_code == 201
