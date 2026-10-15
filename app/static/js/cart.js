// #cart-count есть в шапке только у залогиненного пользователя,
const cartCount = document.getElementById("cart-count");
const cartRoot = document.getElementById("cart-root"); // есть только на странице корзины

// id товаров, которые сейчас лежат в корзине
const cartProductIds = new Set();

// Приводит все кнопки "В корзину" на странице в соответствие с корзиной
function syncCartButtons() {
    document.querySelectorAll(".add-to-cart").forEach((btn) => {
        const inCart = cartProductIds.has(Number(btn.dataset.id));
        btn.classList.toggle("btn-primary", !inCart);
        btn.classList.toggle("btn-outline-primary", inCart);
        btn.classList.toggle("in-cart", inCart);
        btn.textContent = inCart ? "В корзине" : "В корзину";
    });
}

function updateCartBadge(cart) {
    if (cartCount) cartCount.textContent = cart.total_quantity;
}

// Единая точка обновления: счётчик в шапке + страница корзины (если мы на ней)
function refreshCartUI(cart) {
    updateCartBadge(cart);
    cartProductIds.clear();
    cart.items.forEach((i) => cartProductIds.add(i.product.id));
    syncCartButtons();
    if (cartRoot) renderCart(cart);
}

function renderCart(cart) {
    if (cart.items.length === 0) {
        cartRoot.innerHTML = `
          <div class="text-center text-muted py-5">
            <p>Корзина пуста</p>
            <a href="/" class="btn btn-primary">Перейти в каталог</a>
          </div>`;
        return;
    }

    const rows = cart.items.map(({ id, product: p, quantity, subtotal }) => {
        const imageUrl = productImageUrl(p);
        return `
        <tr>
          <td style="width: 80px">
            ${imageUrl
                ? `<img src="${escapeHtml(imageUrl)}" alt="" class="img-fluid">`
                : `<span class="text-muted small">Нет фото</span>`}
          </td>
          <td><a href="/product/${p.id}" class="text-decoration-none">${escapeHtml(p.name)}</a></td>
          <td class="text-nowrap">${formatPrice(p.price)}</td>
          <td style="width: 110px">
            <input type="number" class="form-control form-control-sm qty-input"
                   data-id="${id}" value="${quantity}" min="1" max="${p.stock_quantity}">
          </td>
          <td class="text-nowrap fw-bold">${formatPrice(subtotal)}</td>
          <td class="text-end">
            <button class="btn btn-outline-danger btn-sm remove-item" data-id="${id}">Удалить</button>
          </td>
        </tr>`;
    }).join("");

    cartRoot.innerHTML = `
      <div class="table-responsive">
        <table class="table align-middle">
          <thead>
            <tr><th></th><th>Товар</th><th>Цена</th><th>Кол-во</th><th>Сумма</th><th></th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="d-flex justify-content-between align-items-center mt-3">
        <div class="fs-4">Итого: <strong>${formatPrice(cart.total)}</strong></div>
        <button class="btn btn-success" disabled title="Будет на следующем шаге">Оформить заказ</button>
      </div>`;
}

async function loadCart() {
    try {
        refreshCartUI(await api("/cart"));
    }
    catch (err) {
        showAlert(errorText(err));
    }
}


// "В корзину" на любой странице (кнопки рисуются динамически, поэтому делегирование на document)
document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".add-to-cart");
    if (!btn) return;

    if (btn.classList.contains("in-cart")) {
        location.href = "/my-cart";
        return;
    }

    btn.disabled = true;
    try {
        const cart = await api("/cart/items", {
            method: "POST",
            body: { product_id: Number(btn.dataset.id), quantity: 1 },
        });
        refreshCartUI(cart);
        showAlert("Товар добавлен в корзину", "success");
    }
    catch (err) {
        showAlert(errorText(err));
    }
    finally {
        btn.disabled = false;
    }
});

if (cartRoot) {
    cartRoot.addEventListener("change", async (e) => {
        const input = e.target.closest(".qty-input");
        if (!input) return;

        const quantity = Number(input.value);
        try {
            if (!Number.isInteger(quantity) || quantity < 1) {
                throw new Error("Количество должно быть целым числом от 1");
            }
            refreshCartUI(await api(`/cart/items/${input.dataset.id}`, {
                method: "PATCH",
                body: { quantity },
            }));
        }
        catch (err) {
            showAlert(errorText(err));
            loadCart(); // возвращаем в инпут реальное значение с сервера
        }
    });

    cartRoot.addEventListener("click", async (e) => {
        const btn = e.target.closest(".remove-item");
        if (!btn) return;
        try {
            refreshCartUI(await api(`/cart/items/${btn.dataset.id}`, { method: "DELETE" }));
        }
        catch (err) {
            showAlert(errorText(err));
        }
    });
}

if (cartCount) loadCart();

// Возврат на страницу из bfcache (Alt + ←): скрипты заново не запускаются,
// поэтому состояние корзины нужно перезапросить вручную
window.addEventListener("pageshow", (e) => {
    if (!e.persisted) return;
    document.getElementById("alerts").innerHTML = ""; // убираем устаревшие уведомления
    if (cartCount) loadCart();
});