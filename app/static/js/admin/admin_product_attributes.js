// Блок характеристик в форме товара. Список зависит от категории и при её смене перерисовывается
function createAttributesEditor(box) {
    let lastRequestId = 0; // защита от гонки при быстрой смене категории
    let ready = false;     // true, когда блок отрисован и getSelected() можно доверять
    let lastCategoryId = null;
    let lastSelected = []; // что выбрать при отрисовке

    const hint = (text) => { box.innerHTML = `<p class="text-muted small mb-0">${text}</p>`; };

    async function load(categoryId, selectedIds = []) {
        const requestId = ++lastRequestId;
        ready = false;
        lastCategoryId = categoryId;
        lastSelected = selectedIds;

        if (!categoryId) {
            hint(t("js.admin.attrs_choose_category"));
            ready = true;
            return;
        }

        hint(t("js.admin.loading"));
        try {
            // Здесь отдаются все характеристики, в том числе ещё без вариантов
            const attributes = await api(`/admin/attributes?category_id=${Number(categoryId)}`);
            if (requestId !== lastRequestId) return; // пришёл устаревший ответ

            if (attributes.length === 0) {
                hint(t("js.admin.attrs_empty"));
                ready = true;
                return;
            }

            const selected = new Set(selectedIds);
            box.innerHTML = `<div class="row g-3">` + attributes.map((a, i) => `
                <div class="col-md-6">
                  <label for="attr-${i}" class="form-label">${escapeHtml(a.name)}</label>
                  ${a.options.length
                    ? `<select id="attr-${i}" class="form-select attr-select">
                         <option value="">${t("js.admin.attrs_not_set")}</option>
                         ${a.options.map((o) => `
                           <option value="${o.id}" ${selected.has(o.id) ? "selected" : ""}>${escapeHtml(o.value)}</option>`).join("")}
                       </select>`
                    : `<select id="attr-${i}" class="form-select" disabled>
                         <option>${t("js.admin.attrs_no_options")}</option>
                       </select>`}
                </div>`).join("") + `</div>`;
            ready = true;
        }
        catch (err) {
            showAlert(errorText(err));
        }
    }

    // id выбранных вариантов (пустые "Не указано" отбрасываем)
    function getSelected() {
        return [...box.querySelectorAll(".attr-select")]
            .map((s) => s.value)
            .filter((v) => v !== "")
            .map(Number);
    }

    // Перезагружает список с сохранением текущего выбора. Удалённые варианты в списке уже не найдутся
    // и отсеются сами. Если загрузка ещё шла, берём то, что просили показать в прошлый раз
    function reload() {
        const keep = ready ? getSelected() : lastSelected;
        return load(lastCategoryId, keep);
    }

    return { load, reload, getSelected, isReady: () => ready };
}