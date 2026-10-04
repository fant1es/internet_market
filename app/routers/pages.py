from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from app.dependencies.auth import CurrentUserOptional

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