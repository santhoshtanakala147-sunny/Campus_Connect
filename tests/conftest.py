import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# Importing app.py builds a module-level app, so point it at a throwaway DB.
_tmp = tempfile.mkdtemp()
os.environ["CC_DATABASE_PATH"] = os.path.join(_tmp, "import.db")

import pytest  # noqa: E402

from app import create_app  # noqa: E402


@pytest.fixture
def make_app(tmp_path):
    def _make(**overrides):
        cfg = {"DATABASE_PATH": str(tmp_path / "test.db"), "TESTING": True,
               "REQUIRE_EMAIL_VERIFICATION": False,
               "EDUCATION_ONLY": False, "REEL_VERIFY": False, "DEMO_DATA": False}
        cfg.update(overrides)
        return create_app(cfg)
    return _make


@pytest.fixture
def app(make_app):
    return make_app()


class Client:
    """Thin wrapper so every request is sent as JSON like the real frontend."""

    def __init__(self, app):
        self.c = app.test_client()

    def post(self, url, /, **body):
        return self.c.post(url, json=body)

    def put(self, url, /, **body):
        return self.c.put(url, json=body)

    def delete(self, url):
        return self.c.delete(url, json={})

    def get(self, url):
        return self.c.get(url)


@pytest.fixture
def client(app):
    return Client(app)


def signup(client, name, email, college="Test Uni", password="password1"):
    r = client.post("/api/auth/register", full_name=name, email=email, college=college,
                    password=password, confirm_password=password)
    assert r.status_code == 201, r.json
    return r


def login(client, email, password="password1"):
    r = client.post("/api/auth/login", email=email, password=password)
    assert r.status_code == 200, r.json
    return r.json["user"]["id"]


@pytest.fixture
def users(app):
    """Three logged-in clients (alice, bob, carol) on the same app."""
    out = {}
    for name, college in (("Alice Archer", "Test Uni"), ("Bob Brown", "Test Uni"), ("Carol Chen", "Other Uni")):
        c = Client(app)
        email = f"{name.split()[0].lower()}@college.edu"
        signup(c, name, email, college)
        c.id = login(c, email)
        out[name.split()[0].lower()] = c
    return out
