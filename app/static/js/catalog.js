const PAGE_SIZE = 12;

// Текущее состояние фильтров
const state = { category: "", search: "", page: 1 };

const productsGrid = document.getElementById("products-grid");
const pagination = document.getElementById("pagination");
const searchInput = document.getElementById("search-input");
const categorySelect = document.getElementById("category-select");

// Откладывает вызов fn, пока пользователь не перестанет вводить на delay мс
function debounce(fn, delay = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function renderProducts(items) {
    if (items.length === 0) {
        productsGrid.innerHTML = `<div class="col-12 text-center text-muted py-5">Ничего не найдено</div>`;
        return;
    }

    // Генерация блока для каждого продукта
    productsGrid.innerHTML = items.map((p) => {
        const inStock = p.stock_quantity > 0;
        return `
        <div class="col">
          <div class="card h-100">
            <div class="bg-light text-center text-muted py-5">Нет фото</div>
            <div class="card-body d-flex flex-column">
              <h6 class="card-title">
                <a href="/product/${p.id}" class="text-decoration-none">${escapeHtml(p.name)}</a>
              </h6>
              <div class="fw-bold mb-3">${formatPrice(p.price)}</div>
              <button class="btn btn-primary btn-sm mt-auto add-to-cart"
                      data-id="${p.id}" ${inStock ? "" : "disabled"}>
                ${inStock ? "В корзину" : "Нет в наличии"}
              </button>
            </div>
          </div>
        </div>`;
    }).join("");
}

function renderPagination(page, pages) {
    if (pages <= 1) {
        pagination.innerHTML = "";
        return;
    }

    let html = `<ul class="pagination justify-content-center">`;
    for (let i = 1; i <= pages; i++) {
        html += `<li class="page-item ${i === page ? "active" : ""}">
                   <button class="page-link" data-page="${i}">${i}</button>
                 </li>`;
    }
    pagination.innerHTML = html + `</ul>`;
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
        renderPagination(data.page, data.pages);
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