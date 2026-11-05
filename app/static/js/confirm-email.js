const ceButton = document.getElementById("ce-confirm");

if (ceButton){
    const blocks = {
        pending: document.getElementById("ce-pending"),
        done: document.getElementById("ce-done"),
        error: document.getElementById("ce-error")
    };

    function showBlock(name, message){
        Object.entries(blocks).forEach(([key,node]) => {node.hidden = key !== name;});
        if (message) document.getElementById("ce-error-text").textContent = message;
    }


    const token = new URLSearchParams(location.search).get("token");
    history.replaceState(null, "", location.pathname);

    if (!token){
        showBlock("error", "Ссылка недействительна: в ней нет токена");
    }

    ceButton.addEventListener("click", async ()=> {
        ceButton.disabled = true;
        try {
            await api("/auth/confirm-email", {method: "POST", body: {token}});
            showBlock("done");
        }
        catch (err) {
            showBlock("error", errorText(err));
        }
    })
}