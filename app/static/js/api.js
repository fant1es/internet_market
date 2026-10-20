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
    // price приходит строкой ("29990.00"), для форматирования приводим к числу
    return Number(price).toLocaleString("ru-RU") + " BYN";
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