from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.routers import pages, products, brands, categories, carts, balance, orders, admin_reports, admin_attributes
from app.routers import admin_references, admin_products
from app.routers import reviews
from app.routers.auth import auth_router
from app.routers import users
from app.logging_setup import setup_logging

app = FastAPI()
app.include_router(auth_router)
app.include_router(pages.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(brands.router)
app.include_router(admin_products.router)
app.include_router(admin_references.brands_admin)
app.include_router(admin_references.categories_admin)
app.include_router(carts.router)
app.include_router(balance.router)
app.include_router(orders.router)
app.include_router(users.router)
app.include_router(admin_reports.router)
app.include_router(admin_attributes.router)
app.include_router(reviews.review_router)
app.include_router(reviews.product_reviews_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

setup_logging()

@app.get("/health")
def health():
    return {"status": "ok"}