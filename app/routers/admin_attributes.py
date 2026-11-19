from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.schemas.attribute import (
    AttributeAdminOut, AttributeIn, AttributeOut, OptionAdminOut, OptionIn,
)
from app.services import attribute_service

router = APIRouter(
    prefix="/admin",
    tags=["admin: attributes"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("/attributes", response_model=list[AttributeAdminOut],
            summary="Характеристики категории со всеми вариантами (для управления)")
async def list_attributes(category_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    return await attribute_service.list_attributes(db, category_id)


@router.post("/categories/{category_id}/attributes", response_model=AttributeOut, status_code=201,
             summary="Добавить характеристику в категорию")
async def create_attribute(category_id: int, data: AttributeIn, db: AsyncSession = Depends(get_db)):
    return await attribute_service.create_attribute(db, category_id, data.name, data.slug)


@router.put("/attributes/{attribute_id}", response_model=AttributeOut, summary="Изменить характеристику")
async def update_attribute(attribute_id: int, data: AttributeIn, db: AsyncSession = Depends(get_db)):
    return await attribute_service.update_attribute(db, attribute_id, data.name, data.slug)


@router.delete("/attributes/{attribute_id}", status_code=204,
               summary="Удалить характеристику вместе с вариантами и значениями у товаров")
async def delete_attribute(attribute_id: int, db: AsyncSession = Depends(get_db)):
    await attribute_service.delete_attribute(db, attribute_id)


@router.post("/attributes/{attribute_id}/options", response_model=OptionAdminOut, status_code=201,
             summary="Добавить вариант характеристики")
async def create_option(attribute_id: int, data: OptionIn, db: AsyncSession = Depends(get_db)):
    return await attribute_service.create_option(db, attribute_id, data.value)


@router.put("/attribute-options/{option_id}", response_model=OptionAdminOut, summary="Изменить вариант")
async def update_option(option_id: int, data: OptionIn, db: AsyncSession = Depends(get_db)):
    return await attribute_service.update_option(db, option_id, data.value)


@router.delete("/attribute-options/{option_id}", status_code=204,
               summary="Удалить вариант (у товаров значение снимается)")
async def delete_option(option_id: int, db: AsyncSession = Depends(get_db)):
    await attribute_service.delete_option(db, option_id)