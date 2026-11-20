// В IIFE, чтобы не конфликтовать с глобальными const из product.js
(() => {
    const box = document.getElementById("reviews");
    if (!box) return;

    const pid = box.dataset.productId;
    const userId = box.dataset.userId ? Number(box.dataset.userId) : null;
    const isAdmin = box.dataset.isAdmin === "true";
    const PAGE_SIZE = 10;
    const FIELDS = ["rating", "title", "body", "pros", "cons"];

    const state = {
        page: 1,
        items: [],
        can: null,      // ответ /can-review
        editing: null,  // отзыв, который сейчас редактируется
    };

    box.innerHTML = `
      <h2 class="h4 mb-3">Отзывы</h2>
      <div id="reviews-summary" class="mb-3"></div>
      <div id="reviews-form" class="mb-4"></div>
      <div id="reviews-list"></div>
      <div id="reviews-pagination" class="mt-3"></div>`;

    const summaryBox = box.querySelector("#reviews-summary");
    const formBox = box.querySelector("#reviews-form");
    const listBox = box.querySelector("#reviews-list");
    const pagBox = box.querySelector("#reviews-pagination");

    // --- Отрисовка --------------------------------------------
    function renderSummary(summary) {
        summaryBox.innerHTML = summary.average === null
            ? `<span class="text-muted">Пока нет отзывов</span>`
            : `<span class="fs-4 fw-bold">★ ${Number(summary.average).toFixed(1)}</span>
               <span class="text-muted ms-2">Отзывов: ${summary.count}</span>`;
    }

    function renderReview(r) {
        const own = r.user.id === userId;
        const date = new Date(r.created_at).toLocaleDateString("ru-RU");
        const edited = r.updated_at !== r.created_at ? " (изменён)" : "";

        return `
          <div class="border rounded p-3 mb-3">
            <div class="d-flex justify-content-between">
              <div>
                <span class="fw-bold">★ ${Number(r.rating).toFixed(1)}</span>
                <span class="fw-bold ms-2">${escapeHtml(r.title)}</span>
              </div>
              <div class="text-muted small">${escapeHtml(r.user.name)} · ${date}${edited}</div>
            </div>
            <p class="mt-2 mb-2" style="white-space: pre-line;">${escapeHtml(r.body)}</p>
            ${r.pros ? `<div><span class="text-success fw-bold">Достоинства:</span>
                <span style="white-space: pre-line;">${escapeHtml(r.pros)}</span></div>` : ""}
            ${r.cons ? `<div><span class="text-danger fw-bold">Недостатки:</span>
                <span style="white-space: pre-line;">${escapeHtml(r.cons)}</span></div>` : ""}
            ${own || isAdmin ? `
              <div class="mt-2">
                ${own ? `<button class="btn btn-sm btn-outline-secondary me-2"
                          data-action="edit" data-id="${r.id}">Изменить</button>` : ""}
                <button class="btn btn-sm btn-outline-danger"
                        data-action="delete" data-id="${r.id}">Удалить</button>
              </div>` : ""}
          </div>`;
    }

    function renderList() {
        listBox.innerHTML = state.items.map(renderReview).join("");
    }

    function renderForm() {
        const editing = state.editing;
        const can = state.can;

        // Форма показывается, если пользователь может оставить отзыв или редактирует свой
        if (!editing) {
            if (!userId) {
                formBox.innerHTML = `<div class="text-muted"><a href="/login">Войдите</a>, чтобы оставить отзыв.</div>`;
                return;
            }
            if (!can) {
                formBox.innerHTML = "";
                return;
            }
            if (!can.can_review) {
                const msg = can.reason === "already_reviewed"
                    ? "Вы уже оставили отзыв на этот товар."
                    : "Отзывы могут оставлять только покупатели этого товара.";
                formBox.innerHTML = `<div class="text-muted">${msg}</div>`;
                return;
            }
        }

        const r = editing ?? {};
        formBox.innerHTML = `
          <form class="border rounded p-3" novalidate>
            <h3 class="h6 mb-3">${editing ? "Изменить отзыв" : "Ваш отзыв"}</h3>
            <div class="mb-3">
              <label class="form-label" for="rv-rating">Оценка (1–5)</label>
              <input id="rv-rating" name="rating" type="number" step="0.1" min="1" max="5"
                     class="form-control" style="max-width: 120px;" required
                     value="${r.rating !== undefined ? Number(r.rating).toFixed(1) : ""}">
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-title">Заголовок</label>
              <input id="rv-title" name="title" type="text" maxlength="150" class="form-control" required
                     value="${escapeHtml(r.title ?? "")}">
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-body">Отзыв</label>
              <textarea id="rv-body" name="body" rows="4" maxlength="5000" class="form-control"
                        required>${escapeHtml(r.body ?? "")}</textarea>
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-pros">Достоинства</label>
              <textarea id="rv-pros" name="pros" rows="2" maxlength="2000"
                        class="form-control">${escapeHtml(r.pros ?? "")}</textarea>
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-cons">Недостатки</label>
              <textarea id="rv-cons" name="cons" rows="2" maxlength="2000"
                        class="form-control">${escapeHtml(r.cons ?? "")}</textarea>
              <div class="invalid-feedback"></div>
            </div>
            <button type="submit" class="btn btn-primary">${editing ? "Сохранить" : "Отправить"}</button>
            ${editing ? `<button type="button" class="btn btn-link" data-action="cancel">Отмена</button>` : ""}
          </form>`;
    }

    // --- Загрузка данных ----------------------------------------
    async function loadReviews() {
        try {
            const data = await api(`/products/${pid}/reviews?page=${state.page}&page_size=${PAGE_SIZE}`);

            // Удалили последний отзыв на странице: возвращаемся на предыдущую
            if (!data.items.length && state.page > 1 && data.pages > 0) {
                state.page = data.pages;
                return loadReviews();
            }

            state.items = data.items;
            renderSummary(data.summary);
            renderList();
            renderPagination(pagBox, data.page, data.pages);
        }
        catch (err) {
            // 404 значит, что товар скрыт (обработка в product.js)
            if (err.status !== 404) showAlert(errorText(err));
        }
    }

    async function loadCanReview() {
        // Гостю запрос не шлём
        if (!userId) return;
        try {
            state.can = await api(`/products/${pid}/reviews/can-review`);
        }
        catch (err) {
            if (err.status !== 404) showAlert(errorText(err));
        }
    }

    pagBox.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-page]");
        if (!btn) return;
        state.page = Number(btn.dataset.page);
        loadReviews();
    });

    listBox.addEventListener("click", async (e) => {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;
        const id = Number(btn.dataset.id);

        if (btn.dataset.action === "edit") {
            state.editing = state.items.find((r) => r.id === id) ?? null;
            renderForm();
            formBox.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        else if (btn.dataset.action === "delete") {
            if (!confirm("Удалить отзыв?")) return;
            try {
                await api(`/reviews/${id}`, { method: "DELETE" });
                if (state.editing?.id === id) state.editing = null;
                showAlert("Отзыв удалён", "success");
                await Promise.all([loadReviews(), loadCanReview()]);
                renderForm();
            }
            catch (err) {
                showAlert(errorText(err));
            }
        }
    });

    formBox.addEventListener("click", (e) => {
        if (e.target.closest('[data-action="cancel"]')) {
            state.editing = null;
            renderForm();
        }
    });

    formBox.addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = e.target;
        clearFieldErrors(form);
        if (!form.reportValidity()) return;

        const val = (name) => form.elements.namedItem(name).value;
        // Рейтинг уходит строкой как есть: Pydantic сам разберёт Decimal без float-неточностей.
        // Пустые pros/cons сервер превратит в null.
        const body = Object.fromEntries(FIELDS.map((f) => [f, val(f)]));

        const submitBtn = form.querySelector('[type="submit"]');
        submitBtn.disabled = true;

        try {
            if (state.editing) {
                await api(`/reviews/${state.editing.id}`, { method: "PATCH", body });
            } else {
                await api(`/products/${pid}/reviews`, { method: "POST", body });
                state.page = 1;   // новые отзывы идут первыми
            }
            state.editing = null;
            showAlert("Отзыв сохранён", "success");
            await Promise.all([loadReviews(), loadCanReview()]);
            renderForm();
        }
        catch (err) {
            const detail = err.data?.detail;
            if (err.status === 422 && Array.isArray(detail) && showFieldErrors(form, detail, FIELDS)) {
                submitBtn.disabled = false;
                return;
            }
            showAlert(errorText(err));
            // 403/409: ситуация изменилась с момента загрузки страницы, обновляем форму
            if (err.status === 403 || err.status === 409) {
                state.editing = null;
                await loadCanReview();
                renderForm();
            }
            else {
                submitBtn.disabled = false;
            }
        }
    });

    // Старт функции
    (async () => {
        await Promise.all([loadReviews(), loadCanReview()]);
        renderForm();
    })();
})();