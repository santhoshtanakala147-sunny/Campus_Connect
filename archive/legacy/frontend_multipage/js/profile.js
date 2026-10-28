const flash = document.getElementById("flash");

async function loadProfile() {
    try {
        const data = await apiFetch("/profile");
        document.getElementById("name").textContent = data.user.full_name;
        document.getElementById("email-college").textContent = `${data.user.email} · ${data.user.college}`;
        document.getElementById("bio").value = data.profile.bio || "";
        document.getElementById("major").value = data.profile.major || "";
        document.getElementById("year").value = data.profile.year || "";
        document.getElementById("interests").value = data.profile.interests || "";
    } catch (err) {
        if (err.status === 401) {
            window.location.href = "login.html";
        }
    }
}

document.getElementById("profile-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
        bio: document.getElementById("bio").value,
        major: document.getElementById("major").value,
        year: document.getElementById("year").value,
        interests: document.getElementById("interests").value,
    };

    try {
        await apiFetch("/profile", { method: "PUT", body: JSON.stringify(payload) });
        showFlash(flash, "Profile updated.", "success");
    } catch (err) {
        showFlash(flash, err.message, "error");
    }
});

loadProfile();
