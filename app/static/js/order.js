const checkoutForm = document.getElementById("checkout-form");

if (checkoutForm) {
    const modalEl = document.getElementById("checkout-modal");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const submitBtn = checkoutForm.querySelector('[type="submit"]');
    const phoneInput = checkoutForm.contact_phone;
    phoneInput.addEventListener("input", () => phoneInput.classList.remove("is-invalid"));

    // При открытии модалки показываем актуальный состав заказа
    modalEl.addEventListener("show.bs.modal", () => {
        if (!currentCart) return;
        document.getElementById("checkout-items").innerHTML = currentCart.items.map(({ product: p, quantity }) => `
            <li class="d-flex justify-content-between gap-3">
              <span>${escapeHtml(p.name)} <span class="text-muted">x${quantity}</span></span>
              <span class="text-nowrap">${formatPrice(p.price * quantity)}</span>
            </li>`).join("");
        document.getElementById("checkout-total").textContent = formatPrice(currentCart.total);
    });

    // Текст подсказки в строке корзины по коду причины с сервера
    const REASONS = {
        inactive: () => "Товар больше недоступен - уберите его из корзины",
        insufficient_stock: (i) => `Доступно только ${i.available} шт. - уменьшите количество`,
    };

    // Сброс формы при каждом закрытии модалки
    modalEl.addEventListener("hidden.bs.modal", () => {
        checkoutForm.reset();
        checkoutForm.classList.remove("was-validated");
        phoneInput.classList.remove("is-invalid");
    });

    checkoutForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!checkoutForm.checkValidity()) {
            checkoutForm.classList.add("was-validated");
            return;
        }

        const body = {
            shipping_address: checkoutForm.shipping_address.value.trim(),
            contact_phone: phoneInput.value.trim()
        };

        submitBtn.disabled = true; // защита от двойной отправки
        try {
            const order = await api("/orders", { method: "POST", body });
            modal.hide();
            location.href = "/my-orders";
        }
        catch (err) {
            const detail = err.data?.detail;
            if (err.status === 422 && Array.isArray(detail)
                && detail.some((d) => d.loc?.includes("contact_phone"))){
                phoneInput.classList.add("is-invalid");
                phoneInput.focus();
                return;
            }
            modal.hide();
            if (err.status === 409 && detail?.code === "cart_unavailable") {
                // Подсвечиваем проблемные строки корзины
                cartProblems.clear();
                detail.items.forEach((i) =>
                    cartProblems.set(i.product_id, (REASONS[i.reason] ?? (() => "Товар недоступен"))(i)));
                showAlert(detail.message, "danger");
                await loadCart(); // перерисует корзину уже с подсветкой
            } else {
                showAlert(errorText(err));
            }
        }
        finally {
            submitBtn.disabled = false;
        }
    });
}