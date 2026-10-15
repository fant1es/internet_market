document.addEventListener("DOMContentLoaded", async () => {
    const form = document.getElementById("product-form");
    if (!form) return;

    const imagePreview = document.getElementById("image-preview");
    const imageEmpty = document.getElementById("image-empty");
    const imageInput = document.getElementById("image_file");
    const fileNameLabel = document.getElementById("image-file-name");
    const categorySelect = document.getElementById("category");
    const brandSelect = document.getElementById("brand");
    const submitBtn = form.querySelector('button[type="submit"]');

    const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
    const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

    let selectedFile = null;      // выбранный, но ещё не загруженный файл
    let previewObjectUrl = null;  // временный blob-URL для локального превью
    let createdId = null;         // id товара, если он уже создан, а фото не загрузилось

    // Заполняет выпадающий список: первый пункт-подсказка + варианты из справочника
    function fillSelect(select, placeholder, items) {
        select.innerHTML = `<option value="">${placeholder}</option>`
            + items.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
    }

    // Показывает картинку по URL или заглушку «Нет фото», если url пустой
    function showImage(url) {
        if (url) {
            imagePreview.src = url;
            imagePreview.classList.remove("d-none");
            imageEmpty.classList.add("d-none");
        }
        else {
            imagePreview.removeAttribute("src");
            imagePreview.classList.add("d-none");
            imageEmpty.classList.remove("d-none");
        }
    }

    function updateFileName() {
        fileNameLabel.textContent = selectedFile ? selectedFile.name : "Файл не выбран";
        fileNameLabel.classList.toggle("text-muted", !selectedFile);
    }

    function resetSelectedFile() {
        selectedFile = null;
        imageInput.value = "";
        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);  // иначе утечка памяти
            previewObjectUrl = null;
        }
        updateFileName();
    }

    // Локальное превью + проверка на клиенте (сервер всё равно перепроверит)
    imageInput.addEventListener("change", () => {
        const file = imageInput.files[0];
        resetSelectedFile();
        showImage(null);

        if (!file) return;

        if (!ALLOWED_TYPES.includes(file.type)) {
            showAlert("Допустимы только JPEG, PNG и WebP", "warning");
            return;
        }
        if (file.size > MAX_IMAGE_BYTES) {
            showAlert("Файл слишком большой (максимум 5 МБ)", "warning");
            return;
        }

        selectedFile = file;
        updateFileName();
        previewObjectUrl = URL.createObjectURL(file);
        showImage(previewObjectUrl);
    });

    // Справочники для выпадающих списков
    try {
        const [categories, brands] = await Promise.all([
            api("/categories"),
            api("/brands"),
        ]);
        fillSelect(categorySelect, "Выберите категорию...", categories);
        fillSelect(brandSelect, "Без бренда", brands);
    }
    catch (err) {
        showAlert(errorText(err));
        submitBtn.disabled = true;   // без категорий товар всё равно не создать
        return;
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        form.classList.add("was-validated");
        if (!form.checkValidity()) return;

        const price = Number(document.getElementById("price").value);
        const oldPriceRaw = document.getElementById("old_price").value;
        const oldPrice = oldPriceRaw === "" ? null : Number(oldPriceRaw);

        if (oldPrice !== null && oldPrice <= price) {
            showAlert("Старая цена должна быть больше текущей", "warning");
            return;
        }

        const payload = {
            name: document.getElementById("name").value.trim(),
            sku: document.getElementById("sku").value.trim(),
            description: document.getElementById("description").value.trim() || null,
            category_id: Number(categorySelect.value),
            brand_id: brandSelect.value === "" ? null : Number(brandSelect.value),
            price,
            old_price: oldPrice,
            stock_quantity: Number(document.getElementById("stock_quantity").value),
            is_active: document.getElementById("is_active").checked,
        };

        submitBtn.disabled = true;   // защита от двойного клика

        // 1. Основные данные. Если товар уже создан (фото в прошлый раз не загрузилось),
        // обновляем его, а не создаём дубль: иначе будет 409 из-за занятого артикула
        try {
            const product = createdId === null
                ? await api("/admin/products", { method: "POST", body: payload })
                : await api(`/admin/products/${createdId}`, { method: "PUT", body: payload });
            createdId = product.id;
        }
        catch (err) {
            showAlert(errorText(err));
            submitBtn.disabled = false;
            return;
        }

        // 2. Картинка (только если выбрана)
        if (selectedFile) {
            const fd = new FormData();
            fd.append("file", selectedFile);   // имя поля должно совпадать с параметром `file` на бэкенде
            try {
                await api(`/admin/products/${createdId}/image`, { method: "POST", formData: fd });
            }
            catch (err) {
                showAlert(
                    `Товар создан, но фото не загрузилось: ${errorText(err)}. `
                    + "Выберите другой файл и нажмите кнопку ещё раз или оставьте всё как есть и вернитесь к списку.",
                    "warning",
                );
                submitBtn.disabled = false;
                return;   // остаёмся на странице, повторное нажатие обновит товар, а не создаст копию
            }
        }

        window.location.href = "/admin";
    });
});