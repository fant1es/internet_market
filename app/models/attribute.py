from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint

from app.database import Base


class Attribute(Base):
    """Характеристика категории, например 'Тип' у ноутбуков"""
    __tablename__ = 'attributes'

    id: int = Column(Integer, primary_key=True)
    category_id: int = Column(Integer, ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    name: str = Column(String, nullable=False)
    slug: str = Column(String, nullable=False)

    # Внутри категории slug уникален. Индекс по category_id этот constraint уже покрывает
    __table_args__ = (
        UniqueConstraint('category_id', 'slug', name='uq_attributes_category_slug'),
    )


class AttributeOption(Base):
    """Вариант значения характеристики, например 'Игровой'"""
    __tablename__ = 'attribute_options'

    id: int = Column(Integer, primary_key=True)
    attribute_id: int = Column(Integer, ForeignKey('attributes.id', ondelete='CASCADE'), nullable=False)
    value: str = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('attribute_id', 'value', name='uq_attribute_options_attribute_value'),
        # Нужен только как цель составного внешнего ключа из product_options в ProductOption
        UniqueConstraint('id', 'attribute_id', name='uq_attribute_options_id_attribute'),
    )


class ProductOption(Base):
    """Выбранный вариант характеристики у товара.
    Допускается по одному варианту на атрибут."""
    __tablename__ = 'product_options'

    product_id: int = Column(Integer, ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    # Первичный ключ (product_id, attribute_id) на уровне БД не даёт товару два значения одного атрибута
    attribute_id: int = Column(Integer, primary_key=True)
    option_id: int = Column(Integer, nullable=False, index=True)  # индекс для фильтра по вариантам

    # Составной ключ гарантирует, что option_id действительно относится к attribute_id
    __table_args__ = (
        ForeignKeyConstraint(
            ['option_id', 'attribute_id'],
            ['attribute_options.id', 'attribute_options.attribute_id'],
            ondelete='CASCADE',
            name='fk_product_options_option_attribute',
        ),
    )