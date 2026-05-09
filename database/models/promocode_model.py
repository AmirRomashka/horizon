# database/models/promocode_model.py
from sqlalchemy import String, Integer, DateTime, Float, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from database.models.base_model import Base
from database.enumerate.promocode_enum import PromocodeDiscountType, PromocodeStatus


class Promocodes(Base):
    __tablename__ = "promocodes"

    promocode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    discount_type: Mapped[PromocodeDiscountType] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PromocodeStatus] = mapped_column(String(20), default=PromocodeStatus.ACTIVE)
    uses_left: Mapped[int] = mapped_column(Integer, default=1)
    min_price: Mapped[float] = mapped_column(Float, default=0.0)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=True)

    def __repr__(self) -> str:
        return f"<Promocodes(code={self.code}, discount_type={self.discount_type.value}, discount_value={self.discount_value}, status={self.status.value}, uses_left={self.uses_left})>"

    def is_active(self) -> bool:
        if self.status != PromocodeStatus.ACTIVE:
            return False
        if self.uses_left <= 0:
            return False
        if self.expires_at and self.expires_at < datetime.now():
            return False
        return True

    def can_apply_to_price(self, price: float) -> bool:
        return price >= self.min_price

    def calculate_discount(self, original_price: float, original_days: int) -> tuple:
        new_price = original_price
        new_days = original_days

        if self.discount_type == PromocodeDiscountType.PERCENT:
            new_price = original_price * (1 - self.discount_value / 100)
        elif self.discount_type == PromocodeDiscountType.FIXED:
            new_price = max(0, original_price - self.discount_value)
        elif self.discount_type == PromocodeDiscountType.DAYS:
            new_days = original_days + self.discount_value

        return round(new_price, 2), new_days

    def use(self) -> None:
        if self.uses_left > 0:
            self.uses_left -= 1
        if self.uses_left == 0:
            self.status = PromocodeStatus.EXPIRED