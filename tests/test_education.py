"""Education-only enforcement: offline word lists, Gemini judge, API routes, reels, pet."""
import json

import pytest

from ai import education, gemini
from conftest import Client, login, signup
from content import youtube


@pytest.fixture
def edu_users(make_app):
    app = make_app(EDUCATION_ONLY=True)
    out = {}
    for n in ("alice", "bob"):
        c = Client(app)
        signup(c, n.title() + " X", f"{n}@college.edu")
        c.id = login(c, f"{n}@college.edu")
        out[n] = c
    return out


EDU = ["Anyone have notes for DSA unit 3?", "Explain how AVL rotations work please",
       "Hackathon this Friday in the CSE block, register by Thursday", "Prof. Rao moved tomorrow's class to 10am",
       "Internship openings for ML students", "Looking for a study partner for GATE 2027"]
OFF = ["Who's coming to the party tonight? bring snacks", "Best movies on Netflix this weekend lol",
       "Selling my old bike, DM me, great price", "Dream11 prediction for tonight's IPL match",
       "good morning guys!", "My crush replied to my story omg"]


@pytest.mark.parametrize("t", EDU)
def test_assess_educational(t):
    assert education.assess(t).label == "edu"


@pytest.mark.parametrize("t", OFF)
def test_assess_off_topic(t):
    assert education.assess(t).label == "off"


def test_assess_unclear_and_mixed():
    assert education.assess("hello everyone").label == "unclear"
    assert education.assess("Cricket scorecard analysis for my statistics project").label == "mixed"


def test_posts_and_comments(edu_users):
    a, b = edu_users["alice"], edu_users["bob"]
    for t in EDU[:3]:
        assert a.post("/api/posts", content=t).status_code == 201
    r = a.post("/api/posts", content=OFF[0])
    assert r.status_code == 422 and r.json["code"] == "off_topic" and "education only" in r.json["error"].lower()
    assert a.post("/api/posts", content="hello everyone").status_code == 422     # strict without Gemini
    pid = b.post("/api/posts", content="How does a trie beat a hash table for prefix search?").json["post"]["id"]
    assert a.post(f"/api/posts/{pid}/comments", content="thanks, this helped a lot!").status_code == 201
    assert a.post(f"/api/posts/{pid}/comments", content="lol nice party").status_code == 422
    assert a.post(f"/api/posts/{pid}/comments", content="A trie shares prefixes, so lookup is O(length).").status_code == 201
    assert a.post("/api/posts", content="thanks, this helped a lot!").status_code == 422   # no parent context


def test_every_form_rejects_off_topic(edu_users):
    a = edu_users["alice"]
    assert a.post("/api/groups", name="Movie Club", topic="Netflix and chill").status_code == 422
    assert a.post("/api/groups", name="Algo Club", topic="Dynamic Programming").status_code == 201
    assert a.post("/api/events", title="Birthday party", description="Cake and music", event_date="2030-01-01",
                  location="Hostel").status_code == 422
    assert a.post("/api/resources", title="Movie night tickets", description="Selling tickets",
                  url="https://example.com/x").status_code == 422
    assert a.post("/api/resources", title="CLRS notes", description="Algorithms study notes",
                  url="https://example.com/x").status_code == 201
    assert a.put("/api/profile", bio="I love parties and gossip", interests="movies, dating").status_code == 422


def test_off_topic_does_not_trigger_cooldown(edu_users):
    a = edu_users["alice"]
    for i in range(6):
        assert a.post("/api/posts", content=OFF[1] + "!" * i).status_code == 422
    assert a.post("/api/posts", content="Notes for operating systems unit 2?").status_code == 201


def test_distress_is_supported_not_rejected(edu_users):
    r = edu_users["alice"].post("/api/posts", content="exams are crushing me, I want to die")
    assert r.status_code == 201 and "14416" in (r.json.get("notice") or "")


def test_gemini_decides_unclear_text(make_app, monkeypatch):
    app = make_app(EDUCATION_ONLY=True, GEMINI_API_KEY="k")
    c = Client(app); signup(c, "Al X", "al@college.edu"); login(c, "al@college.edu")
    seen = []

    def fake(cfg, **kw):
        seen.append(kw)
        txt = kw["contents"][0]["parts"][0]["text"]
        v = {"verdict": "allow"} if "recursion" in txt else \
            {"verdict": "block", "categories": ["off_topic"], "reason": "Please keep it educational."}
        return {"text": json.dumps(v), "blocked": False, "block_reason": None}

    monkeypatch.setattr(gemini, "generate", fake)
    assert c.post("/api/posts", content="why does this recursion keep going?").status_code == 201
    r = c.post("/api/posts", content="anyone up for a chill evening")
    assert r.status_code == 422 and r.json["code"] == "off_topic"
    assert "EDUCATION ONLY" in seen[0]["system"]


def test_gemini_down_blocks_unclear_text(make_app, monkeypatch):
    app = make_app(EDUCATION_ONLY=True, GEMINI_API_KEY="k")
    c = Client(app); signup(c, "Al X", "al@college.edu"); login(c, "al@college.edu")

    def boom(cfg, **kw):
        raise gemini.GeminiError("down")
    monkeypatch.setattr(gemini, "generate", boom)
    assert c.post("/api/posts", content="hello everyone").status_code == 422
    assert c.post("/api/posts", content="Notes for DSA unit 3?").status_code == 201     # clearly educational: no AI needed


def test_education_independent_of_moderation_switch(make_app):
    app = make_app(EDUCATION_ONLY=True, MODERATION_ENABLED=False)
    c = Client(app); signup(c, "Al X", "al@college.edu"); login(c, "al@college.edu")
    assert c.post("/api/posts", content=OFF[0]).status_code == 422


def test_reels_checked_against_real_youtube_title(make_app, monkeypatch):
    app = make_app(EDUCATION_ONLY=True, REEL_VERIFY=True)
    c = Client(app); signup(c, "Al X", "al@college.edu"); login(c, "al@college.edu")
    titles = {"eduvid00001": ("Binary Search Trees explained", "Some Prof"),
              "offvid00001": ("Top 10 funny movie bloopers lol", "Memes TV")}

    def fake(vid, timeout=6):
        if vid == "gone0000001":
            raise youtube.VideoUnavailable()
        if vid == "net00000001":
            raise youtube.LookupFailed("offline")
        t, a = titles[vid]
        return {"title": t, "author": a}
    monkeypatch.setattr(youtube, "fetch_oembed", fake)
    ok = c.post("/api/reels", url="https://youtu.be/eduvid00001", title="BST lecture", topic="Data Structures")
    assert ok.status_code == 201 and ok.json["reel"]["credit"].startswith("Some Prof")
    # a student can't dress a funny-movie video up with an educational title
    assert c.post("/api/reels", url="https://youtu.be/offvid00001", title="DSA lecture notes").status_code == 422
    assert c.post("/api/reels", url="https://youtu.be/gone0000001", title="DSA lecture").status_code == 422
    assert c.post("/api/reels", url="https://youtu.be/net00000001", title="DSA lecture").status_code == 503
    assert c.post("/api/reels", url="https://youtu.be/zzzzzzzzzzz", title="Movie night trailer").status_code == 422


def test_pet_stays_on_education(edu_users):
    a = edu_users["alice"]
    r = a.post("/api/pet/chat", message="tell me a funny movie joke lol", view="dashboard", history=[])
    assert r.status_code == 200 and "only help with studies" in r.json["reply"]
    r = a.post("/api/pet/chat", message="how do I find study groups?", view="dashboard", history=[])
    assert "only help with studies" not in r.json["reply"]
