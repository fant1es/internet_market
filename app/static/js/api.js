class ApiError extends Error {
  constructor(status, data) {
    super(data?.detail?.toString() || `HTTP ${status}`);
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
  return detail || err.message;
}