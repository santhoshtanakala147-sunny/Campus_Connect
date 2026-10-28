const postsFlash = document.getElementById("posts-flash");
const composerFlash = document.getElementById("composer-flash");
let activeTab = "recent";

function timeAgo(createdAt) {
    // createdAt is "YYYY-MM-DD HH:MM:SS" UTC from SQLite
    const then = new Date(createdAt.replace(" ", "T") + "Z");
    const diffMs = Date.now() - then.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

function renderPost(post) {
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
            <button class="small-btn icon-btn secondary comment-toggle" data-id="${post.id}">${ICONS.chat}<span>Comments (${post.comment_count})</span></button>
        </div>
        <div class="comments-section" id="comments-${post.id}" style="display:none;">
            <div class="comments-list" id="comments-list-${post.id}"></div>
            <form class="comment-form" data-id="${post.id}">
                <input type="text" placeholder="Write a comment..." maxlength="500">
                <button type="submit" class="small-btn">Send</button>
            </form>
        </div>
    `;
    return el;
}

async function loadPosts() {
    const container = document.getElementById("posts-list");
    container.innerHTML = `<p class="loading-note">Loading...</p>`;
    try {
        const path = activeTab === "trending" ? "/posts/trending" : "/posts/feed";
        const data = await apiFetch(path);
        container.innerHTML = "";
        if (data.posts.length === 0) {
            container.innerHTML = `<p class="empty-note">No posts yet — be the first to share something.</p>`;
            return;
        }
        data.posts.forEach((post) => container.appendChild(renderPost(post)));
        wirePostEvents();
    } catch (err) {
        if (err.status === 401) { window.location.href = "login.html"; return; }
        showFlash(postsFlash, err.message, "error");
    }
}

function wirePostEvents() {
    document.querySelectorAll(".like-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            btn.disabled = true;
            try {
                const data = await apiFetch(`/posts/${btn.dataset.id}/like`, { method: "POST" });
                btn.innerHTML = `${ICONS.heart}<span>Like (${data.post.likes})</span>`;
            } catch (err) {
                showFlash(postsFlash, err.message, "error");
            } finally {
                btn.disabled = false;
            }
        });
    });

    document.querySelectorAll(".comment-toggle").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const section = document.getElementById(`comments-${btn.dataset.id}`);
            const isHidden = section.style.display === "none";
            section.style.display = isHidden ? "block" : "none";
            if (isHidden) await loadComments(btn.dataset.id);
        });
    });

    document.querySelectorAll(".comment-form").forEach((form) => {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const input = form.querySelector("input");
            const content = input.value.trim();
            if (!content) return;
            try {
                await apiFetch(`/posts/${form.dataset.id}/comments`, {
                    method: "POST",
                    body: JSON.stringify({ content }),
                });
                input.value = "";
                await loadComments(form.dataset.id);
                const toggle = document.querySelector(`.comment-toggle[data-id="${form.dataset.id}"]`);
                const list = document.getElementById(`comments-list-${form.dataset.id}`);
                toggle.innerHTML = `${ICONS.chat}<span>Comments (${list.children.length})</span>`;
            } catch (err) {
                showFlash(postsFlash, err.message, "error");
            }
        });
    });
}

async function loadComments(postId) {
    const list = document.getElementById(`comments-list-${postId}`);
    list.innerHTML = `<p class="loading-note">Loading comments...</p>`;
    try {
        const data = await apiFetch(`/posts/${postId}/comments`);
        list.innerHTML = "";
        if (data.comments.length === 0) {
            list.innerHTML = `<p class="empty-note">No comments yet.</p>`;
            return;
        }
        data.comments.forEach((c) => {
            const div = document.createElement("div");
            div.className = "comment-row";
            div.textContent = c.content;
            list.appendChild(div);
        });
    } catch (err) {
        showFlash(postsFlash, err.message, "error");
    }
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        activeTab = btn.dataset.tab;
        loadPosts();
    });
});

document.getElementById("composer-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const textarea = document.getElementById("post-content");
    const content = textarea.value.trim();
    if (!content) return;
    try {
        await apiFetch("/posts", { method: "POST", body: JSON.stringify({ content }) });
        textarea.value = "";
        if (activeTab === "recent") loadPosts();
        else showFlash(composerFlash, "Posted! Switch to Recent to see it.", "success");
    } catch (err) {
        showFlash(composerFlash, err.message, "error");
    }
});

loadPosts();
