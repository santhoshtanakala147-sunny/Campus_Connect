const params = new URLSearchParams(window.location.search);
const groupId = params.get("id");
const groupFlash = document.getElementById("group-flash");
const composerFlash = document.getElementById("composer-flash");

if (!groupId) {
    window.location.href = "groups.html";
}

function timeAgo(createdAt) {
    const then = new Date(createdAt.replace(" ", "T") + "Z");
    const mins = Math.floor((Date.now() - then.getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

async function loadGroup() {
    try {
        const data = await apiFetch(`/groups/${groupId}`);
        document.getElementById("group-name").textContent = data.group.name;
        document.getElementById("group-meta").textContent =
            `${data.group.topic} · ${data.group.member_count} member${data.group.member_count === 1 ? "" : "s"}`;
        if (!data.group.is_member) {
            document.getElementById("composer-form").style.display = "none";
            document.getElementById("leave-btn").style.display = "none";
        }
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; return; }
        showFlash(groupFlash, err.message, "error");
    }
}

async function loadPosts() {
    const container = document.getElementById("posts-list");
    try {
        const data = await apiFetch(`/groups/${groupId}/posts`);
        container.innerHTML = data.posts.length
            ? ""
            : `<p class="empty-note">No posts in this group yet.</p>`;
        data.posts.forEach((post) => {
            const el = document.createElement("div");
            el.className = "post-card";
            el.innerHTML = `
                <div class="post-header">
                    ${avatarHtml(post.author_name, "small")}
                    <div class="post-header-text">
                        <span class="post-author">${escapeHtml(post.author_name)}</span>
                        <span class="post-time">${timeAgo(post.created_at)}</span>
                    </div>
                </div>
                <div class="post-content">${escapeHtml(post.content)}</div>
                <div class="post-actions">
                    <button class="small-btn icon-btn like-btn" data-id="${post.id}">${ICONS.heart}<span>Like (${post.likes})</span></button>
                </div>
            `;
            container.appendChild(el);
        });
        container.querySelectorAll(".like-btn").forEach((btn) => {
            btn.addEventListener("click", async () => {
                btn.disabled = true;
                try {
                    const data = await apiFetch(`/posts/${btn.dataset.id}/like`, { method: "POST" });
                    btn.innerHTML = `${ICONS.heart}<span>Like (${data.post.likes})</span>`;
                } finally {
                    btn.disabled = false;
                }
            });
        });
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; }
    }
}

document.getElementById("composer-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const textarea = document.getElementById("post-content");
    const content = textarea.value.trim();
    if (!content) return;
    try {
        await apiFetch("/posts", { method: "POST", body: JSON.stringify({ content, group_id: Number(groupId) }) });
        textarea.value = "";
        loadPosts();
    } catch (err) {
        showFlash(composerFlash, err.message, "error");
    }
});

document.getElementById("leave-btn").addEventListener("click", async () => {
    try {
        await apiFetch(`/groups/${groupId}/leave`, { method: "POST" });
        window.location.href = "groups.html";
    } catch (err) {
        showFlash(groupFlash, err.message, "error");
    }
});

loadGroup();
loadPosts();
