const createFlash = document.getElementById("create-flash");
const eventsFlash = document.getElementById("events-flash");
let scope = "college";

function eventCard(ev) {
    const div = document.createElement("div");
    div.className = "person-row";
    div.innerHTML = `
        <div class="person-main">
            <div class="avatar">${ICONS.events}</div>
            <div>
                <div class="person-name">${escapeHtml(ev.title)}</div>
                <div class="person-meta">${escapeHtml(ev.event_date)} &middot; ${escapeHtml(ev.college)}</div>
                ${ev.description ? `<div class="person-meta" style="margin-top:4px;">${escapeHtml(ev.description)}</div>` : ""}
            </div>
        </div>
    `;
    return div;
}

async function loadEvents() {
    const container = document.getElementById("events-list");
    try {
        const data = await apiFetch(`/events?scope=${scope}`);
        container.innerHTML = data.events.length
            ? ""
            : `<p class="empty-note">No upcoming events.</p>`;
        data.events.forEach((ev) => container.appendChild(eventCard(ev)));
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; return; }
        showFlash(eventsFlash, err.message, "error");
    }
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        scope = btn.dataset.scope;
        loadEvents();
    });
});

document.getElementById("create-event-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("event-title").value.trim();
    const event_date = document.getElementById("event-date").value;
    const description = document.getElementById("event-description").value.trim();
    try {
        await apiFetch("/events", { method: "POST", body: JSON.stringify({ title, event_date, description }) });
        document.getElementById("create-event-form").reset();
        showFlash(createFlash, "Event created.", "success");
        loadEvents();
    } catch (err) {
        showFlash(createFlash, err.message, "error");
    }
});

loadEvents();
