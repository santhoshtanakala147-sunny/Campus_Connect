const searchFlash = document.getElementById("search-flash");
const requestsFlash = document.getElementById("requests-flash");

function personRow(person, actionsHtml) {
    const div = document.createElement("div");
    div.className = "person-row";
    div.innerHTML = `
        <div class="person-main">
            ${avatarHtml(person.full_name)}
            <div>
                <div class="person-name">${escapeHtml(person.full_name)}</div>
                <div class="person-meta">${escapeHtml(person.college)} &middot; ${escapeHtml(person.email)}</div>
            </div>
        </div>
        <div class="person-actions">${actionsHtml}</div>
    `;
    return div;
}

async function runSearch(q) {
    const container = document.getElementById("search-results");
    container.innerHTML = "";
    try {
        const data = await apiFetch(`/students/search?q=${encodeURIComponent(q)}`);
        if (data.results.length === 0) {
            container.innerHTML = `<p class="empty-note">No students found.</p>`;
            return;
        }
        data.results.forEach((person) => {
            const actions = person.is_friend
                ? `<span class="tag">Friends</span>`
                : `<button class="small-btn" data-id="${person.id}">Add friend</button>`;
            const row = personRow(person, actions);
            container.appendChild(row);
        });
        container.querySelectorAll("button[data-id]").forEach((btn) => {
            btn.addEventListener("click", () => sendRequest(btn.dataset.id, btn));
        });
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; return; }
        showFlash(searchFlash, err.message, "error");
    }
}

async function sendRequest(receiverId, btn) {
    btn.disabled = true;
    try {
        await apiFetch("/friends/request", {
            method: "POST",
            body: JSON.stringify({ receiver_id: Number(receiverId) }),
        });
        btn.textContent = "Request sent";
        showFlash(searchFlash, "Friend request sent.", "success");
        loadRequests();
    } catch (err) {
        showFlash(searchFlash, err.message, "error");
        btn.disabled = false;
    }
}

let searchTimer;
document.getElementById("search-input").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    const q = e.target.value;
    searchTimer = setTimeout(() => runSearch(q), 250);
});

async function loadRequests() {
    try {
        const data = await apiFetch("/friends/requests");

        const incoming = document.getElementById("incoming-list");
        incoming.innerHTML = data.incoming.length
            ? ""
            : `<p class="empty-note">No incoming requests.</p>`;
        data.incoming.forEach((person) => {
            const actions = `
                <button class="small-btn" data-id="${person.request_id}" data-action="accept">Accept</button>
                <button class="small-btn secondary" data-id="${person.request_id}" data-action="reject">Reject</button>
            `;
            incoming.appendChild(personRow(person, actions));
        });
        incoming.querySelectorAll("button[data-action]").forEach((btn) => {
            btn.addEventListener("click", () => respond(btn.dataset.id, btn.dataset.action));
        });

        const outgoing = document.getElementById("outgoing-list");
        outgoing.innerHTML = data.outgoing.length
            ? ""
            : `<p class="empty-note">No sent requests pending.</p>`;
        data.outgoing.forEach((person) => {
            outgoing.appendChild(personRow(person, `<span class="tag">Pending</span>`));
        });
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; return; }
        showFlash(requestsFlash, err.message, "error");
    }
}

async function respond(requestId, action) {
    try {
        await apiFetch(`/friends/requests/${requestId}/respond`, {
            method: "POST",
            body: JSON.stringify({ action }),
        });
        showFlash(requestsFlash, `Request ${action}ed.`, "success");
        loadRequests();
        loadFriends();
    } catch (err) {
        showFlash(requestsFlash, err.message, "error");
    }
}

async function loadFriends() {
    const container = document.getElementById("friends-list");
    try {
        const data = await apiFetch("/friends");
        container.innerHTML = data.friends.length
            ? ""
            : `<p class="empty-note">No friends yet — search above to send requests.</p>`;
        data.friends.forEach((person) => container.appendChild(personRow(person, "")));
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; }
    }
}

runSearch("");
loadRequests();
loadFriends();
