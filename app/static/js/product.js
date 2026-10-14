const productBox = document.getElementById("product");
// id товара пришёл из роута через data-атрибут (см. product.html)
const productId = productBox.dataset.id;

let categoryName = "—";
let brandName = "—";

function renderProduct(p) {
    const img = productImageUrl(p);
    const inStock = p.stock_quantity > 0;

    document.title = p.name;
    productBox.innerHTML = `
      <div class="row g-4">
        <div class="col-md-5">
          ${img
            ? `<img src="${img}" alt="${escapeHtml(p.name)}" class="img-fluid rounded">`
            : `<div class="bg-light text-center text-muted py-5 rounded">Нет фото</div>`}
        </div>

        <div class="col-md-7">
          <div class="d-flex align-items-start gap-2 mb-1">
            <h1 class="h3 mb-0">${escapeHtml(p.name)}</h1>
          </div>
          <div class="text-muted mb-3">Артикул: ${escapeHtml(p.sku)}</div>

          <div class="fs-3 fw-bold mb-3">
            ${formatPrice(p.price)}
            ${p.old_price ? `<s class="fs-6 fw-normal text-muted ms-2">${formatPrice(p.old_price)}</s>` : ""}
          </div>

          <dl class="row mb-3">
            <dt class="col-sm-3">Категория</dt>
            <dd class="col-sm-9">${escapeHtml(categoryName)}</dd>
            <dt class="col-sm-3">Бренд</dt>
            <dd class="col-sm-9">${escapeHtml(brandName)}</dd>
            <dt class="col-sm-3">В наличии</dt>
            <dd class="col-sm-9 ${inStock ? "" : "text-danger"}">
              ${inStock ? `${p.stock_quantity} шт.` : "Нет в наличии"}
            </dd>
          </dl>

          <h2 class="h6">Описание</h2>
          <p style="white-space: pre-line;">${escapeHtml(p.description ?? "Описание отсутствует")}</p>
          <button class="btn btn-primary add-to-cart"
                  data-id="${p.id}" ${inStock ? "" : "disabled"}>
            ${inStock ? "В корзину" : "Нет в наличии"}
          </button>
        </div>
      </div>`;
}

async function loadProduct() {
    try {
        const [product, categories, brands] = await Promise.all([
            api(`/admin/products/${productId}`),
            api("/categories"),
            api("/brands"),
        ]);

        categoryName = categories.find((c) => c.id === product.category_id)?.name ?? "—";
        brandName = product.brand_id
            ? (brands.find((b) => b.id === product.brand_id)?.name ?? "—")
            : "—";

        renderProduct(product);
    }
    catch (err) {
        if (err.status === 404) {
            // Товара нет или он скрыт: это не сбой, а штатная ситуация
            productBox.innerHTML = `<div class="alert alert-warning">Товар не найден</div>`;
        }
        else {
            showAlert(errorText(err));
        }
    }
}

loadProduct();