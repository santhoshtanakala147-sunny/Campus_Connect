"""Look up a YouTube video's real title/author via YouTube's public oEmbed endpoint.

Used to stop people sharing an off-topic video under an educational-sounding title:
we judge the title YouTube reports, not just the one the student typed.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

OEMBED = "https://www.youtube.com/oembed"


class VideoUnavailable(Exception):
    """Video is private, removed or can't be embedded."""


class LookupFailed(Exception):
    """Couldn't reach YouTube (network problem)."""


def fetch_oembed(vid, timeout=6):
    """Return {"title": str, "author": str} for an 11-char video id."""
    q = urllib.parse.urlencode({"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"})
    try:
        with urllib.request.urlopen(f"{OEMBED}?{q}", timeout=timeout) as r:
            data = json.loads(r.read(100_000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403, 404):
            raise VideoUnavailable() from exc
        raise LookupFailed(str(exc)) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LookupFailed(str(exc)) from exc
    return {"title": str(data.get("title") or "")[:200], "author": str(data.get("author_name") or "")[:100]}
