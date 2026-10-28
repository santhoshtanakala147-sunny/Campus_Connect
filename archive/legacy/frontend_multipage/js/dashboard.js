const QUICK_LINKS = [
    { href: "feed.html", icon: ICONS.feed, label: "Feed", desc: "See what's trending" },
    { href: "groups.html", icon: ICONS.groups, label: "Groups", desc: "Join a discussion" },
    { href: "friends.html", icon: ICONS.friends, label: "Friends", desc: "Find classmates" },
    { href: "events.html", icon: ICONS.events, label: "Events", desc: "What's coming up" },
    { href: "games.html", icon: ICONS.games, label: "Games", desc: "Take a quick break" },
    { href: "profile.html", icon: ICONS.profile, label: "Profile", desc: "Edit your details" },
];

document.getElementById("quick-links").innerHTML = QUICK_LINKS.map((item) => `
    <a class="quick-link-card" href="${item.href}">
        <span class="icon">${item.icon}</span>
        <span class="label">${item.label}</span>
        <span class="desc">${item.desc}</span>
    </a>
`).join("");

(async function loadDashboard() {
    try {
        const data = await apiFetch("/dashboard");
        document.getElementById("welcome").textContent = `Welcome, ${data.user.full_name}`;
        document.getElementById("college").textContent = data.user.college;
        document.getElementById("friend-count").textContent = data.friend_count;
    } catch (err) {
        if (err.status === 401) {
            window.location.href = "login.html";
        }
    }
})();
