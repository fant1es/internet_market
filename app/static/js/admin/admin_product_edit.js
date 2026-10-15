document.addEventListener("DOMContentLoaded", async () => {
    const form = document.getElementById("product-form");
    if (!form) return;

    const productId = form.dataset.id;

    const imagePreview = document.getElementById("image-preview");
    const imageEmpty = document.getElementById("image-empty");
    const imageInput = document.getElementById("image_file");
    const categorySelect = document.getElementById("category");
    const brandSelect = document.getElementById("brand");
    const submitBtn = form.querySelector('button[type="submit"]');
    const deleteImageBtn = document.getElementById("image-delete");
    const fileNameLabel = document.getElementById("image-file-name");

    const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
    const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

    let currentImageUrl = null;   // картинка, которая сейчас на сервере
    let selectedFile = null;      // выбранный, но ещё не загруженный файл
    let previewObjectUrl = null;  // временный blob-URL для локального превью

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

    function updateDeleteBtn() {
        deleteImageBtn.classList.toggle("d-none", !currentImageUrl);
    }

    // Подпись рядом с кнопкой выбора файла (нативную подпись браузера не переопределить)
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

        if (!file) {
            showImage(currentImageUrl);   // выбор отменён: возвращаем прежнюю картинку
            return;
        }
        if (!ALLOWED_TYPES.includes(file.type)) {
            showAlert("Допустимы только JPEG, PNG и WebP", "warning");
            showImage(currentImageUrl);
            return;
        }
        if (file.size > MAX_IMAGE_BYTES) {
            showAlert("Файл слишком большой (максимум 5 МБ)", "warning");
            showImage(currentImageUrl);
            return;
        }

        selectedFile = file;
        updateFileName();
        previewObjectUrl = URL.createObjectURL(file);
        showImage(previewObjectUrl);
    });

    try {
        const [product, categories, brands] = await Promise.all([
            api(`/admin/products/${productId}`),
            api("/categories"),
            api("/brands"),
        ]);

        // Списки нужно заполнить до установки value, иначе выбирать будет не из чего
        fillSelect(categorySelect, "Выберите категорию...", categories);
        fillSelect(brandSelect, "Без бренда", brands);
        categorySelect.value = product.category_id;
        brandSelect.value = product.brand_id ?? "";

        // Текстовые поля и цены (price и old_price приходят строками, как отдаёт API)
        document.getElementById("name").value = product.name;
        document.getElementById("sku").value = product.sku;
        document.getElementById("description").value = product.description ?? "";
        document.getElementById("price").value = product.price;
        document.getElementById("old_price").value = product.old_price ?? "";

        // Склад и видимость
        document.getElementById("stock_quantity").value = product.stock_quantity;
        document.getElementById("is_active").checked = product.is_active;

        // Изображение: если картинки нет, остаётся заглушка «Нет фото»
        currentImageUrl = productImageUrl(product);
        showImage(currentImageUrl);
        updateDeleteBtn();
    }
    catch (err) {
        if (err.status === 404) {
            // Товара нет: редактировать нечего, форму прячем
            form.classList.add("d-none");
            showAlert("Товар не найден", "warning");
        }
        else {
            showAlert(errorText(err));
        }
    }

    deleteImageBtn.addEventListener("click", async () => {
        if (!confirm("Удалить изображение товара?")) return;

        deleteImageBtn.disabled = true;
        try {
            await api(`/admin/products/${productId}/image`, { method: "DELETE" });
            currentImageUrl = null;
            resetSelectedFile();   // выбранный, но не сохранённый файл тоже сбрасываем
            showImage(null);
            updateDeleteBtn();
            showAlert("Изображение удалено", "success");
        }
        catch (err) {
            showAlert(errorText(err));
        }
        finally {
            deleteImageBtn.disabled = false;
        }
    });

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

        // 1. Основные данные
        try {
            await api(`/admin/products/${productId}`, { method: "PUT", body: payload });
        }
        catch (err) {
            showAlert(errorText(err));
            submitBtn.disabled = false;
            return;
        }

        // 2. Картинка (только если выбрана новая)
        if (selectedFile) {
            const fd = new FormData();
            fd.append("file", selectedFile);   // имя поля должно совпадать с параметром `file` на бэкенде
            try {
                const updated = await api(`/admin/products/${productId}/image`, { method: "POST", formData: fd });
                currentImageUrl = productImageUrl(updated);
                resetSelectedFile();
                showImage(currentImageUrl);
                updateDeleteBtn();
            }
            catch (err) {
                showAlert(`Товар сохранён, но фото не загрузилось: ${errorText(err)}`, "warning");
                submitBtn.disabled = false;
                return;   // остаёмся на странице, чтобы можно было повторить
            }
        }

        window.location.href = "/admin";
    });
});