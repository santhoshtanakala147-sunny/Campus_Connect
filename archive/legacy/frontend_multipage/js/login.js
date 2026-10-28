document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const flash = document.getElementById("flash");
    const button = e.target.querySelector("button");
    button.disabled = true;

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
        await apiFetch("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
        });
        window.location.href = "dashboard.html";
    } catch (err) {
        showFlash(flash, err.message, "error");
        button.disabled = false;
    }
});
