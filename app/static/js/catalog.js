const PAGE_SIZE = 12;

// Переходим на функцию с созданием словаря из-за brands
const defaultState = () => ({
    category: "", search: "", minPrice: "", maxPrice: "",
    sort: "newest", brands: [], discountOnly: false, page: 1,
});
const state = defaultState();

const minPriceInput = document.getElementById("min-price");
const maxPriceInput = document.getElementById("max-price");
const rangeMin = document.getElementById("range-min");
const rangeMax = document.getElementById("range-max");
const rangeFill = document.getElementById("range-fill");
const priceLabel = document.getElementById("price-label");
const sortSelect = document.getElementById("sort-select");
const resetBtn = document.getElementById("reset-filters");
const productsGrid = document.getElementById("products-grid");
const pagination = document.getElementById("pagination");
const searchInput = document.getElementById("search-input");
const categorySelect = document.getElementById("category-select");
const brandsBox = document.getElementById("brands-box");
const discountCheck = document.getElementById("discount-only");

// Границы слайдера
let bounds = { min: 0, max: 0 };

// Перерисовывает синюю полосу между ползунками и подпись
function updateSlider() {
    const lo = Number(rangeMin.value);
    const hi = Number(rangeMax.value);
    const span = bounds.max - bounds.min || 1;

    rangeFill.style.left = ((lo - bounds.min) / span) * 100 + "%";
    rangeFill.style.width = ((hi - lo) / span) * 100 + "%";
    priceLabel.textContent = `${lo} — ${hi} BYN`;

    // Если оба ползунка в одной точке, наверх выводим тот, который можно сдвинуть "наружу",
    // иначе один из них будет невозможно схватить
    rangeMin.style.zIndex = lo > (bounds.min + bounds.max) / 2 ? 3 : 1;
}

// Границы зависят от категории - выбор цены при этом сбрасывается
async function loadPriceBounds() {
    const params = new URLSearchParams();
    if (state.category) params.set("category", state.category);

    try {
        const data = await api(`/products/price-range?${params}`);
        const empty = data.price_min === null;
        bounds = empty
            ? { min: 0, max: 0 }
            : { min: Math.floor(Number(data.price_min)), max: Math.ceil(Number(data.price_max)) };

        for (const r of [rangeMin, rangeMax]) {
            r.min = bounds.min;
            r.max = bounds.max;
            r.step = 1;
            r.disabled = empty;
        }
        rangeMin.value = bounds.min;
        rangeMax.value = bounds.max;

        state.minPrice = "";
        state.maxPrice = "";
        minPriceInput.value = "";
        maxPriceInput.value = "";
        minPriceInput.placeholder = `от ${bounds.min}`;
        maxPriceInput.placeholder = `до ${bounds.max}`;
        updateSlider();
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

const reloadFromFirstPage = debounce(() => {
    state.page = 1;
    loadProducts();
});

function onSlide(e) {
    let lo = Number(rangeMin.value);
    let hi = Number(rangeMax.value);

    // Ползунки не должны перескакивать друг через друга
    if (lo > hi) {
        if (e.target === rangeMin) lo = hi; else hi = lo;
        rangeMin.value = lo;
        rangeMax.value = hi;
    }

    // Если ползунок стоит на краю, фильтр по этой стороне не нужен
    state.minPrice = lo > bounds.min ? String(lo) : "";
    state.maxPrice = hi < bounds.max ? String(hi) : "";
    minPriceInput.value = state.minPrice;
    maxPriceInput.value = state.maxPrice;

    updateSlider();
    reloadFromFirstPage();
}

rangeMin.addEventListener("input", onSlide);
rangeMax.addEventListener("input", onSlide);

function renderProducts(items) {
    if (items.length === 0) {
        productsGrid.innerHTML = `<div class="col-12 text-center text-muted py-5">Ничего не найдено</div>`;
        return;
    }

    // Генерация блока для каждого продукта
    productsGrid.innerHTML = items.map((p) => {
        const inStock = p.stock_quantity > 0;
        const imageUrl = productImageUrl(p);
        const hasDiscount = p.old_price !== null && Number(p.old_price) > Number(p.price);
        const discountPercent = hasDiscount ?
            Math.round((1 - Number(p.price) / Number(p.old_price)) * 100) : 0;
        return `
        <div class="col">
          <div class="card h-100">
            <a href="/product/${p.id}" class="ratio ratio-4x3 bg-light text-decoration-none">
                ${imageUrl
                ? `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(p.name)}"
                    class="card-img-top object-fit-contain" loading="lazy">`
                : `<div class="d-flex align-items-center justify-content-center text-muted">Нет фото</div>`}
            </a>
            ${hasDiscount
                ? `<span class="badge bg-danger position-absolute top-0 start-0 m-2">−${discountPercent}%</span>`
                : ""}
            <div class="card-body d-flex flex-column">
              <h6 class="card-title">
                <a href="/product/${p.id}" class="text-decoration-none">${escapeHtml(p.name)}</a>
              </h6>
              <div class="mb-3">
                <span class="fw-bold">${formatPrice(p.price)}</span>
                ${hasDiscount
                  ? `<span class="text-muted text-decoration-line-through small ms-2">${formatPrice(p.old_price)}</span>`
                  : ""}
              </div>
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
    if (state.minPrice !== "") params.set("min_price", state.minPrice);
    if (state.maxPrice !== "") params.set("max_price", state.maxPrice);
    params.set("sort", state.sort);

    state.brands.forEach((b) => params.append("brand", b)); // ?brand=a&brand=b
    if (state.discountOnly) params.set("has_discount", "true");

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

// Проверка диапазона на клиенте, чтобы не слать заведомо плохой запрос
function priceRangeValid() {
    const bad = state.minPrice !== "" && state.maxPrice !== ""
        && Number(state.minPrice) > Number(state.maxPrice);
    minPriceInput.classList.toggle("is-invalid", bad);
    maxPriceInput.classList.toggle("is-invalid", bad);
    return !bad;
}

const onPriceChange = debounce(() => {
    state.minPrice = minPriceInput.value.trim();
    state.maxPrice = maxPriceInput.value.trim();
    state.page = 1;

    // подтягиваем ползунки (браузер сам ограничит значение границами min/max)
    rangeMin.value = state.minPrice !== "" ? state.minPrice : bounds.min;
    rangeMax.value = state.maxPrice !== "" ? state.maxPrice : bounds.max;
    updateSlider();

    if (priceRangeValid()) loadProducts();
});
minPriceInput.addEventListener("input", onPriceChange);
maxPriceInput.addEventListener("input", onPriceChange);

sortSelect.addEventListener("change", () => {
    state.sort = sortSelect.value;
    state.page = 1;
    loadProducts();
});

resetBtn.addEventListener("click", async () => {
    Object.assign(state, defaultState());   // brands становится новым пустым массивом
    searchInput.value = "";
    categorySelect.value = "";
    sortSelect.value = state.sort;
    discountCheck.checked = false;
    priceRangeValid();
    await Promise.all([loadPriceBounds(), loadBrands()]);
    loadProducts();
});

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

categorySelect.addEventListener("change", async () => {
    state.category = categorySelect.value;
    state.page = 1;
    await Promise.all([loadPriceBounds(), loadBrands()]);
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

// Т.к. бренды зависят от категории, то при её смене список и выбранные бренды обновляются
async function loadBrands() {
    const params = new URLSearchParams();
    if (state.category) params.set("category", state.category);

    try {
        const brands = await api(`/brands?${params}`);
        state.brands = [];
        brandsBox.innerHTML = brands.length
            ? brands.map((b) => `
                <div class="form-check mb-0">
                  <input class="form-check-input brand-check" type="checkbox"
                         id="brand-${escapeHtml(b.slug)}" value="${escapeHtml(b.slug)}">
                  <label class="form-check-label" for="brand-${escapeHtml(b.slug)}">${escapeHtml(b.name)}</label>
                </div>`).join("")
            : `<span class="text-muted small">Нет брендов</span>`;
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

// Делегируем один обработчик на весь блок брендов
brandsBox.addEventListener("change", (e) => {
    if (!e.target.classList.contains("brand-check")) return;
    state.brands = [...brandsBox.querySelectorAll(".brand-check:checked")].map((c) => c.value);
    state.page = 1;
    loadProducts();
});

discountCheck.addEventListener("change", () => {
    state.discountOnly = discountCheck.checked;
    state.page = 1;
    loadProducts();
});

// Шаг цены на один щелчок колеса (поставь своё значение)
const WHEEL_STEP = 15;

function enableWheelPrice(input, fallback) {
    input.addEventListener("wheel", (e) => {
        if (document.activeElement !== input) return; // без фокуса листаем страницу как обычно
        e.preventDefault();

        const direction = e.deltaY < 0 ? 1 : -1; // вверх = больше
        const current = input.value !== "" ? Number(input.value) : fallback();
        const next = current + direction * WHEEL_STEP;

        // Не выходим за границы и не даём "от" обогнать "до"
        const lo = input === maxPriceInput && minPriceInput.value !== "" ? Number(minPriceInput.value) : bounds.min;
        const hi = input === minPriceInput && maxPriceInput.value !== "" ? Number(maxPriceInput.value) : bounds.max;
        input.value = Math.min(Math.max(next, lo), hi);

        onPriceChange();
    }, { passive: false });
}

enableWheelPrice(minPriceInput, () => bounds.min);
enableWheelPrice(maxPriceInput, () => bounds.max);

loadCategories();
loadBrands();
loadPriceBounds();
loadProducts();