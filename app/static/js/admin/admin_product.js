const card = document.getElementById("product-card");
// id товара пришёл из роута через data-атрибут (см. admin/product.html)
const productId = card.dataset.id;

// Названия категории и бренда нужны при каждой перерисовке (например, после скрытия товара)
let categoryName = "—";
let brandName = "—";

function renderCard(p) {
    const img = productImageUrl(p);
    const inStock = p.stock_quantity > 0;

    document.title = `Админка: ${p.name}`;
    card.innerHTML = `
      <div class="row g-4">
        <div class="col-md-5">
          ${img
            ? `<img src="${img}" alt="${escapeHtml(p.name)}" class="img-fluid rounded">`
            : `<div class="bg-light text-center text-muted py-5 rounded">Нет фото</div>`}
        </div>

        <div class="col-md-7">
          <div class="d-flex align-items-start gap-2 mb-1">
            <h1 class="h3 mb-0">${escapeHtml(p.name)}</h1>
            <span class="badge ${p.is_active ? "bg-success" : "bg-secondary"} mt-1">
              ${p.is_active ? "Виден" : "Скрыт"}
            </span>
          </div>
          <div class="text-muted mb-3">Артикул: ${escapeHtml(p.sku)}</div>

          <div class="fs-3 fw-bold mb-3">
            ${formatPrice(p.price)}
            ${p.old_price ? `<s class="fs-6 fw-normal text-muted ms-2">${formatPrice(p.old_price)}</s>` : ""}
          </div>

          <dl class="row mb-3">
            <dt class="col-sm-3">Категория</dt>
            <dd class="col-sm-9">${escapeHtml(categoryName)}</dd>
            <dt class="col-sm-3">Бренд</dt>
            <dd class="col-sm-9">${escapeHtml(brandName)}</dd>
            <dt class="col-sm-3">В наличии</dt>
            <dd class="col-sm-9 ${inStock ? "" : "text-danger"}">
              ${inStock ? `${p.stock_quantity} шт.` : "Нет в наличии"}
            </dd>
          </dl>

          <h2 class="h6">Описание</h2>
          <p style="white-space: pre-line;">${escapeHtml(p.description ?? "Описание отсутствует")}</p>

          <div class="d-flex gap-2 mt-4">
            <a href="/admin/product/${p.id}/edit" class="btn btn-primary">Изменить</a>
            <button id="toggle-active" class="btn btn-outline-secondary" data-active="${p.is_active}">
              ${p.is_active ? "Скрыть" : "Показать"}
            </button>
          </div>
        </div>
      </div>`;
}

async function loadProduct() {
    try {
        const [product, categories, brands] = await Promise.all([
            api(`/admin/products/${productId}`),
            api("/categories"),
            api("/brands"),
        ]);

        categoryName = categories.find((c) => c.id === product.category_id)?.name ?? "—";
        brandName = product.brand_id
            ? (brands.find((b) => b.id === product.brand_id)?.name ?? "—")
            : "—";

        renderCard(product);
    }
    catch (err) {
        if (err.status === 404) {
            card.innerHTML = `<div class="alert alert-warning">Товар не найден</div>`;
        }
        else {
            showAlert(errorText(err));
        }
    }
}

// Кнопка пересоздаётся при каждой отрисовке, поэтому обработчик висит на контейнере
card.addEventListener("click", async (e) => {
    const btn = e.target.closest("#toggle-active");
    if (!btn) return;

    btn.disabled = true;
    try {
        const isActiveNow = btn.dataset.active === "true";
        // Сервер возвращает обновлённый товар: перерисовываем карточку без повторной загрузки
        const updated = await api(`/admin/products/${productId}/active`, {
            method: "PATCH",
            body: { is_active: !isActiveNow },
        });
        renderCard(updated);
    }
    catch (err) {
        showAlert(errorText(err));
        btn.disabled = false;
    }
});

loadProduct();