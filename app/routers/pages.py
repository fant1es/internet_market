from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from app.dependencies.auth import CurrentUserOptional
from app.models.user import UserRole

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
async def index(request: Request, user: CurrentUserOptional):
    return templates.TemplateResponse(request, "index.html", {"user": user})


@router.get("/login")
async def login_page(request: Request, user: CurrentUserOptional):
    if user:
        return RedirectResponse("/")
    return templates.TemplateResponse(request, "auth/login.html", {"user": user})


@router.get("/register")
async def register_page(request: Request, user: CurrentUserOptional):
    if user:
        return RedirectResponse("/")
    return templates.TemplateResponse(request, "auth/register.html", {"user": user})


@router.get("/product/{product_id}")
async def product_page(request: Request, product_id: int, user: CurrentUserOptional):
    return templates.TemplateResponse(
        request, "product.html", {"user": user, "product_id": product_id}
    )


def _admin_redirect(user) -> RedirectResponse | None:
    """Если просто поставить в admin_product_page, обычные юзеры получали бы 403,
    поэтому их просто редиректим на нужную страницу."""
    if user is None:
        return RedirectResponse("/login")
    if user.role != UserRole.ADMIN:
        return RedirectResponse("/")
    return None


@router.get("/admin")
async def admin_products_page(request: Request, user: CurrentUserOptional):
    redirect = _admin_redirect(user)
    if redirect is not None:
        return redirect
    return templates.TemplateResponse(request, "admin/products.html", {"user": user})


@router.get("/admin/product/new")
async def admin_product_new(request: Request, user: CurrentUserOptional):
    redirect = _admin_redirect(user)
    if redirect is not None:
        return redirect
    return templates.TemplateResponse(request, "admin/new.html")


@router.get("/admin/product/{product_id}")
async def admin_product_page(request: Request, product_id: int, user: CurrentUserOptional):
    redirect = _admin_redirect(user)
    if redirect is not None:
        return redirect
    return templates.TemplateResponse(request, "admin/product.html", {"user": user, "product_id": product_id})


@router.get("/admin/product/{product_id}/edit")
async def admin_product_edit_page(request: Request, product_id: int, user: CurrentUserOptional):
    redirect = _admin_redirect(user)
    if redirect is not None:
        return redirect
    return templates.TemplateResponse(request, "admin/edit.html", {"user": user, "product_id": product_id})


@router.get("/admin/references")
async def admin_references_page(request: Request, user: CurrentUserOptional):
    redirect = _admin_redirect(user)
    if redirect is not None:
        return redirect
    return templates.TemplateResponse(request, "admin/references.html")


@router.get("/my-cart")
async def cart_page(request: Request, user: CurrentUserOptional):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "cart.html", {"user": user})