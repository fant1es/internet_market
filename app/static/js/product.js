const productBox = document.getElementById("product");
// id товара пришёл из роута через data-атрибут (см. product.html)
const productId = productBox.dataset.id;

function renderProduct(p) {
    const inStock = p.stock_quantity > 0;

    document.title = p.name;
    productBox.innerHTML = `
      <div class="row g-4">
        <div class="col-md-5">
          <div class="bg-light text-center text-muted py-5">Нет фото</div>
        </div>
        <div class="col-md-7">
          <h1 class="h3">${escapeHtml(p.name)}</h1>
          <div class="text-muted mb-3">Артикул: ${escapeHtml(p.sku)}</div>
          <div class="fs-3 fw-bold mb-3">${formatPrice(p.price)}</div>
          <p>${escapeHtml(p.description ?? "Описание отсутствует")}</p>
          <div class="mb-3 ${inStock ? "text-success" : "text-danger"}">
            ${inStock ? `В наличии: ${p.stock_quantity} шт.` : "Нет в наличии"}
          </div>
          <button class="btn btn-primary add-to-cart"
                  data-id="${p.id}" ${inStock ? "" : "disabled"}>
            ${inStock ? "В корзину" : "Нет в наличии"}
          </button>
        </div>
      </div>`;
}

async function loadProduct() {
    try {
        const product = await api(`/products/${productId}`);
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