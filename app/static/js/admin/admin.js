const LOW_STOCK = 5; // Здесь такое же значение, что и в роутере
const PAGE_SIZE = 20;

const defaultState = () => ({
    search: "", is_active: "", category: "",
    minPrice: "", maxPrice: "", brand: "", stock: "",
    discountOnly: false, sort: "id_asc", page: 1,
});
const state = defaultState();

const productsBody = document.getElementById("products-body");
const pagination = document.getElementById("pagination");
const searchInput = document.getElementById("search-input");
const statusSelect = document.getElementById("status-select");
const categorySelect = document.getElementById("category-select");
const minPriceInput = document.getElementById("min-price");
const maxPriceInput = document.getElementById("max-price");
const rangeMin = document.getElementById("range-min");
const rangeMax = document.getElementById("range-max");
const rangeFill = document.getElementById("range-fill");
const priceLabel = document.getElementById("price-label");
const brandsBox = document.getElementById("brands-box");
const stockSelect = document.getElementById("stock-select");
const sortSelect = document.getElementById("sort-select");
const discountCheck = document.getElementById("discount-only");
const resetBtn = document.getElementById("reset-filters");

// id -> название, чтобы в таблице были имена вместо чисел
const categoryNames = {};
const brandNames = {};

// ---------- Таблица ----------
function renderRow(p) {
    const img = productImageUrl(p);
    const thumb = img
        ? `<img src="${img}" alt="" class="rounded" style="width: 48px; height: 48px; object-fit: cover;">`
        : `<div class="bg-light rounded" style="width: 48px; height: 48px;"></div>`;

    const hasDiscount = p.old_price !== null && Number(p.old_price) > Number(p.price);
    const stockClass = p.stock_quantity === 0 ? "text-danger fw-bold"
        : p.stock_quantity <= LOW_STOCK ? "text-warning fw-bold" : "";

    return `
    <tr class="${p.is_active ? "" : "table-secondary"}">
      <td>${thumb}</td>
      <td>${escapeHtml(p.sku)}</td>
      <td>
        <a href="/admin/product/${p.id}">${escapeHtml(p.name)}</a>
      </td>
      <td>${escapeHtml(categoryNames[p.category_id] ?? "—")}</td>
      <td>${p.brand_id ? escapeHtml(brandNames[p.brand_id] ?? "—") : "—"}</td>
      <td class="text-end text-nowrap">
        ${formatPrice(p.price)}
        ${hasDiscount
          ? `<div class="small text-muted text-decoration-line-through">${formatPrice(p.old_price)}</div>`
          : ""}
      </td>
      <td class="text-end ${stockClass}">${p.stock_quantity}</td>
      <td>
        <span class="badge ${p.is_active ? "bg-success" : "bg-secondary"}">
          ${p.is_active ? t("js.admin.visible") : t("js.admin.hidden")}
        </span>
      </td>
      <td class="text-end text-nowrap">
        <a href="/admin/product/${p.id}/edit" class="btn btn-outline-primary btn-sm">${t("js.admin.edit")}</a>
        <button class="btn btn-outline-secondary btn-sm toggle-active"
                data-id="${p.id}" data-active="${p.is_active}">
          ${p.is_active ? t("js.admin.hide") : t("js.admin.show")}
        </button>
      </td>
    </tr>`;
}

function renderProducts(items) {
    if (items.length === 0) {
        productsBody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-5">${t("js.catalog.no_results")}</td></tr>`;
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
    if (state.minPrice !== "") params.set("min_price", state.minPrice);
    if (state.maxPrice !== "") params.set("max_price", state.maxPrice);
    if (state.brand === "none") params.set("without_brand", "true");
    else if (state.brand) params.set("brand_id", state.brand);
    if (state.stock) params.set("stock", state.stock);
    if (state.discountOnly) params.set("has_discount", "true");
    params.set("sort", state.sort);

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

const reloadFromFirstPage = debounce(() => {
    state.page = 1;
    loadProducts();
});

// ---------- Слайдер цены ----------
// Границы слайдера
let bounds = { min: 0, max: 0 };

// Перерисовывает полосу между ползунками и подпись
function updateSlider() {
    const lo = Number(rangeMin.value);
    const hi = Number(rangeMax.value);
    const span = bounds.max - bounds.min || 1;

    rangeFill.style.left = ((lo - bounds.min) / span) * 100 + "%";
    rangeFill.style.width = ((hi - lo) / span) * 100 + "%";
    priceLabel.textContent = `${lo} — ${hi} BYN`;

    // Если оба ползунка в одной точке, наверх выводим тот, который можно сдвинуть "наружу"
    rangeMin.style.zIndex = lo > (bounds.min + bounds.max) / 2 ? 3 : 1;
}

// Границы берём из самого админского списка (самый дешёвый и самый дорогой товар),
// чтобы в диапазон попадали и скрытые товары. Зависят от категории; выбор цены при этом сбрасывается
async function loadPriceBounds() {
    const base = { page: 1, page_size: 1 };
    if (state.category) base.category = state.category;
    const q = (sort) => new URLSearchParams({ ...base, sort });

    try {
        const [cheap, expensive] = await Promise.all([
            api(`/admin/products?${q("price_asc")}`),
            api(`/admin/products?${q("price_desc")}`),
        ]);
        const empty = cheap.items.length === 0;
        bounds = empty
            ? { min: 0, max: 0 }
            : {
                min: Math.floor(Number(cheap.items[0].price)),
                max: Math.ceil(Number(expensive.items[0].price)),
            };

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
        minPriceInput.placeholder = t("js.catalog.price_from", { value: bounds.min });
        maxPriceInput.placeholder = t("js.catalog.price_to", { value: bounds.max });
        minPriceInput.classList.remove("is-invalid");
        maxPriceInput.classList.remove("is-invalid");
        updateSlider();
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

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
    minPriceInput.classList.remove("is-invalid");
    maxPriceInput.classList.remove("is-invalid");

    updateSlider();
    reloadFromFirstPage();
}
rangeMin.addEventListener("input", onSlide);
rangeMax.addEventListener("input", onSlide);

const onPriceChange = debounce(() => {
    state.minPrice = minPriceInput.value.trim();
    state.maxPrice = maxPriceInput.value.trim();
    state.page = 1;

    // подтягиваем ползунки (браузер сам ограничит значение границами min/max)
    rangeMin.value = state.minPrice !== "" ? state.minPrice : bounds.min;
    rangeMax.value = state.maxPrice !== "" ? state.maxPrice : bounds.max;
    updateSlider();

    const bad = state.minPrice !== "" && state.maxPrice !== ""
        && Number(state.minPrice) > Number(state.maxPrice);
    minPriceInput.classList.toggle("is-invalid", bad);
    maxPriceInput.classList.toggle("is-invalid", bad);
    if (!bad) loadProducts();
});
minPriceInput.addEventListener("input", onPriceChange);
maxPriceInput.addEventListener("input", onPriceChange);

// ---------- Справочники ----------
// Нужны для названий в таблице и для списка категорий
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

// Список брендов в панели зависит от категории. Выбор один (админский эндпоинт принимает один brand_id)
async function loadBrands() {
    const params = new URLSearchParams();
    if (state.category) params.set("category", state.category);

    try {
        const brands = await api(`/brands?${params}`);
        state.brand = "";

        const radio = (id, value, label, checked = false) => `
            <div class="form-check">
              <input class="form-check-input brand-radio" type="radio" name="brand"
                     id="${id}" value="${value}" ${checked ? "checked" : ""}>
              <label class="form-check-label" for="${id}">${label}</label>
            </div>`;

        brandsBox.innerHTML =
            radio("brand-all", "", t("js.admin.brand_all"), true) +
            radio("brand-none", "none", t("js.admin.brand_none")) +
            brands.map((b) => radio(`brand-${b.id}`, b.id, escapeHtml(b.name))).join("");
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

// ---------- Обработчики ----------
searchInput.addEventListener("input", debounce(() => {
    state.search = searchInput.value.trim();
    state.page = 1; // при смене фильтра всегда возвращаемся на первую страницу
    loadProducts();
}));

categorySelect.addEventListener("change", async () => {
    state.category = categorySelect.value;
    state.page = 1;
    // Бренды и границы цены зависят от категории, выбор в них сбрасывается
    await Promise.all([loadPriceBounds(), loadBrands()]);
    loadProducts();
});

brandsBox.addEventListener("change", (e) => {
    if (!e.target.classList.contains("brand-radio")) return;
    state.brand = e.target.value;
    state.page = 1;
    loadProducts();
});

// Одинаковые по логике селекты: ключ состояния берём из словаря
for (const [el, key] of [[statusSelect, "is_active"], [stockSelect, "stock"], [sortSelect, "sort"]]) {
    el.addEventListener("change", () => {
        state[key] = el.value;
        state.page = 1;
        loadProducts();
    });
}

discountCheck.addEventListener("change", () => {
    state.discountOnly = discountCheck.checked;
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

resetBtn.addEventListener("click", async () => {
    Object.assign(state, defaultState());
    searchInput.value = "";
    categorySelect.value = "";
    statusSelect.value = "";
    stockSelect.value = "";
    sortSelect.value = state.sort;
    discountCheck.checked = false;
    await Promise.all([loadPriceBounds(), loadBrands()]);
    loadProducts();
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
    await Promise.all([loadBrands(), loadPriceBounds()]);
    await loadProducts();
})();