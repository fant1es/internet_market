const ordersRoot = document.getElementById("orders-root");

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

    bindOrderActions(ordersRoot, loadOrders);
}