"""Safe handling of student-uploaded posters and diagrams.

The browser shrinks the picture and sends it as a base64 data URL inside JSON (so the JSON-only CSRF rule
still applies). The server never trusts the declared type: it checks the file's own header bytes, accepts only
PNG / JPEG / GIF / WebP (never SVG, which can carry scripts), caps the size, stores it under a random name and
serves it back with a fixed content type and `nosniff`.
"""
import base64
import binascii
import os
import re
import secrets

MAX_BYTES = 2 * 1024 * 1024
NAME_RE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif|webp)$")
DATA_URL = re.compile(r"^data:image/(?:png|jpe?g|gif|webp);base64,([A-Za-z0-9+/=\s]+)$")
MIME = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}


class ImageError(ValueError):
    pass


def sniff(data):
    """Return the extension for the real file type, or None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def decode(data_url):
    """data URL -> (bytes, ext). Raises ImageError with a message fit to show the student."""
    m = DATA_URL.match(data_url or "")
    if not m:
        raise ImageError("Please choose a PNG, JPEG, GIF or WebP image.")
    try:
        data = base64.b64decode(re.sub(r"\s", "", m.group(1)), validate=True)
    except (binascii.Error, ValueError):
        raise ImageError("That image couldn't be read. Please try another one.")
    if not data or len(data) > MAX_BYTES:
        raise ImageError("Images must be under 2 MB.")
    ext = sniff(data)
    if ext is None:
        raise ImageError("That file isn't a valid PNG, JPEG, GIF or WebP image.")
    return data, ext


def save(folder, data, ext):
    os.makedirs(folder, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{ext}"
    with open(os.path.join(folder, name), "wb") as f:
        f.write(data)
    return name


def remove(folder, name):
    if name and NAME_RE.match(name):
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            pass
