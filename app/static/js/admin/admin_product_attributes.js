// Блок характеристик в форме товара. Список зависит от категории: при её смене перерисовывается
function createAttributesEditor(box) {
    let lastRequestId = 0; // защита от гонки при быстрой смене категории
    let ready = false;     // true, когда блок отрисован и getSelected() можно доверять

    const hint = (text) => { box.innerHTML = `<p class="text-muted small mb-0">${text}</p>`; };

    async function load(categoryId, selectedIds = []) {
        const requestId = ++lastRequestId;
        ready = false;

        if (!categoryId) {
            hint("Выберите категорию, чтобы задать характеристики.");
            ready = true;
            return;
        }

        hint("Загрузка...");
        try {
            const attributes = await api(`/admin/categories/${Number(categoryId)}/attributes`);
            if (requestId !== lastRequestId) return; // пришёл устаревший ответ

            if (attributes.length === 0) {
                hint("У этой категории нет характеристик.");
                ready = true;
                return;
            }

            const selected = new Set(selectedIds);
            box.innerHTML = `<div class="row g-3">` + attributes.map((a, i) => `
                <div class="col-md-6">
                  <label for="attr-${i}" class="form-label">${escapeHtml(a.name)}</label>
                  <select id="attr-${i}" class="form-select attr-select">
                    <option value="">Не указано</option>
                    ${a.options.map((o) => `
                      <option value="${o.id}" ${selected.has(o.id) ? "selected" : ""}>${escapeHtml(o.value)}</option>`).join("")}
                  </select>
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

    return { load, getSelected, isReady: () => ready };
}