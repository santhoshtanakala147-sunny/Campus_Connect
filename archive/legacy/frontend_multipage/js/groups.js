const createFlash = document.getElementById("create-flash");
const groupsFlash = document.getElementById("groups-flash");

function groupCard(group) {
    const div = document.createElement("div");
    div.className = "person-row";
    const actions = group.is_member
        ? `<a class="small-btn" href="group.html?id=${group.id}">Open</a>`
        : `<button class="small-btn" data-id="${group.id}">Join</button>`;
    div.innerHTML = `
        <div class="person-main">
            <div class="avatar">${ICONS.groups}</div>
            <div>
                <div class="person-name">${escapeHtml(group.name)}</div>
                <div class="person-meta">${escapeHtml(group.topic)} &middot; ${group.member_count} member${group.member_count === 1 ? "" : "s"}</div>
            </div>
        </div>
        <div class="person-actions">${actions}</div>
    `;
    return div;
}

async function loadGroups() {
    const container = document.getElementById("groups-list");
    try {
        const data = await apiFetch("/groups");
        container.innerHTML = data.groups.length
            ? ""
            : `<p class="empty-note">No groups yet — start the first one above.</p>`;
        data.groups.forEach((g) => container.appendChild(groupCard(g)));
        container.querySelectorAll("button[data-id]").forEach((btn) => {
            btn.addEventListener("click", async () => {
                btn.disabled = true;
                try {
                    await apiFetch(`/groups/${btn.dataset.id}/join`, { method: "POST" });
                    loadGroups();
                } catch (err) {
                    showFlash(groupsFlash, err.message, "error");
                    btn.disabled = false;
                }
            });
        });
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; return; }
        showFlash(groupsFlash, err.message, "error");
    }
}

document.getElementById("create-group-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("group-name").value.trim();
    const topic = document.getElementById("group-topic").value.trim();
    try {
        await apiFetch("/groups", { method: "POST", body: JSON.stringify({ name, topic }) });
        document.getElementById("create-group-form").reset();
        showFlash(createFlash, "Group created.", "success");
        loadGroups();
    } catch (err) {
        showFlash(createFlash, err.message, "error");
    }
});

loadGroups();
