document.getElementById("logout-btn")?.addEventListener("click", async () => {
    try {
        await api("/auth/logout", { method: "POST" });
        location.href = "/login";
    }
    catch (err) {
        showAlert(errorText(err));
    }
});