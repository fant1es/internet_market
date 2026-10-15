// Одна страница обслуживает два справочника, все отличия в этом конфиге
const CONFIG = {
    brands: {
        url: "/admin/brands",
        hasActive: true,   // у брендов есть скрытие, у категорий нет
        createTitle: "Новый бренд",
        editTitle: "Редактирование бренда",
    },
    categories: {
        url: "/admin/categories",
        hasActive: false,
        createTitle: "Новая категория",
        editTitle: "Редактирование категории",
    },
};

const TRANSLIT = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i", й: "y",
    к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f",
    х: "h", ц: "ts", ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya",
};

// "Умный дом" -> "umnyy-dom"
function slugify(text) {
    return text.toLowerCase()
        .split("").map((ch) => TRANSLIT[ch] ?? ch).join("")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

let kind = "brands";   // активная вкладка
let items = [];        // загруженный список активной вкладки
let editingId = null;  // null: создаём, число: редактируем
let slugTouched = false;  // Если админ не правил slug руками, подставляем его из названия

const tabs = document.getElementById("ref-tabs");
const addBtn = document.getElementById("add-btn");
const statusCol = document.getElementById("status-col");
const body = document.getElementById("ref-body");

const modalEl = document.getElementById("ref-modal");
const modal = new bootstrap.Modal(modalEl);
const form = document.getElementById("ref-form");
const modalTitle = document.getElementById("ref-modal-title");
const modalError = document.getElementById("ref-modal-error");
const nameInput = document.getElementById("ref-name");
const slugInput = document.getElementById("ref-slug");
const activeWrap = document.getElementById("ref-active-wrap");
const activeInput = document.getElementById("ref-active");
const saveBtn = document.getElementById("ref-save");

function renderTable() {
    const cfg = CONFIG[kind];
    statusCol.classList.toggle("d-none", !cfg.hasActive);

    if (items.length === 0) {
        body.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-5">Пока ничего нет</td></tr>`;
        return;
    }

    body.innerHTML = items.map((item) => `
    <tr class="${cfg.hasActive && !item.is_active ? "table-secondary" : ""}">
      <td>${escapeHtml(item.name)}</td>
      <td><code>${escapeHtml(item.slug)}</code></td>
      <td class="text-end">${item.products_count}</td>
      ${cfg.hasActive ? `
      <td>
        <span class="badge ${item.is_active ? "bg-success" : "bg-secondary"}">
          ${item.is_active ? "Виден" : "Скрыт"}
        </span>
      </td>` : ""}
      <td class="text-end text-nowrap">
        <button class="btn btn-outline-primary btn-sm" data-action="edit" data-id="${item.id}">Изменить</button>
        ${cfg.hasActive ? `
        <button class="btn btn-outline-secondary btn-sm" data-action="toggle" data-id="${item.id}">
          ${item.is_active ? "Скрыть" : "Показать"}
        </button>` : ""}
        <button class="btn btn-outline-danger btn-sm" data-action="delete" data-id="${item.id}">Удалить</button>
      </td>
    </tr>`).join("");
}

async function load() {
    const requestKind = kind;
    try {
        const data = await api(CONFIG[requestKind].url);
        if (requestKind !== kind) return;   // пока грузилось, переключили вкладку: ответ устарел
        items = data;
        renderTable();
    }
    catch (err) {
        showAlert(errorText(err));
    }
}

function openModal(item = null) {
    const cfg = CONFIG[kind];

    editingId = item ? item.id : null;
    modalTitle.textContent = item ? cfg.editTitle : cfg.createTitle;
    nameInput.value = item?.name ?? "";
    slugInput.value = item?.slug ?? "";
    slugTouched = item !== null;   // у существующей записи slug не меняем сам

    activeWrap.classList.toggle("d-none", !cfg.hasActive);
    activeInput.checked = item ? item.is_active : true;

    modalError.classList.add("d-none");
    form.classList.remove("was-validated");
    modal.show();
}

// --- Обработчики ---
tabs.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-kind]");
    if (!btn || btn.dataset.kind === kind) return;

    kind = btn.dataset.kind;
    tabs.querySelectorAll(".nav-link").forEach((el) => {
        el.classList.toggle("active", el === btn);
    });
    items = [];
    renderTable();
    load();
});

addBtn.addEventListener("click", () => openModal());

modalEl.addEventListener("shown.bs.modal", () => nameInput.focus());

nameInput.addEventListener("input", () => {
    if (!slugTouched) slugInput.value = slugify(nameInput.value);
});

slugInput.addEventListener("input", () => {
    slugTouched = true;
    // Пока вводят: заглавные в строчные, пробелы в дефисы
    slugInput.value = slugInput.value.toLowerCase().replace(/\s+/g, "-");
});

form.addEventListener("submit", async (e) => {
    e.preventDefault();

    form.classList.add("was-validated");
    if (!form.checkValidity()) return;

    const cfg = CONFIG[kind];
    const payload = { name: nameInput.value.trim(), slug: slugInput.value.trim() };
    if (cfg.hasActive) payload.is_active = activeInput.checked;

    saveBtn.disabled = true;
    try {
        if (editingId === null) {
            await api(cfg.url, { method: "POST", body: payload });
        }
        else {
            await api(`${cfg.url}/${editingId}`, { method: "PUT", body: payload });
        }
        modal.hide();
        await load();
    }
    catch (err) {
        modalError.textContent = errorText(err);
        modalError.classList.remove("d-none");
    }
    finally {
        saveBtn.disabled = false;
    }
});

// Кнопки в строках пересоздаются при каждой отрисовке, поэтому один обработчик на всю таблицу
body.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;

    const cfg = CONFIG[kind];
    const id = Number(btn.dataset.id);
    const item = items.find((i) => i.id === id);
    if (!item) return;

    if (btn.dataset.action === "edit") {
        openModal(item);
        return;
    }

    if (btn.dataset.action === "delete" && !confirm(`Удалить «${item.name}»?`)) return;

    btn.disabled = true;
    try {
        if (btn.dataset.action === "toggle") {
            await api(`${cfg.url}/${id}/active`, { method: "PATCH", body: { is_active: !item.is_active } });
        }
        else {
            await api(`${cfg.url}/${id}`, { method: "DELETE" });
            showAlert("Удалено", "success");
        }
        await load();
    }
    catch (err) {
        showAlert(errorText(err));   // например, 409: к бренду ещё привязаны товары
        btn.disabled = false;
    }
});

load();