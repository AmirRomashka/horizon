# database/models/payment_model.py
from sqlalchemy import String, ForeignKey, BigInteger, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base_model import Base
from database.enumerate.payment_enum import PaymentStatus, PaymentSystem


class Payments(Base):
    __tablename__ = "payments"

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    rate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rates.id", ondelete="RESTRICT"),  # rates.rate_id → rates.id
        nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        String(20),
        default=PaymentStatus.PENDING
    )
    payment_system: Mapped[PaymentSystem] = mapped_column(
        String(20),
        nullable=False
    )
    # Для YooKassa
    external_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )
    confirmation_url: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    # Для Telegram Stars
    telegram_payment_charge_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    def __repr__(self) -> str:
        return f"<Payments(payment_id={self.payment_id}, user_id={self.user_id}, rate_id={self.rate_id}, amount={self.amount}, status={self.status.value}, payment_system={self.payment_system.value})>"

    def is_pending(self) -> bool:
        return self.status == PaymentStatus.PENDING

    def is_paid(self) -> bool:
        return self.status == PaymentStatus.PAID

    def mark_as_paid(self) -> None:
        self.status = PaymentStatus.PAID

    def mark_as_failed(self) -> None:
        self.status = PaymentStatus.FAILED