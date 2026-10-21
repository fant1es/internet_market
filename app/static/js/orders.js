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
      </div>
      <div class="card-footer d-flex justify-content-between align-items-center">
        <div class="order-actions d-flex gap-2"><!-- кнопки оплаты и отмены добавим следующим шагом --></div>
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
}