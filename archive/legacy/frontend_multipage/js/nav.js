// Renders the shared navbar into <div id="app-nav"></div> on every page.
// Single source of truth for nav markup/icons so every page stays in sync.

const ICONS = {
    brand: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/><path d="M22 10v6"/></svg>`,
    dashboard: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-6h6v6"/></svg>`,
    feed: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h10M7 17h6"/></svg>`,
    groups: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>`,
    events: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>`,
    friends: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="3.2"/><circle cx="16.2" cy="9" r="2.6"/><path d="M2.2 20c0-3.4 2.6-6 6-6 2 0 3.7 1 4.8 2.5"/><path d="M13.8 14.4c2.7.4 5.9 2 5.9 5.6"/></svg>`,
    games: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="8" width="20" height="10" rx="5"/><path d="M7 11v4M5 13h4"/><circle cx="16" cy="11" r="1"/><circle cx="18.2" cy="14" r="1"/></svg>`,
    profile: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>`,
    bell: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>`,
    logout: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/></svg>`,
    heart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 8.6c0 4.4-8.8 10-8.8 10s-8.8-5.6-8.8-10a4.8 4.8 0 0 1 8.8-2.7A4.8 4.8 0 0 1 20.8 8.6z"/></svg>`,
    chat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 0 1-8 8H4l2.3-3.4A8 8 0 1 1 21 12z"/></svg>`,
    lock: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>`,
    rocket: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 15l-2 6 6-2 9-9a4 4 0 0 0-4-4l-9 9z"/><circle cx="15" cy="9" r="1.4"/><path d="M9 15l-4 4"/></svg>`,
    wave: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 13c2-4 5-6 8-4"/><path d="M8 21c4 1 9-1 11-6 1-3-1-6-3-6-1.5 0-2.5 1-3 2.5"/></svg>`,
};

const NAV_ITEMS = [
    { href: "dashboard.html", label: "Dashboard", icon: ICONS.dashboard },
    { href: "feed.html", label: "Feed", icon: ICONS.feed },
    { href: "groups.html", label: "Groups", icon: ICONS.groups, matchAlso: ["group.html"] },
    { href: "events.html", label: "Events", icon: ICONS.events },
    { href: "friends.html", label: "Friends", icon: ICONS.friends },
    { href: "games.html", label: "Games", icon: ICONS.games },
    { href: "profile.html", label: "Profile", icon: ICONS.profile },
];

function renderNav() {
    const root = document.getElementById("app-nav");
    if (!root) return;

    const current = window.location.pathname.split("/").pop() || "index.html";

    const linksHtml = NAV_ITEMS.map((item) => {
        const isActive = current === item.href || (item.matchAlso || []).includes(current);
        return `<a class="${isActive ? "active" : ""}" href="${item.href}">${item.icon}<span>${item.label}</span></a>`;
    }).join("");

    root.innerHTML = `
        <a class="brand" href="index.html"><span class="brand-mark">${ICONS.brand}</span>CampusConnect</a>
        <div class="nav-links">
            ${linksHtml}
            <a id="notif-link" href="notifications.html">${ICONS.bell}<span id="notif-badge" class="badge" style="display:none;"></span></a>
            <a id="logout-link">${ICONS.logout}<span>Log out</span></a>
        </div>
    `;

    document.getElementById("logout-link").addEventListener("click", logout);
}

renderNav();
