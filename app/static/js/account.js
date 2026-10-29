const profileForm = document.getElementById("profile-form");

if (profileForm) {
    const fields = document.getElementById("pf-fields");
    const viewActions = document.getElementById("pf-view-actions");
    const editActions = document.getElementById("pf-edit-actions");
    const submitBtn = profileForm.querySelector('[type="submit"]');
    const navName = document.getElementById("nav-user-name");
    const el = profileForm.elements;

    const KEYS = ["name", "phone", "default_address"];

    // Сохраняем последние значения с сервера из полей
    const saved = Object.fromEntries(KEYS.map((k)=>[k,el[k].value.trim()]));

    function setEditing(on){
        fields.disabled = !on
        viewActions.hidden = on;
        editActions.hidden = !on;
        if (on) el.name.focus();
    }

    function restore(){
        KEYS.forEach((k)=>{el[k].value = saved[k];});
        profileForm.querySelectorAll(".is-invalid").forEach(
            (i)=>i.classList.remove("is-invalid"));
        profileForm.classList.remove("was-validated");
    }

    function showFieldErrors(detail){
        let found = false;
        for (const d of detail){
            const input = el[d.loc?.[d.loc.length - 1]];
            if (!input || !KEYS.includes(input.name)) continue;

            input.classList.add("is-invalid");
            // Убираем префикс от pydantic "Value error"
            input.parentElement.querySelector(".invalid-feedback").textContent =
                d.msg.replace(/^Value error, /, "");
            found = true;
        }
        return found;
    }

    document.getElementById("pf-edit").addEventListener("click", () => setEditing(true));
    document.getElementById("pf-cancel").addEventListener("click", () => {
        restore();
        setEditing(false);
    });

    // Правка поля снимает подсветку ошибки именно с него
    profileForm.addEventListener("input", (e) => e.target.classList.remove("is-invalid"));

    profileForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (fields.disabled) return;
        if (!profileForm.checkValidity()){
            profileForm.classList.add("was-validated");
            return;
        }

        // Отправка только измененных полей
        const body = {};
        for (const k of KEYS){
            const v = el[k].value.trim();
            if(v !== saved[k]) body[k] = v;
        }
        if (Object.keys(body).length === 0){
            setEditing(false);
            return;
        }

        //Защита от двойного клика
        submitBtn.disabled = true;
        try {
            const me = await api("/users/me", { method: "PATCH", body });
            // Показываем то, что реально сохранилось
            saved.name = me.name;
            saved.phone = me.phone ?? "";
            saved.default_address = me.default_address ?? "";
            restore();
            setEditing(false);
            if (navName) navName.textContent = me.name;
            showAlert("Профиль сохранён", "success");
        }
        catch (err) {
            const detail = err.data?.detail;
            if (err.status === 422 && Array.isArray(detail) && showFieldErrors(detail)) return;
            showAlert(errorText(err));
        }
        finally {
            submitBtn.disabled = false;
        }
    });
}