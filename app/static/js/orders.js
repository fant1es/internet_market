const ordersRoot = document.getElementById("orders-root");

const STATUSES = {
    pending:   { label: "Ожидает оплаты", cls: "bg-warning text-dark" },
    paid:      { label: "Оплачен", cls: "bg-info text-dark" },
    completed: { label: "Выполнен", cls: "bg-success" },
    cancelled: { label: "Отменён", cls: "bg-secondary" },
};

function formatDate(iso) {
    // Сервер отдаёт время без часового пояса (это UTC базы). Без "Z" браузер счёл бы его местным
    const hasZone = /[zZ]|[+-]\d\d:\d\d$/.test(iso);
    return new Date(hasZone ? iso : iso + "Z")
        .toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function formatPhone(p) {
    if (!p) return "-";
    const m = /^\+375(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(p);
    return m ? `+375 (${m[1]}) ${m[2]}-${m[3]}-${m[4]}` : p;
}


// Кнопки зависят от статуса: оплатить можно только pending, отменить pending и paid
function actionsHtml(order) {
    const pay = `<button class="btn btn-success btn-sm order-pay" data-id="${order.id}">Оплатить</button>`;
    const cancel = `<button class="btn btn-outline-danger btn-sm order-cancel" data-id="${order.id}">Отменить</button>`;
    if (order.status === "pending") return pay + cancel;
    if (order.status === "paid") return cancel;
    return "";
}

function renderOrder(order) {
    const st = STATUSES[order.status] ?? { label: order.status, cls: "bg-secondary" };

    const items = order.items.map((i) => `
        <li class="d-flex justify-content-between gap-3">
          <span>${escapeHtml(i.product_name)} <span class="text-muted">x${i.quantity}</span></span>
          <span class="text-nowrap">${formatPrice(roundMoney(i.product_price * i.quantity))}</span>
        </li>`).join("");

    return `
    <div class="card mb-3 order-card" data-id="${order.id}">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span class="fw-semibold">Заказ №${order.id}
          <span class="text-muted fw-normal ms-2">${formatDate(order.created_at)}</span>
        </span>
        <span class="badge ${st.cls}">${st.label}</span>
      </div>
      <div class="card-body">
        <ul class="list-unstyled mb-3">${items}</ul>
        <div class="text-muted small">Адрес доставки: ${escapeHtml(order.shipping_address ?? "-")}</div>
        <div class="text-muted small">Телефон: ${formatPhone(order.contact_phone)}</div>
      </div>
      <div class="card-footer d-flex justify-content-between align-items-center">
        <div class="order-actions d-flex gap-2">${actionsHtml(order)}</div>
        <div>Итого: <strong class="fs-5 text-nowrap">${formatPrice(order.total_amount)}</strong></div>
      </div>
    </div>`;
}

function renderOrders(orders) {
    if (orders.length === 0) {
        ordersRoot.innerHTML = `
          <div class="text-center text-muted py-5">
            <p>Заказов пока нет</p>
            <a href="/" class="btn btn-primary">Перейти в каталог</a>
          </div>`;
        return;
    }
    ordersRoot.innerHTML = orders.map(renderOrder).join("");
}

async function loadOrders() {
    try {
        renderOrders(await api("/orders"));
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

if (ordersRoot) {
    loadOrders();

    // Возврат из bfcache, т.к. статусы могли измениться
    window.addEventListener("pageshow", (e) => {
        if (e.persisted) loadOrders();
    });

    ordersRoot.addEventListener("click", async (e) => {
        const btn = e.target.closest(".order-pay, .order-cancel");
        if (!btn) return;

        const isPay = btn.classList.contains("order-pay");
        if (!isPay && !confirm("Отменить заказ? Товары вернутся на склад, а если заказ оплачен, деньги вернутся на баланс.")) {
            return;
        }

        btn.disabled = true; // защита от двойного клика
        try {
            await api(`/orders/${btn.dataset.id}/${isPay ? "pay" : "cancel"}`, { method: "POST" });
            showAlert(isPay ? "Заказ оплачен" : "Заказ отменён", "success");
        }
        catch (err) {
            showAlert(errorText(err));
        }
        // В любом исходе перерисовываем: статус мог измениться в другой вкладке
        await Promise.all([loadOrders(), refreshBalance()]);
    });
}