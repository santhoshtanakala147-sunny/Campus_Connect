import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _flag(name, default):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # SECRET_KEY: if the env var is unset, app.py generates a random key once
    # and stores it in instance/secret_key (never a hard-coded default).
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Students must click an emailed link before they can log in. Set
    # CC_REQUIRE_VERIFICATION=0 to skip this while developing/demoing.
    # Without SMTP settings below, the link is printed to the server console.
    REQUIRE_EMAIL_VERIFICATION = _flag("CC_REQUIRE_VERIFICATION", "1")
    SMTP_HOST = os.environ.get("CC_SMTP_HOST")
    SMTP_PORT = int(os.environ.get("CC_SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("CC_SMTP_USER")
    SMTP_PASSWORD = os.environ.get("CC_SMTP_PASSWORD")
    MAIL_FROM = os.environ.get("CC_MAIL_FROM", "CampusConnect <no-reply@campusconnect.local>")
    SESSION_COOKIE_SECURE = _flag("CC_SECURE_COOKIES", "0")  # set 1 behind HTTPS

    # --- Gemini (server-side only; the key is never sent to the browser) ---
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    GEMINI_TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "8"))

    # Content safety checks on posts, comments, groups, links, events, announcements, bios.
    # Local rules always run; Gemini adds AI classification when a key is set.
    MODERATION_ENABLED = _flag("CC_MODERATION", "1")
    # If Gemini is down: 0 = fall back to local rules only (default), 1 = reject the post.
    EDUCATION_ONLY = _flag("CC_EDUCATION_ONLY", "1")   # reject anything not about education
    DEMO_DATA = _flag("CC_DEMO_DATA", "1")            # sample classmates, posts, groups and events (CC_DEMO_DATA=0 to disable)
    REEL_VERIFY = _flag("CC_REEL_VERIFY", "1")        # check shared videos with YouTube oEmbed
    MODERATION_FAIL_CLOSED = _flag("CC_MODERATION_FAIL_CLOSED", "0")
    MODERATION_MAX_BLOCKS = 3            # this many blocked submissions...
    MODERATION_COOLDOWN_SECONDS = 600    # ...within this window triggers a cooldown

    # Pet chatbot
    PET_NAME = os.environ.get("CC_PET_NAME", "Mochi")
    PET_CHATS_PER_MINUTE = int(os.environ.get("CC_PET_CHATS_PER_MINUTE", "15"))

    # Friend-to-friend chat. Safety checks (harassment, scams, links...) always apply; the
    # education-only gate is OFF for chat by default because "are you coming to the lab?" is
    # normal between friends. Set CC_CHAT_EDUCATION_ONLY=1 to hold chat to the same rule as posts.
    CHAT_EDUCATION_ONLY = _flag("CC_CHAT_EDUCATION_ONLY", "0")
    CHAT_MESSAGES_PER_MINUTE = int(os.environ.get("CC_CHAT_MESSAGES_PER_MINUTE", "30"))
    CHAT_MAX_LENGTH = 1000

    LOGIN_MAX_FAILURES = 5
    LOGIN_WINDOW_SECONDS = 300
    DATABASE_PATH = os.environ.get("CC_DATABASE_PATH") or os.path.join(BASE_DIR, "instance", "campusconnect.db")
    SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

    # A student's email domain must END WITH one of these (suffix match, see
    # campusconnect/auth/routes.py::_is_allowed_college_email). This lets one
    # entry like ".edu" cover every US university, ".ac.in"/".edu.in" cover
    # most Indian institutions generically, and specific official domains
    # (IITs, NITs, etc.) still work even if they don't fit those patterns.
    ALLOWED_COLLEGE_EMAIL_DOMAINS = [
        # Generic academic suffixes
        ".edu",         # any accredited US college/university (e.g. mit.edu, stanford.edu)
        ".ac.in",       # Indian institutions (e.g. iitb.ac.in, iitd.ac.in)
        ".edu.in",      # Indian institutions using the .edu.in pattern
        ".ac.uk",       # UK universities

        # Popular official Indian college/university domains that don't
        # match the generic suffixes above
        "cb.students.amrita.edu",
        "amrita.edu",
        "vit.ac.in",
        "vitstudent.ac.in",
        "bits-pilani.ac.in",
        "srmist.edu.in",
        "srmuniv.ac.in",
        "manipal.edu",
        "learner.manipal.edu",
        "kluniversity.in",
        "nitt.edu",
        "anna.univ.edu",
        "annauniv.edu",

        # Fallback for local dev/testing
        "college.edu",
    ]
