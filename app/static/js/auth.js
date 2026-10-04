document.getElementById("login-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const form = e.target;
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;

    try {
        const payload = Object.fromEntries(new FormData(form));
        await api("/auth/login", { method: "POST", body: payload });
        location.href = "/";
    }
    catch (err) {
        showAlert(errorText(err));
    }
    finally {
        submitBtn.disabled = false;
    }
});


document.getElementById("register-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();

    const form = e.target;
    const submitBtn = form.querySelector("button[type=submit]");
    submitBtn.disabled = true;

    try {
        const payload = Object.fromEntries(new FormData(form));
        await api("/auth/register", {
            method: "POST",
            body: payload
        });
        // Запрос к логину нужен для создания токена сессии (регистрация его не создает)
        await api("/auth/login", {
            method: "POST",
            body: { email: payload.email, password: payload.password },
        });
        location.href = "/";
    }
    catch (err) {
        showAlert(errorText(err));
    }
    finally {
        submitBtn.disabled = false;
    }
});