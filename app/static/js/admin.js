const PAGE_SIZE = 20;

// Текущее состояние фильтров. is_active хранится строкой: "" (все), "true" или "false"
const state = { search: "", is_active: "", category: "", page: 1 };

const productsBody = document.getElementById("products-body");
const pagination = document.getElementById("pagination");
const searchInput = document.getElementById("search-input");
const statusSelect = document.getElementById("status-select");
const categorySelect = document.getElementById("category-select");

// id -> название, чтобы в таблице были имена вместо чисел
const categoryNames = {};
const brandNames = {};

function renderRow(p) {
    const img = productImageUrl(p);
    const thumb = img
        ? `<img src="${img}" alt="" class="rounded" style="width: 48px; height: 48px; object-fit: cover;">`
        : `<div class="bg-light rounded" style="width: 48px; height: 48px;"></div>`;

    return `
    <tr class="${p.is_active ? "" : "table-secondary"}">
      <td>${thumb}</td>
      <td>${escapeHtml(p.sku)}</td>
      <td>${escapeHtml(p.name)}</td>
      <td>${escapeHtml(categoryNames[p.category_id] ?? "—")}</td>
      <td>${p.brand_id ? escapeHtml(brandNames[p.brand_id] ?? "—") : "—"}</td>
      <td class="text-end">${formatPrice(p.price)}</td>
      <td class="text-end">${p.stock_quantity}</td>
      <td>
        <span class="badge ${p.is_active ? "bg-success" : "bg-secondary"}">
          ${p.is_active ? "Виден" : "Скрыт"}
        </span>
      </td>
      <td class="text-end text-nowrap">
        <a href="/admin/product/${p.id}" class="btn btn-outline-primary btn-sm">Изменить</a>
        <button class="btn btn-outline-secondary btn-sm toggle-active"
                data-id="${p.id}" data-active="${p.is_active}">
          ${p.is_active ? "Скрыть" : "Показать"}
        </button>
      </td>
    </tr>`;
}

function renderProducts(items) {
    if (items.length === 0) {
        productsBody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-5">Ничего не найдено</td></tr>`;
        return;
    }
    productsBody.innerHTML = items.map(renderRow).join("");
}

// Номер последнего запроса: защита от гонки, когда старый ответ приходит позже нового
let lastRequestId = 0;

async function loadProducts() {
    const requestId = ++lastRequestId;

    const params = new URLSearchParams({ page: state.page, page_size: PAGE_SIZE });
    if (state.search) params.set("search", state.search);
    if (state.category) params.set("category", state.category);
    if (state.is_active) params.set("is_active", state.is_active);

    try {
        const data = await api(`/admin/products?${params}`);
        if (requestId !== lastRequestId) return; // пришёл устаревший ответ, игнорируем

        // Страница опустела (например, скрыли последний товар на последней странице): возвращаемся назад
        if (data.items.length === 0 && state.page > 1) {
            state.page = Math.max(data.pages, 1);
            return loadProducts();
        }

        renderProducts(data.items);
        renderPagination(pagination, data.page, data.pages);
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

// Справочники нужны, чтобы показывать названия + для фильтра по категории
async function loadDictionaries() {
    try {
        const [categories, brands] = await Promise.all([api("/categories"), api("/brands")]);

        categories.forEach((c) => { categoryNames[c.id] = c.name; });
        brands.forEach((b) => { brandNames[b.id] = b.name; });

        categorySelect.innerHTML += categories
            .map((c) => `<option value="${escapeHtml(c.slug)}">${escapeHtml(c.name)}</option>`)
            .join("");
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

// --- Обработчики ---
searchInput.addEventListener("input", debounce(() => {
    state.search = searchInput.value.trim();
    state.page = 1; // при смене фильтра всегда возвращаемся на первую страницу
    loadProducts();
}));

statusSelect.addEventListener("change", () => {
    state.is_active = statusSelect.value;
    state.page = 1;
    loadProducts();
});

categorySelect.addEventListener("change", () => {
    state.category = categorySelect.value;
    state.page = 1;
    loadProducts();
});

pagination.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-page]");
    if (!btn) return;
    state.page = Number(btn.dataset.page);
    loadProducts();
    window.scrollTo({ top: 0, behavior: "smooth" });
});

// Скрыть / показать: один обработчик на всю таблицу (строки перерисовываются, поэтому делегирование)
productsBody.addEventListener("click", async (e) => {
    const btn = e.target.closest(".toggle-active");
    if (!btn) return;

    btn.disabled = true;
    try {
        const isActiveNow = btn.dataset.active === "true";
        await api(`/admin/products/${btn.dataset.id}/active`, {
            method: "PATCH",
            body: { is_active: !isActiveNow },
        });
        // Перезагружаем текущую страницу: если включён фильтр по статусу, строка сама исчезнет из списка
        await loadProducts();
    }
    catch (err) {
        showAlert(errorText(err));
        btn.disabled = false;
    }
});

// Сначала справочники, потом товары: иначе в первой отрисовке вместо названий будут прочерки
(async () => {
    await loadDictionaries();
    await loadProducts();
})();