const balanceAmount = document.getElementById("balance-amount"); // есть только у залогиненного

// Единая точка обновления баланса на странице (пригодится и при оплате заказа)
function setBalance(value) {
    if (!balanceAmount) return;
    balanceAmount.dataset.balance = value;
    const text = formatPrice(Number(value));
    balanceAmount.textContent = text;
    const current = document.getElementById("topup-current");
    if (current) current.textContent = text;
}

// Запрашивает актуальный баланс и обновляет шапку
async function refreshBalance() {
    try {
        const me = await api("/auth/me");
        setBalance(me.balance);
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

if (balanceAmount) {
    setBalance(balanceAmount.dataset.balance); // значение пришло из шаблона

    const form = document.getElementById("topup-form");
    const input = document.getElementById("topup-amount");
    const modalEl = document.getElementById("topup-modal");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const submitBtn = form.querySelector('[type="submit"]');

    // Быстрые суммы просто подставляют значение в поле
    form.addEventListener("click", (e) => {
        const preset = e.target.closest(".topup-preset");
        if (preset) input.value = preset.dataset.amount;
    });

    // Сброс формы при каждом закрытии
    modalEl.addEventListener("hidden.bs.modal", () => {
        form.reset();
        form.classList.remove("was-validated");
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!form.checkValidity()) {
            form.classList.add("was-validated");
            return;
        }

        submitBtn.disabled = true; // защита от двойной отправки
        try {
            const res = await api("/balance/topup", {
                method: "POST",
                body: { amount: input.value },
            });
            setBalance(res.balance);
            modal.hide();
            showAlert("Баланс пополнен", "success");
        }
        catch (err) {
            showAlert(errorText(err));
        }
        finally {
            submitBtn.disabled = false;
        }
    });
}