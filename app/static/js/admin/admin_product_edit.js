document.addEventListener("DOMContentLoaded", async () => {
    const form = document.getElementById("product-form");
    if (!form) return;

    const productId = form.dataset.id;

    const imagePreview = document.getElementById("image-preview");
    const imageEmpty = document.getElementById("image-empty");
    const categorySelect = document.getElementById("category");
    const brandSelect = document.getElementById("brand");

    // Заполняет выпадающий список: первый пункт-подсказка + варианты из справочника
    function fillSelect(select, placeholder, items) {
        select.innerHTML = `<option value="">${placeholder}</option>`
            + items.map((item) => `<option value="${item.id}">${escapeHtml(item.name)}</option>`).join("");
    }

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
        const imageUrl = productImageUrl(product);
        if (imageUrl) {
            imagePreview.src = imageUrl;
            imagePreview.classList.remove("d-none");
            imageEmpty.classList.add("d-none");
        }
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
});