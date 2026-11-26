// В IIFE, чтобы не конфликтовать с глобальными const из product.js
(() => {
    const box = document.getElementById("reviews");
    if (!box) return;

    const pid = box.dataset.productId;
    const userId = box.dataset.userId ? Number(box.dataset.userId) : null;
    const isAdmin = box.dataset.isAdmin === "true";
    const PAGE_SIZE = 10;
    const FIELDS = ["rating", "title", "body", "pros", "cons"];

    const LOCALE = window.LANG === "en" ? "en-GB" : "ru-RU";

    const state = {
        page: 1,
        items: [],
        can: null,      // ответ /can-review
        editing: null,  // отзыв, который сейчас редактируется
    };

    box.innerHTML = `
      <h2 class="h4 mb-3">${t("js.reviews.title")}</h2>
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
        ? `<span class="text-muted">${t("js.reviews.none_yet")}</span>`
        : `<span class="fs-4 fw-bold">★ ${Number(summary.average).toFixed(1)}</span>
           <span class="text-muted ms-2">${t("js.reviews.count", { count: summary.count })}</span>`;
    }

    function renderReview(r) {
        const own = r.user.id === userId;
        const date = new Date(r.created_at).toLocaleDateString(LOCALE);
        const edited = r.updated_at !== r.created_at ? ` ${t("js.reviews.edited")}` : "";

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
            ${r.pros ? `<div><span class="text-success fw-bold">${t("js.reviews.pros")}:</span>
                <span style="white-space: pre-line;">${escapeHtml(r.pros)}</span></div>` : ""}
            ${r.cons ? `<div><span class="text-danger fw-bold">${t("js.reviews.cons")}:</span>
                <span style="white-space: pre-line;">${escapeHtml(r.cons)}</span></div>` : ""}
            ${own || isAdmin ? `
              <div class="mt-2">
                ${own ? `<button class="btn btn-sm btn-outline-secondary me-2"
                          data-action="edit" data-id="${r.id}">${t("js.reviews.edit")}</button>` : ""}
                <button class="btn btn-sm btn-outline-danger"
                        data-action="delete" data-id="${r.id}">${t("js.reviews.delete")}</button>
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
                    ? t("js.reviews.already_reviewed")
                    : t("js.reviews.buyers_only");
                formBox.innerHTML = `<div class="text-muted"><a href="/login">${t("js.reviews.login_link")}</a>${t("js.reviews.login_rest")}</div>`;
                return;
            }
        }

        const r = editing ?? {};
        formBox.innerHTML = `
          <form class="border rounded p-3" novalidate>
            <h3 class="h6 mb-3">${editing ? t("js.reviews.form_edit") : t("js.reviews.form_new")}</h3>
            <div class="mb-3">
              <label class="form-label" for="rv-rating">${t("js.reviews.rating")}</label>
              <input id="rv-rating" name="rating" type="number" step="0.1" min="1" max="5"
                     class="form-control" style="max-width: 120px;" required
                     value="${r.rating !== undefined ? Number(r.rating).toFixed(1) : ""}">
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-title">${t("js.reviews.heading")}</label>
              <input id="rv-title" name="title" type="text" maxlength="150" class="form-control" required
                     value="${escapeHtml(r.title ?? "")}">
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-body">${t("js.reviews.body")}</label>
              <textarea id="rv-body" name="body" rows="4" maxlength="5000" class="form-control"
                        required>${escapeHtml(r.body ?? "")}</textarea>
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-pros">${t("js.reviews.pros")}</label>
              <textarea id="rv-pros" name="pros" rows="2" maxlength="2000"
                        class="form-control">${escapeHtml(r.pros ?? "")}</textarea>
              <div class="invalid-feedback"></div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="rv-cons">${t("js.reviews.cons")}</label>
              <textarea id="rv-cons" name="cons" rows="2" maxlength="2000"
                        class="form-control">${escapeHtml(r.cons ?? "")}</textarea>
              <div class="invalid-feedback"></div>
            </div>
            <button type="submit" class="btn btn-primary">${editing ? t("js.reviews.save") : t("js.reviews.submit")}</button>
            ${editing ? `<button type="button" class="btn btn-link" data-action="cancel">${t("js.reviews.cancel")}</button>` : ""}
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
            if (!confirm(t("js.reviews.delete_confirm"))) return;
            try {
                await api(`/reviews/${id}`, { method: "DELETE" });
                if (state.editing?.id === id) state.editing = null;
                showAlert(t("js.reviews.deleted"), "success");
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
            showAlert(t("js.reviews.saved"), "success");
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