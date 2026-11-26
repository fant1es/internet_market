// Перевод для JS: словарь кладёт в window.I18N шаблон base.html
function t(key, params) {
  let s = window.I18N?.[key] ?? key;
  if (params) s = s.replace(/\{(\w+)\}/g, (m, k) => params[k] ?? m);
  return s;
}

class ApiError extends Error {
  constructor(status, data) {
      // При передаче обьекта нужно обрабатывать его, чтобы не было сообщения [object Object]
      const detail = data?.detail;
      super(typeof detail === "string" ? detail : detail?.message || `HTTP ${status}`);
      this.status = status;
      this.data = data;
  }
}

async function api(url, { method = "GET", body, formData } = {}) {
  const opts = { method, headers: {} };

  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  } else if (formData) {
    opts.body = formData;
  }

  const res = await fetch(url, opts);
  const data = res.status === 204 ? null : await res.json().catch(() => null);

  if (res.status === 401 && !location.pathname.startsWith("/login")) {
    location.href = "/login";
    throw new ApiError(401, data);
  }

  if (!res.ok) {
    throw new ApiError(res.status, data);
  }

  return data;
}

function showAlert(message, type = "danger") {
  const box = document.getElementById("alerts");
  box.innerHTML = `<div class="alert alert-${type}">${escapeHtml(message)}</div>`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function errorText(err) {
  const detail = err.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map(e => e.msg).join("; ");
  }
  // Отдельная обработка для обьектов
  if (detail && typeof detail === "object") {
    return detail.message || err.message;
  }
  return detail || err.message;
}

function formatPrice(price) {
    const locale = window.LANG === "en" ? "en-US" : "ru-RU";
    return Number(price).toLocaleString(locale) + " BYN";
}

// Откладывает вызов fn, пока пользователь не перестанет вводить на delay мс
function debounce(fn, delay = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

// Рисует кнопки страниц в контейнере. Клики обрабатывает вызывающий код (кнопки, помеченные data-page)
function renderPagination(container, page, pages) {
    if (pages <= 1) {
        container.innerHTML = "";
        return;
    }

    let html = `<ul class="pagination justify-content-center">`;
    for (let i = 1; i <= pages; i++) {
        html += `<li class="page-item ${i === page ? "active" : ""}">
                   <button class="page-link" data-page="${i}">${i}</button>
                 </li>`;
    }
    container.innerHTML = html + `</ul>`;
}

// Адрес картинки товара. В БД лежит путь относительно /static
function productImageUrl(product) {
    return product.image_path ? `/static/${product.image_path}` : null;
}

// Подсвечивает поле и пишет текст ошибки в соседний .invalid-feedback
function setFieldError(input, message) {
    input.classList.add("is-invalid");
    const feedback = input.parentElement.querySelector(".invalid-feedback");
    if (feedback) feedback.textContent = message;
}

function clearFieldErrors(form) {
    form.querySelectorAll(".is-invalid").forEach((i) => i.classList.remove("is-invalid"));
    form.classList.remove("was-validated");
}

// Привязывает ошибки 422 к полям формы. Возвращает true, если хоть одна нашла своё поле
function showFieldErrors(form, detail, keys) {
    let found = false;
    for (const d of detail) {
        const name = d.loc?.[d.loc.length - 1];
        const input = form.elements.namedItem(String(name));
        if (!input || !keys.includes(input.name)) continue;

        // Убираем префикс от pydantic "Value error, "
        setFieldError(input, d.msg.replace(/^Value error, /, ""));
        found = true;
    }
    return found;
}


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


function renderAttributes(attrs) {
    if (!attrs.length) return "";

    const rows = attrs.map((a) => `
        <div class="row py-2 border-bottom">
          <div class="col-sm-6 col-md-5">${escapeHtml(a.name)}</div>
          <div class="col-sm-6 col-md-7 fw-bold">${escapeHtml(a.value)}</div>
        </div>`).join("");

    return `
      <section class="mt-5">
        <h2 class="h4 mb-3">${t("js.product.attributes")}</h2>
        ${rows}
      </section>`;
}