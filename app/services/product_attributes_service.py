from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attribute, AttributeOption, ProductOption


# noinspection PyTypeChecker
async def fetch_product_attributes(db: AsyncSession, product_id: int) -> list[dict]:
    rows = await db.execute(
        select(Attribute.name, AttributeOption.value)
        .select_from(ProductOption)
        .join(Attribute, Attribute.id == ProductOption.attribute_id)
        .join(AttributeOption, AttributeOption.id == ProductOption.option_id)
        .where(ProductOption.product_id == product_id)
        .order_by(Attribute.position, Attribute.id)
    )
    return [{"name": name, "value": value} for name, value in rows.all()]