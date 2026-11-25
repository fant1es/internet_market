const STATUS_CLASSES = {
    pending: "bg-warning text-dark",
    paid: "bg-info text-dark",
    completed: "bg-success",
    cancelled: "bg-secondary",
};

function statusOf(order) {
    const key = `status.${order.status}`;
    return {
        label: window.I18N?.[key] ? t(key) : order.status,   // неизвестный статус показываем как есть
        cls: STATUS_CLASSES[order.status] ?? "bg-secondary",
    };
}

function formatDate(iso) {
    // Сервер отдаёт время без часового пояса (это UTC базы). Без "Z" браузер счёл бы его местным
    const hasZone = /[zZ]|[+-]\d\d:\d\d$/.test(iso);
    const locale = window.LANG === "en" ? "en-GB" : "ru-RU";
    return new Date(hasZone ? iso : iso + "Z")
        .toLocaleString(locale, { dateStyle: "short", timeStyle: "short" });
}

function formatPhone(p) {
    if (!p) return "-";
    const m = /^\+375(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(p);
    return m ? `+375 (${m[1]}) ${m[2]}-${m[3]}-${m[4]}` : p;
}

// Кнопки зависят от статуса: оплата только для pending, отмена еще и для paid,
function actionsHtml(order) {
    const pay = `<button class="btn btn-success btn-sm order-pay" data-id="${order.id}">${t("js.orders.pay")}</button>`;
    const cancel = `<button class="btn btn-outline-danger btn-sm order-cancel" data-id="${order.id}">${t("js.orders.cancel")}</button>`;

    const receipt = `
        <a class="btn btn-outline-secondary btn-sm" href="/orders/${order.id}/receipt" target="_blank" rel="noopener">${t("js.orders.receipt")}</a>
        <a class="btn btn-outline-secondary btn-sm" href="/orders/${order.id}/receipt.pdf">${t("js.orders.download_pdf")}</a>`;

    if (order.status === "pending") return pay + cancel;
    if (order.status === "paid") return receipt + cancel;
    if (order.status === "completed") return receipt;
    return "";
}

// Полная карточка
function renderOrder(order) {
    const st = statusOf(order);

    const items = order.items.map((i) => `
        <li class="d-flex justify-content-between gap-3">
          <span>${escapeHtml(i.product_name)} <span class="text-muted">x${i.quantity}</span></span>
          <span class="text-nowrap">${formatPrice(roundMoney(i.product_price * i.quantity))}</span>
        </li>`).join("");

    return `
    <div class="card mb-3 order-card" data-id="${order.id}">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">${t("js.orders.order_no", { id: order.id })}
          <span class="text-muted fw-normal ms-2">${formatDate(order.created_at)}</span>
        </span>
        <span class="badge ${st.cls}">${st.label}</span>
      </div>
      <div class="card-body">
        <ul class="list-unstyled mb-3">${items}</ul>
        <div class="text-muted small">${t("js.orders.address")}: ${escapeHtml(order.shipping_address ?? "-")}</div>
        <div class="text-muted small">${t("js.orders.phone")}: ${formatPhone(order.contact_phone)}</div>
      </div>
      <div class="card-footer d-flex justify-content-between align-items-center">
        <div class="order-actions d-flex gap-2">${actionsHtml(order)}</div>
        <div>${t("js.orders.total")}: <strong class="fs-5 text-nowrap">${formatPrice(order.total_amount)}</strong></div>
      </div>
    </div>`;
}

// Компактная строка для кабинета с номером, датой, статусом и суммой
function renderOrderRow(order) {
    const st = statusOf(order);
    return `
    <a href="/my-orders" class="list-group-item list-group-item-action
                                d-flex justify-content-between align-items-center gap-3">
      <span>${t("js.orders.order_no", { id: order.id })}
        <span class="text-muted small ms-2">${formatDate(order.created_at)}</span>
      </span>
      <span class="d-flex align-items-center gap-3">
        <span class="badge ${st.cls}">${st.label}</span>
        <strong class="text-nowrap">${formatPrice(order.total_amount)}</strong>
      </span>
    </a>`;
}

// Оплата и отмена на любом контейнере с карточками. onChange для перерисовки списка после действия
function bindOrderActions(root, onChange) {
    root.addEventListener("click", async (e) => {
        const btn = e.target.closest(".order-pay, .order-cancel");
        if (!btn) return;

        const isPay = btn.classList.contains("order-pay");
        if (!isPay && !confirm(t("js.orders.cancel_confirm"))) {
            return;
        }

        btn.disabled = true; // защита от двойного клика
        try {
            await api(`/orders/${btn.dataset.id}/${isPay ? "pay" : "cancel"}`, { method: "POST" });
            showAlert(isPay ? t("js.orders.paid") : t("js.orders.cancelled"), "success");
        }
        catch (err) {
            showAlert(errorText(err));
        }
        // В любом исходе перерисовываем: статус мог измениться в другой вкладке
        await Promise.all([onChange(), refreshBalance()]);
    });
}