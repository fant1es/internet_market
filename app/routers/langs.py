from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.i18n import COOKIE, SUPPORTED, safe_back_url

router = APIRouter()


@router.get("/lang/{code}", include_in_schema=False)
async def set_lang(code: str, request: Request):
    if code not in SUPPORTED:
        raise HTTPException(status_code=404, detail="Язык не поддерживается")
    response = RedirectResponse(safe_back_url(request.headers.get("referer")), status_code=303)
    response.set_cookie(COOKIE, code, max_age=365 * 24 * 3600, samesite="lax", path="/")
    return response