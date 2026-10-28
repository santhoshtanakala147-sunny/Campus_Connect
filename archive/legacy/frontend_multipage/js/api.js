// Shared fetch helper for talking to the Flask REST API. All endpoints
// live under /api and use session-cookie auth (same-origin, so no CORS
// setup is needed as long as the frontend is served by the same Flask app).

const API_BASE = "/api";

async function apiFetch(path, options = {}) {
    const res = await fetch(API_BASE + path, {
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        ...options,
    });

    let data = {};
    try {
        data = await res.json();
    } catch (e) {
        // no JSON body
    }

    if (!res.ok) {
        const error = new Error(data.error || `Request failed (${res.status})`);
        error.status = res.status;
        error.data = data;
        throw error;
    }

    return data;
}

function showFlash(el, message, kind) {
    if (!el) return;
    el.textContent = message;
    el.className = `flash flash-${kind} visible`;
}

async function logout() {
    try {
        await apiFetch("/auth/logout", { method: "POST" });
    } catch (e) {
        // ignore
    }
    window.location.href = "login.html";
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function initialsOf(name) {
    if (!name) return "?";
    const parts = name.trim().split(/\s+/);
    const first = parts[0]?.[0] || "";
    const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
    return (first + last).toUpperCase();
}

function avatarHtml(name, size) {
    const cls = size === "small" ? "avatar small" : "avatar";
    return `<div class="${cls}">${initialsOf(name)}</div>`;
}
