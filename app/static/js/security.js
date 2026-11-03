const passwordForm = document.getElementById("password-form");

if (passwordForm) {
    const viewActions = document.getElementById("pw-view-actions");
    const submitBtn = passwordForm.querySelector('[type="submit"]');
    const el = passwordForm.elements;

    const KEYS = ["current_password", "new_password", "confirm_password"];
    const MIN_LEN = 8;
    const MAX_LEN = 128;

    function openForm() {
        viewActions.hidden = true;
        passwordForm.hidden = false;
        el.current_password.focus();
    }

    function closeForm() {
        passwordForm.reset();
        clearFieldErrors(passwordForm);
        passwordForm.hidden = true;
        viewActions.hidden = false;
    }

    // Клиентские проверки нужны для мгновенного отклика, главными остаются серверные.
    // Пароли намеренно не обрезаются по пробелам
    function validate() {
        const current = el.current_password.value;
        const next = el.new_password.value;
        const confirm = el.confirm_password.value;
        const errors = {};

        if (!current) {
            errors.current_password = "Введите текущий пароль";
        }
        if (next.length < MIN_LEN) {
            errors.new_password = `Пароль должен быть не короче ${MIN_LEN} символов`;
        } else if (next.length > MAX_LEN) {
            errors.new_password = `Пароль должен быть не длиннее ${MAX_LEN} символов`;
        } else if (next === current) {
            errors.new_password = "Новый пароль должен отличаться от текущего";
        }
        if (confirm !== next) {
            errors.confirm_password = "Пароли не совпадают";
        }
        return errors;
    }

    document.getElementById("pw-open").addEventListener("click", openForm);
    document.getElementById("pw-cancel").addEventListener("click", closeForm);

    // Правка поля снимает подсветку ошибки именно с него
    passwordForm.addEventListener("input", (e) => e.target.classList.remove("is-invalid"));

    passwordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        clearFieldErrors(passwordForm);

        const errors = validate();
        const failed = Object.keys(errors);
        if (failed.length) {
            failed.forEach((k) => setFieldError(el[k], errors[k]));
            el[failed[0]].focus();
            return;
        }

        // Защита от двойного клика
        submitBtn.disabled = true;
        try {
            // confirm_password на сервер не уходит из-за extra="forbid"
            await api("/users/me/password", {
                method: "PATCH",
                body: {
                    current_password: el.current_password.value,
                    new_password: el.new_password.value,
                },
            });
            closeForm();
            showAlert("Пароль изменён. На других устройствах вы будете разлогинены", "success");
        }
        catch (err) {
            const detail = err.data?.detail;
            if (err.status === 422 && Array.isArray(detail) && showFieldErrors(passwordForm, detail, KEYS)) return;
            showAlert(errorText(err));
        }
        finally {
            submitBtn.disabled = false;
        }
    });
}