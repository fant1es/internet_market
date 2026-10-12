from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.routers import brands, admin_products
from app.routers import pages, products, categories
from app.routers.auth import auth_router


app = FastAPI()
app.include_router(auth_router)
app.include_router(pages.router)
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(brands.router)
app.include_router(admin_products.router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/health")
def health():
    return {"status": "ok"}