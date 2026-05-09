# database/models/subscription_model.py
from sqlalchemy import String, ForeignKey, BigInteger, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from database.models.base_model import Base
from database.enumerate.subscription_enum import SubscriptionStatus


class Subscriptions(Base):
    __tablename__ = "subscriptions"

    sub_id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False
    )
    host_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("hosts.host_id", ondelete="CASCADE"),
        nullable=False
    )
    rate_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rates.id", ondelete="RESTRICT"),  # rates.rate_id → rates.id
        nullable=False
    )
    vless_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(50),
        default=SubscriptionStatus.ACTIVE
    )

    def __repr__(self) -> str:
        return f"<Subscriptions(sub_id={self.sub_id}, user_id={self.user_id}, rate_id={self.rate_id}, status={self.status.value}, host_id={self.host_id})>"

    def is_active(self) -> bool:
        return self.status == SubscriptionStatus.ACTIVE

    def is_expired(self) -> bool:
        return self.status == SubscriptionStatus.EXPIRED

    def is_blocked(self) -> bool:
        return self.status == SubscriptionStatus.BLOCKED

    def is_limited(self) -> bool:
        return self.status == SubscriptionStatus.LIMITED