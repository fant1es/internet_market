const PAGE_SIZE = 12;

// Текущее состояние фильтров
const state = { category: "", search: "", page: 1 };

const productsGrid = document.getElementById("products-grid");
const pagination = document.getElementById("pagination");
const searchInput = document.getElementById("search-input");
const categorySelect = document.getElementById("category-select");

function renderProducts(items) {
    if (items.length === 0) {
        productsGrid.innerHTML = `<div class="col-12 text-center text-muted py-5">Ничего не найдено</div>`;
        return;
    }

    // Генерация блока для каждого продукта
    productsGrid.innerHTML = items.map((p) => {
        const inStock = p.stock_quantity > 0;
        const imageUrl = productImageUrl(p);
        return `
        <div class="col">
          <div class="card h-100">
            <a href="/product/${p.id}" class="ratio ratio-4x3 bg-light text-decoration-none">
                ${imageUrl
                ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(p.name)}"
                    class="card-img-top object-fit-contain" loading="lazy">`
                : `<div class="d-flex align-items-center justify-content-center text-muted">Нет фото</div>`}
            </a>
            <div class="card-body d-flex flex-column">
              <h6 class="card-title">
                <a href="/product/${p.id}" class="text-decoration-none">${escapeHtml(p.name)}</a>
              </h6>
              <div class="fw-bold mb-3">${formatPrice(p.price)}</div>
              ${inStock
                ? `<button class="btn btn-primary btn-sm mt-auto add-to-cart"
                           data-id="${p.id}">В корзину</button>`
                : `<button class="btn btn-secondary btn-sm mt-auto" disabled>Нет в наличии</button>`}
            </div>
          </div>
        </div>`;
    }).join("");

    syncCartButtons();
}

// Номер последнего запроса: защита от гонки, когда старый ответ приходит позже нового
let lastRequestId = 0;

async function loadProducts() {
    const requestId = ++lastRequestId;

    const params = new URLSearchParams({ page: state.page, page_size: PAGE_SIZE });
    if (state.category) params.set("category", state.category);
    if (state.search) params.set("search", state.search);

    try {
        const data = await api(`/products?${params}`);
        if (requestId !== lastRequestId) return; // пришёл устаревший ответ, игнорируем

        renderProducts(data.items);
        renderPagination(pagination, data.page, data.pages);
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

async function loadCategories() {
    try {
        const categories = await api("/categories");
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

categorySelect.addEventListener("change", () => {
    state.category = categorySelect.value;
    state.page = 1;
    loadProducts();
});

// Делегирование: один обработчик на весь блок вместо кнопки на каждую страницу
pagination.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-page]");
    if (!btn) return;
    state.page = Number(btn.dataset.page);
    loadProducts();
    window.scrollTo({ top: 0, behavior: "smooth" });
});

loadCategories();
loadProducts();