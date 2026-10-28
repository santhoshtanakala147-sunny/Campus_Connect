"""Minimal Gemini client (REST `generateContent`, standard library only).

The API key is read from server-side config and sent in the `x-goog-api-key`
header; it is never exposed to the browser or written to logs.
"""

import json
import time
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


class GeminiError(Exception):
    """Network failure, bad status, or an unusable response."""


def is_configured(cfg):
    return bool(cfg.get("GEMINI_API_KEY"))


def _post(cfg, body, timeout):
    url = f"{API_ROOT}/models/{cfg['GEMINI_MODEL']}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": cfg["GEMINI_API_KEY"]},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            pass
        err = GeminiError(f"Gemini HTTP {exc.code}: {detail[:200]}")
        err.status = exc.code
        raise err from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        err = GeminiError(f"Gemini request failed: {type(exc).__name__}")
        err.status = None
        raise err from None


def generate(cfg, *, system, contents, schema=None, temperature=0.2, max_tokens=512, timeout=None):
    """Call the model once.

    `contents` is a list of {"role": "user"|"model", "parts": [{"text": ...}]}.
    With `schema`, the model is asked for JSON matching it (the schema is
    dropped and the call retried once if the API rejects it with HTTP 400).

    Returns {"text": str, "blocked": bool, "block_reason": str|None}.
    "blocked" means Gemini's own safety layer refused the input or output.
    """
    if not is_configured(cfg):
        raise GeminiError("GEMINI_API_KEY is not set")
    timeout = timeout or cfg.get("GEMINI_TIMEOUT", 8)

    def build(with_schema):
        gen = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if schema is not None:
            gen["responseMimeType"] = "application/json"
            if with_schema:
                gen["responseSchema"] = schema
        return {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gen}

    data = None
    for attempt in range(3):
        try:
            data = _post(cfg, build(True), timeout)
            break
        except GeminiError as exc:
            status = getattr(exc, "status", None)
            if status == 400 and schema is not None:
                data = _post(cfg, build(False), timeout)   # schema dialect not accepted: rely on the prompt
                break
            if status in (429, 500, 502, 503, 504) and attempt < 1:
                time.sleep(0.6)
                continue
            raise

    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        return {"text": "", "blocked": True, "block_reason": str(feedback["blockReason"])}
    candidates = data.get("candidates") or []
    if not candidates:
        raise GeminiError("Gemini returned no candidates")
    cand = candidates[0]
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    if cand.get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII") and not text:
        return {"text": "", "blocked": True, "block_reason": cand["finishReason"]}
    if not text:
        raise GeminiError("Gemini returned an empty response")
    return {"text": text, "blocked": False, "block_reason": None}


def parse_json(text):
    """Parse model output as JSON, tolerating ```json fences. Raises GeminiError."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    try:
        value = json.loads(t)
    except ValueError:
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end <= start:
            raise GeminiError("Model did not return JSON") from None
        try:
            value = json.loads(t[start:end + 1])
        except ValueError:
            raise GeminiError("Model returned malformed JSON") from None
    if not isinstance(value, dict):
        raise GeminiError("Model returned unexpected JSON")
    return value
