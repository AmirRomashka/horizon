# database/models/promocode_rate_model.py
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base_model import Base


class PromocodeRates(Base):
    __tablename__ = "promocode_rates"

    promocode_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("promocodes.promocode_id", ondelete="CASCADE"),
        primary_key=True
    )
    rate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rates.id", ondelete="CASCADE"),  # rates.rate_id → rates.id
        primary_key=True
    )

    def __repr__(self) -> str:
        return f"<PromocodeRates(promocode_id={self.promocode_id}, rate_id={self.rate_id})>"