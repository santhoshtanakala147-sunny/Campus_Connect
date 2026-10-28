document.getElementById("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const flash = document.getElementById("flash");
    const button = e.target.querySelector("button");
    button.disabled = true;

    const payload = {
        full_name: document.getElementById("full_name").value,
        college: document.getElementById("college").value,
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
        confirm_password: document.getElementById("confirm_password").value,
    };

    try {
        await apiFetch("/auth/register", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        showFlash(flash, "Account created! Redirecting to log in...", "success");
        setTimeout(() => { window.location.href = "login.html"; }, 1200);
    } catch (err) {
        showFlash(flash, err.message, "error");
        button.disabled = false;
    }
});
