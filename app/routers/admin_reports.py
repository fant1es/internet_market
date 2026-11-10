from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.services import report_service

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"],
                   dependencies=[Depends(get_current_admin)])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(data: bytes, name: str) -> Response:
    return Response(data, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Cache-Control": "private, no-store",
    })


@router.get("/stock", summary="Остатки на складе (Excel)")
async def stock(db: AsyncSession = Depends(get_db)):
    return _xlsx(await report_service.stock_report(db), f"stock_{date.today()}.xlsx")


@router.get("/users", summary="Все пользователи (Excel)")
async def users(db: AsyncSession = Depends(get_db)):
    return _xlsx(await report_service.users_report(db), f"users_{date.today()}.xlsx")


@router.get("/users/{user_id}", summary="Заказы и транзакции пользователя (Excel)")
async def user_detail(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await report_service.user_report(db, user_id)
    if result is None:
        raise HTTPException(404, "Пользователь не найден")
    return _xlsx(*result)