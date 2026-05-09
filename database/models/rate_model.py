# database/models/rate_model.py
from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base_model import Base
from database.enumerate.rate_enum import RateStatus


class Rates(Base):
    __tablename__ = "rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_limit_gb: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[RateStatus] = mapped_column(String(20), default=RateStatus.ACTIVE)

    def __repr__(self) -> str:
        return f"<Rates(id={self.id}, name={self.name}, price={self.price}, days={self.days}, status={self.status.value})>"

    def is_unlimited(self) -> bool:
        """Всегда True, так как лимит всегда 0"""
        return True

    def is_available(self) -> bool:
        return self.status == RateStatus.ACTIVE