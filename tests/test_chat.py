"""1:1 chat between friends."""
import pytest

from conftest import Client, login, signup


def befriend(a, b):
    assert a.post("/api/friends/request", receiver_id=b.id).status_code == 201
    rid = b.get("/api/friends/requests").json["incoming"][0]["request_id"]
    assert b.post(f"/api/friends/requests/{rid}/respond", action="accept").status_code == 200


def test_friends_can_chat_and_unread_counts(users):
    a, b = users["alice"], users["bob"]
    befriend(a, b)
    r = a.post(f"/api/chat/{b.id}", content="Are you free to revise graphs tonight?")
    assert r.status_code == 201 and r.json["message"]["mine"] is True

    convs = b.get("/api/chat/conversations").json
    assert convs["unread_total"] == 1
    row = [c for c in convs["conversations"] if c["id"] == a.id][0]
    assert row["unread"] == 1 and row["last_message"]["mine"] is False
    assert b.get("/api/chat/unread").json["unread"] == 1
    assert any(i["type"] == "message" for i in b.get("/api/notifications").json["items"])

    thread = b.get(f"/api/chat/{a.id}").json                  # opening the thread marks it read
    assert [m["content"] for m in thread["messages"]] == ["Are you free to revise graphs tonight?"]
    assert thread["messages"][0]["mine"] is False
    assert b.get("/api/chat/unread").json["unread"] == 0

    # Alice sees the read receipt.
    seen = a.get(f"/api/chat/{b.id}").json
    assert seen["read_upto"] == seen["messages"][0]["id"]


def test_polling_returns_only_newer_messages(users):
    a, b = users["alice"], users["bob"]
    befriend(a, b)
    first = a.post(f"/api/chat/{b.id}", content="Notes on AVL rotations").json["message"]
    b.post(f"/api/chat/{a.id}", content="Thanks, sending the trie notes next")
    newer = a.get(f"/api/chat/{b.id}?after={first['id']}").json["messages"]
    assert [m["content"] for m in newer] == ["Thanks, sending the trie notes next"]
    assert a.get(f"/api/chat/{b.id}?after=999999").json["messages"] == []


def test_conversations_sorted_by_latest_message(users):
    a, b, c = users["alice"], users["bob"], users["carol"]
    befriend(a, b); befriend(a, c)
    a.post(f"/api/chat/{b.id}", content="hello bob")
    a.post(f"/api/chat/{c.id}", content="hello carol")
    names = [x["full_name"] for x in a.get("/api/chat/conversations").json["conversations"]]
    assert names == ["Carol Chen", "Bob Brown"]


def test_only_friends_can_chat(users):
    a, b = users["alice"], users["bob"]
    assert a.post(f"/api/chat/{b.id}", content="hi").status_code == 403
    assert a.get(f"/api/chat/{b.id}").status_code == 403
    assert a.post(f"/api/chat/{a.id}", content="hi me").status_code == 404
    assert a.post("/api/chat/99999", content="hi").status_code == 404


def test_no_chat_after_unfriending(users):
    a, b = users["alice"], users["bob"]
    befriend(a, b)
    a.post(f"/api/chat/{b.id}", content="hi")
    assert a.post(f"/api/friends/{b.id}/remove").status_code == 200
    assert a.post(f"/api/chat/{b.id}", content="still there?").status_code == 403
    assert b.get(f"/api/chat/{a.id}").status_code == 403
    assert a.get("/api/chat/conversations").json["conversations"] == []


def test_validation_and_login_required(app, users):
    a, b = users["alice"], users["bob"]
    befriend(a, b)
    assert a.post(f"/api/chat/{b.id}", content="   ").status_code == 400
    assert a.post(f"/api/chat/{b.id}", content="x" * 1001).status_code == 400
    anon = Client(app)
    assert anon.get("/api/chat/conversations").status_code == 401
    assert anon.post(f"/api/chat/{b.id}", content="hi").status_code == 401


def test_safety_checks_apply_to_messages(users):
    a, b = users["alice"], users["bob"]
    befriend(a, b)
    r = a.post(f"/api/chat/{b.id}", content="my otp is 482913 and password: hunter22, use it")
    assert r.status_code in (422, 400), r.json
    r = a.post(f"/api/chat/{b.id}", content="click http://192.168.4.4/login now")
    assert r.status_code in (422, 400), r.json
    assert b.get("/api/chat/unread").json["unread"] == 0


def test_rate_limit(make_app):
    app = make_app(CHAT_MESSAGES_PER_MINUTE=3)
    a, b = Client(app), Client(app)
    for c, n in ((a, "alice"), (b, "bob")):
        signup(c, n.title() + " X", f"{n}@college.edu"); c.id = login(c, f"{n}@college.edu")
    befriend(a, b)
    codes = [a.post(f"/api/chat/{b.id}", content=f"note {i}").status_code for i in range(5)]
    assert codes == [201, 201, 201, 429, 429]


@pytest.mark.parametrize("flag, expected", [(False, 201), (True, 422)])
def test_education_only_switch_for_chat(make_app, flag, expected):
    app = make_app(EDUCATION_ONLY=True, CHAT_EDUCATION_ONLY=flag)
    a, b = Client(app), Client(app)
    for c, n in ((a, "alice"), (b, "bob")):
        signup(c, n.title() + " X", f"{n}@college.edu"); c.id = login(c, f"{n}@college.edu")
    befriend(a, b)
    r = a.post(f"/api/chat/{b.id}", content="lol did you watch the cricket match yesterday")
    assert r.status_code == expected, r.json


def test_messages_survive_restart(make_app):
    app = make_app()
    a, b = Client(app), Client(app)
    for c, n in ((a, "alice"), (b, "bob")):
        signup(c, n.title() + " X", f"{n}@college.edu"); c.id = login(c, f"{n}@college.edu")
    befriend(a, b)
    a.post(f"/api/chat/{b.id}", content="one")
    a.post(f"/api/chat/{b.id}", content="two")
    b.get(f"/api/chat/{a.id}")                                   # reads both
    a.post(f"/api/chat/{b.id}", content="three")                 # unread
    from app import create_app
    app2 = create_app({"DATABASE_PATH": app.config["DATABASE_PATH"], "TESTING": True,
                       "REQUIRE_EMAIL_VERIFICATION": False, "EDUCATION_ONLY": False, "DEMO_DATA": False})
    b2 = Client(app2)
    login(b2, "bob@college.edu")
    thread = b2.get(f"/api/chat/{a.id}").json["messages"]
    assert [m["content"] for m in thread] == ["one", "two", "three"]


def test_friendly_small_talk_is_allowed_with_default_settings(make_app):
    """Greetings, 'how are you' and a self-introduction must never be blocked, even with the
    education-only rule on for posts (the project default)."""
    app = make_app(EDUCATION_ONLY=True)
    a, b = Client(app), Client(app)
    for c, n in ((a, "alice"), (b, "bob")):
        signup(c, n.title() + " X", f"{n}@college.edu"); c.id = login(c, f"{n}@college.edu")
    befriend(a, b)
    for text in ["Hi", "Hi Bob! \U0001F44B", "Hi Bob, how are you?", "hey, how's it going?",
                 "Hi Bob! I'm Alice Archer from Test Uni. Nice to connect with you. What are you studying?",
                 "Good morning! Hope you're doing well", "thanks, see you tomorrow"]:
        r = a.post(f"/api/chat/{b.id}", content=text)
        assert r.status_code == 201, (text, r.json)
