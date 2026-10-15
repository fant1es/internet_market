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

// Старая цена показывается, только если она действительно выше текущей
function oldPriceOf(p) {
    const old = Number(p.old_price);
    return old > Number(p.price) ? old : null;
}

// Деньги считаем с округлением до копеек, чтобы не тянуть хвосты вида 0.30000000000000004
function roundMoney(x) {
    return Math.round(x * 100) / 100;
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

    // Итоги: со скидкой (с сервера), без скидки и разница
    const total = Number(cart.total);
    const totalOld = roundMoney(cart.items.reduce(
        (sum, { product: p, quantity }) => sum + (oldPriceOf(p) ?? Number(p.price)) * quantity, 0
    ));
    const discount = roundMoney(totalOld - total);

    const rows = cart.items.map(({ id, product: p, quantity, subtotal }) => {
        const imageUrl = productImageUrl(p);
        const oldPrice = oldPriceOf(p);
        return `
        <div class="d-flex gap-3 p-3 border-bottom cart-item">
          <a href="/product/${p.id}" class="flex-shrink-0 bg-light rounded d-flex align-items-center justify-content-center"
             style="width: 140px; height: 140px;">
            ${imageUrl
                ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(p.name)}"
                        class="w-100 h-100 object-fit-contain rounded">`
                : `<span class="text-muted small">Нет фото</span>`}
          </a>

          <div class="flex-grow-1 d-flex flex-column flex-md-row gap-3">
            <div class="flex-grow-1">
              <a href="/product/${p.id}" class="fs-5 fw-semibold text-decoration-none">${escapeHtml(p.name)}</a>
              <div class="mt-2">
                <span class="fs-5 fw-bold">${formatPrice(p.price)}</span>
                ${oldPrice ? `<s class="text-muted ms-2">${formatPrice(oldPrice)}</s>` : ""}
                <span class="text-muted small">за шт.</span>
              </div>
              <div class="text-muted small mt-1">В наличии: ${p.stock_quantity} шт.</div>
            </div>

            <div class="d-flex flex-md-column align-items-md-end justify-content-between gap-2">
              <input type="number" class="form-control qty-input" style="width: 100px"
                     data-id="${id}" value="${quantity}" min="1" max="${p.stock_quantity}">
              <div class="text-md-end">
                <div class="fs-5 fw-bold text-nowrap">${formatPrice(subtotal)}</div>
                ${oldPrice
                    ? `<s class="text-muted small text-nowrap">${formatPrice(roundMoney(oldPrice * quantity))}</s>`
                    : ""}
              </div>
              <button class="btn btn-outline-danger btn-sm remove-item" data-id="${id}">Удалить</button>
            </div>
          </div>
        </div>`;
    }).join("");

    cartRoot.innerHTML = `
      <div class="row g-4 align-items-start">
        <div class="col-lg-8">
          <div class="card">
            <div class="card-header fw-semibold">Товары в корзине (${cart.total_quantity} шт.)</div>
            <div>${rows}</div>
          </div>
        </div>

        <div class="col-lg-4">
          <div class="card position-sticky" style="top: 1rem;">
            <div class="card-header fw-semibold">Итого</div>
            <div class="card-body">
              <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Сумма без скидки</span>
                <span class="text-nowrap">${formatPrice(totalOld)}</span>
              </div>
              <div class="d-flex justify-content-between mb-2">
                <span class="text-muted">Скидка</span>
                <span class="text-nowrap ${discount > 0 ? "text-danger" : ""}">
                  ${discount > 0 ? "−" : ""}${formatPrice(discount)}
                </span>
              </div>
              <hr>
              <div class="d-flex justify-content-between align-items-baseline mb-3">
                <span class="fs-5">К оплате</span>
                <strong class="fs-4 text-nowrap">${formatPrice(total)}</strong>
              </div>
              <button class="btn btn-success w-100" disabled title="Будет на следующем шаге">Оформить заказ</button>
            </div>
          </div>
        </div>
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