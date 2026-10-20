from decimal import Decimal

from pydantic import BaseModel, Field

MAX_TOPUP = Decimal("100000")


class TopUpIn(BaseModel):
    amount: Decimal = Field(gt=0, le=MAX_TOPUP, max_digits=10, decimal_places=2)


class BalanceOut(BaseModel):
    balance: Decimal