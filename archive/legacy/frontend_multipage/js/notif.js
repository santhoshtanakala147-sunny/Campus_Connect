// Shared across every page's nav: fetch the notification count and show a badge.
(async function loadNotifBadge() {
    const badge = document.getElementById("notif-badge");
    if (!badge) return;
    try {
        const data = await apiFetch("/notifications");
        if (data.count > 0) {
            badge.textContent = data.count;
            badge.style.display = "inline-block";
        }
    } catch (e) {
        // not logged in yet or request failed — leave badge hidden
    }
})();
