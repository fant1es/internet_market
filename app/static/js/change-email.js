const emailForm = document.getElementById("email-form");

if(emailForm){
    const viewActions = document.getElementById("em-view-actions");
    const submitBtn = emailForm.querySelector('[type="submit"]')
    const el = emailForm.elements;

    const KEYS = ["new_email", "current_password"];
    const currentEmail = document.getElementById("pf-email").value.trim().toLowerCase();

    function openForm(){
        viewActions.hidden = true;
        emailForm.hidden = false;
        el.new_email.focus();
    }

    function closeForm(){
        emailForm.reset();
        clearFieldErrors(emailForm);
        emailForm.hidden = true;
        viewActions.hidden = false;
    }

    // Быстрые клиентские проверки
    function validate(){
        const email = el.new_email.value.trim().toLowerCase();
        const errors = {};

        if (!email){
            errors.new_email = "Введите новую почту";
        }
        else if (!el.new_email.validity.valid){
            errors.new_email = "Некорректный адрес почты";
        }
        else if (email === currentEmail) {
            errors.new_email = "Это ваша текущая почта";
        }
        if (!el.current_password.value){
            errors.current_password = "Введите текущий пароль";
        }
        return errors;
    }

    document.getElementById("em-open").addEventListener("click", openForm);
    document.getElementById("em-cancel").addEventListener("click", closeForm);

    emailForm.addEventListener("input", (e) => e.target.classList.remove("is-invalid"));

    emailForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        clearFieldErrors(emailForm);

        const errors = validate();
        const failed = Object.keys(errors);
        if (failed.length){
            failed.forEach((k)=>setFieldError(el[k], errors[k]));
        }

        const newEmail = el.new_email.value.trim();
        submitBtn.disabled = true;
        try {
            await api("/users/me/email",
                {method: "POST",
                    body: {new_email: newEmail, current_password: el.current_password.value}}
            );
            closeForm();
            showAlert(`Письмо со ссылкой отправлено на ${newEmail}.` + "  Почта изменится после подтверждения.",
                "success");
            window.scrollTo({top: 0, behavior: "smooth"});
        }
        catch (err) {
            const detail = err.data?.detail;
            if (err.status === 422 && Array.isArray(detail) && showFieldErrors(emailForm, detail, KEYS)) return;
            showAlert(errorText(err));
        }
        finally {
            submitBtn.disabled = false;
        }
    });
}