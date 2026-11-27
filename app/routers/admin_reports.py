from datetime import date

from fastapi import APIRouter, Depends, Response
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import CurrentAdmin, get_current_admin
from app.services import report_service
from app.utils.errors import AppError

audit = logger.bind(channel="audit")

router = APIRouter(prefix="/admin/reports", tags=["admin-reports"],
                   dependencies=[Depends(get_current_admin)])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(data: bytes, name: str) -> Response:
    return Response(data, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Cache-Control": "private, no-store",
    })


@router.get("/stock", summary="Остатки на складе (Excel)")
async def stock(admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    data = await report_service.stock_report(db)
    audit.info("Выгружен отчёт | отчёт=остатки admin_id={}", admin.id)
    return _xlsx(data, f"stock_{date.today()}.xlsx")


@router.get("/users", summary="Все пользователи (Excel)")
async def users(admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    data = await report_service.users_report(db)
    audit.info("Выгружен отчёт | отчёт=все пользователи admin_id={}", admin.id)
    return _xlsx(data, f"users_{date.today()}.xlsx")


@router.get("/users/{user_id}", summary="Заказы и транзакции пользователя (Excel)")
async def user_detail(user_id: int, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    result = await report_service.user_report(db, user_id)
    if result is None:
        logger.debug("Отчёт не выгружен | причина=пользователь не найден user_id={}", user_id)
        raise AppError(404, "user_not_found")
    audit.info("Выгружен отчёт | отчёт=пользователь user_id={} admin_id={}", user_id, admin.id)
    return _xlsx(*result)