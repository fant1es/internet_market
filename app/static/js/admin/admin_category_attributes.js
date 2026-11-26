// Управление характеристиками категории через кнопку в строке категории
(() => {
    const modalEl = document.getElementById("attr-modal");
    const modal = new bootstrap.Modal(modalEl);
    const titleEl = document.getElementById("attr-modal-title");
    const errorEl = document.getElementById("attr-modal-error");
    const listEl = document.getElementById("attr-list");
    const addForm = document.getElementById("attr-add-form");
    const newName = document.getElementById("attr-new-name");

    let categoryId = null;
    let attributes = [];
    let onClose = null;   // что сделать после закрытия окна (например, обновить форму товара)
    let changed = false;  // менялось ли что-то, пока окно было открыто

    // Ошибки показываем внутри окна: общий блок #alerts закрыт затемнением
    function showError(message) {
        errorEl.textContent = message;
        errorEl.classList.remove("d-none");
    }
    const clearError = () => errorEl.classList.add("d-none");

    function render() {
        if (attributes.length === 0) {
            listEl.innerHTML = `<p class="text-muted text-center py-4 mb-0">${t("js.admin.attrs_none")}</p>`;
            return;
        }

        listEl.innerHTML = attributes.map((a) => `
        <div class="card mb-3" data-attr-id="${a.id}">
          <div class="card-header d-flex justify-content-between align-items-center">
            <strong>${escapeHtml(a.name)}</strong>
            <div class="text-nowrap">
              <button type="button" class="btn btn-outline-primary btn-sm" data-action="rename-attr">${t("js.admin.rename")}</button>
              <button type="button" class="btn btn-outline-danger btn-sm" data-action="delete-attr">${t("js.admin.delete")}</button>
            </div>
          </div>
          <div class="card-body">
            <div class="d-flex flex-wrap gap-2 mb-3">
              ${a.options.length
                ? a.options.map((o) => `
                  <span class="btn-group btn-group-sm" role="group" data-option-id="${o.id}">
                    <button type="button" class="btn btn-outline-secondary" data-action="rename-option"
                            title="${t("js.admin.option_hint", { count: o.products_count })}">
                      ${escapeHtml(o.value)}
                    </button>
                    <button type="button" class="btn btn-outline-danger" data-action="delete-option"
                            aria-label="${t("js.admin.option_delete_aria")}">×</button>
                  </span>`).join("")
                : `<span class="text-muted small">${t("js.admin.options_none")}</span>`}
            </div>
            <form class="option-form input-group input-group-sm" novalidate>
              <input type="text" class="form-control" maxlength="100" required placeholder="${t("js.admin.new_option")}">
              <button type="submit" class="btn btn-outline-primary">${t("js.admin.add")}</button>
            </form>
          </div>
        </div>`).join("");
    }

    async function reload() {
        attributes = await api(`/admin/attributes?category_id=${categoryId}`);
        render();
    }

    // Общая обёртка: действие -> перезагрузка списка, ошибка показывается в окне
    async function run(action) {
        clearError();
        try {
            await action();
            changed = true;
            await reload();
        }
        catch (err) {
            showError(errorText(err));
        }
    }

    // Вызывается в admin_references.js
    window.openAttributesModal = async (category, callback = null) => {
        categoryId = category.id;
        attributes = [];
        onClose = callback;
        changed = false;
        titleEl.textContent = t("js.admin.attrs_modal_title", { name: category.name });
        newName.value = "";
        listEl.innerHTML = `<p class="text-muted text-center py-4 mb-0">${t("js.admin.loading")}</p>`;
        clearError();
        modal.show();

        try {
            await reload();
        }
        catch (err) {
            listEl.innerHTML = "";
            showError(errorText(err));
        }
    };

    // Добавление характеристики
    addForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const name = newName.value.trim();
        if (!name) return;

        const slug = slugify(name);
        if (!slug) {
            showError(t("js.admin.slug_required"));
            return;
        }

        run(async () => {
            await api(`/admin/categories/${categoryId}/attributes`, { method: "POST", body: { name, slug } });
            newName.value = "";
        });
    });

    // Добавление варианта: форма есть в каждой карточке, поэтому делегирование
    listEl.addEventListener("submit", (e) => {
        const form = e.target.closest(".option-form");
        if (!form) return;
        e.preventDefault();

        const value = form.querySelector("input").value.trim();
        if (!value) return;

        const attrId = form.closest("[data-attr-id]").dataset.attrId;
        run(() => api(`/admin/attributes/${attrId}/options`, { method: "POST", body: { value } }));
    });

    listEl.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;

        const attr = attributes.find((a) => a.id === Number(btn.closest("[data-attr-id]").dataset.attrId));
        const optEl = btn.closest("[data-option-id]");
        const option = optEl ? attr.options.find((o) => o.id === Number(optEl.dataset.optionId)) : null;

        switch (btn.dataset.action) {
            case "rename-attr": {
                const name = prompt(t("js.admin.prompt_attr"), attr.name)?.trim();
                if (!name || name === attr.name) return;
                // slug не меняем: он нужен только для уникальности внутри категории
                run(() => api(`/admin/attributes/${attr.id}`, { method: "PUT", body: { name, slug: attr.slug } }));
                break;
            }
            case "delete-attr": {
                let text = t("js.admin.delete_attr", { name: attr.name });
                if (attr.products_count) text += "\n\n" + t("js.admin.delete_attr_used", { count: attr.products_count });
                if (!confirm(text)) return;
                run(() => api(`/admin/attributes/${attr.id}`, { method: "DELETE" }));
                break;
            }
            case "rename-option": {
                const value = prompt(t("js.admin.prompt_option"), option.value)?.trim();
                if (!value || value === option.value) return;
                run(() => api(`/admin/attribute-options/${option.id}`, { method: "PUT", body: { value } }));
                break;
            }
            case "delete-option": {
                let text = t("js.admin.delete_option", { name: option.value });
                if (option.products_count) text += "\n\n" + t("js.admin.delete_option_used", { count: option.products_count });
                if (!confirm(text)) return;
                run(() => api(`/admin/attribute-options/${option.id}`, { method: "DELETE" }));
                break;
            }
        }
    });

    // Если что-то менялось, даём странице обновить свои данные
    modalEl.addEventListener("hidden.bs.modal", () => {
        if (changed && onClose) onClose();
    });
})();