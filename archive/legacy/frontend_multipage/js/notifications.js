const flash = document.getElementById("notifications-flash");

async function loadNotifications() {
    const container = document.getElementById("notifications-list");
    try {
        const data = await apiFetch("/notifications");
        container.innerHTML = data.items.length
            ? ""
            : `<p class="empty-note">You're all caught up.</p>`;
        data.items.forEach((item) => {
            const div = document.createElement("div");
            div.className = "person-row";
            const link = item.type === "friend_request" ? "friends.html" : "events.html";
            const icon = item.type === "friend_request" ? ICONS.friends : ICONS.events;
            div.innerHTML = `
                <div class="person-main">
                    <div class="avatar">${icon}</div>
                    <div class="person-name">${escapeHtml(item.message)}</div>
                </div>
                <div class="person-actions"><a class="small-btn" href="${link}">View</a></div>
            `;
            container.appendChild(div);
        });
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; return; }
        showFlash(flash, err.message, "error");
    }
}

loadNotifications();
