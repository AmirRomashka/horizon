# database/models/subscription_model.py
from sqlalchemy import String, ForeignKey, BigInteger, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4
from datetime import datetime

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
        ForeignKey("rates.id", ondelete="RESTRICT"),
        nullable=False
    )
    vless_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(50),
        default=SubscriptionStatus.ACTIVE
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True
    )

    def __repr__(self) -> str:
        return f"<Subscriptions(sub_id={self.sub_id}, user_id={self.user_id}, rate_id={self.rate_id}, status={self.status.value}, host_id={self.host_id}, expires_at={self.expires_at})>"

    def is_active(self) -> bool:
        return self.status == SubscriptionStatus.ACTIVE

    def is_expired(self) -> bool:
        return self.status == SubscriptionStatus.EXPIRED

    def is_blocked(self) -> bool:
        return self.status == SubscriptionStatus.BLOCKED

    def is_limited(self) -> bool:
        return self.status == SubscriptionStatus.LIMITED
    
    def is_expired_by_date(self) -> bool:
        """Проверяет, истекла ли подписка по дате"""
        if self.expires_at:
            return self.expires_at < datetime.now()
        return False
    
    def days_left(self) -> int:
        """Возвращает количество оставшихся дней"""
        if self.expires_at:
            return max(0, (self.expires_at - datetime.now()).days)
        return 0