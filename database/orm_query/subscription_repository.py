# database/orm_query/subscription_repository.py
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.base_repository import BaseRepository
from database.models.subscription_model import Subscriptions
from database.enumerate.subscription_enum import SubscriptionStatus


class SubscriptionRepository(BaseRepository[Subscriptions]):
    """Репозиторий для работы с подписками"""

    def __init__(self, session: AsyncSession):
        super().__init__(Subscriptions, session)

    async def get_by_sub_id(self, sub_id: str) -> Optional[Subscriptions]:
        """Получить подписку по UUID"""
        return await self.get_by_field("sub_id", sub_id)

    async def get_by_user_id(self, user_id: int) -> List[Subscriptions]:
        """Получить все подписки пользователя"""
        return await self.get_all(user_id=user_id)

    async def get_active_subscription(self, user_id: int) -> Optional[Subscriptions]:
        """Получить активную подписку пользователя (по статусу)"""
        result = await self.session.execute(
            select(Subscriptions).where(
                Subscriptions.user_id == user_id,
                Subscriptions.status == SubscriptionStatus.ACTIVE
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_subscription_by_date(self, user_id: int) -> Optional[Subscriptions]:
        """Получить активную подписку пользователя (по дате expires_at)"""
        now = datetime.now()
        result = await self.session.execute(
            select(Subscriptions).where(
                Subscriptions.user_id == user_id,
                Subscriptions.status == SubscriptionStatus.ACTIVE,
                Subscriptions.expires_at > now
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(self, sub_id: str, status: SubscriptionStatus) -> Optional[Subscriptions]:
        """Обновить статус подписки"""
        return await self.update(sub_id, status=status)

    async def update_expiry(self, sub_id: str, expires_at: datetime) -> Optional[Subscriptions]:
        """Обновить дату истечения подписки"""
        return await self.update(sub_id, expires_at=expires_at)

    async def expire_subscription(self, sub_id: str) -> Optional[Subscriptions]:
        """Истекшая подписка (обновляет статус)"""
        return await self.update_status(sub_id, SubscriptionStatus.EXPIRED)

    async def block_subscription(self, sub_id: str) -> Optional[Subscriptions]:
        """Заблокировать подписку"""
        return await self.update_status(sub_id, SubscriptionStatus.BLOCKED)

    async def get_all_active(self) -> List[Subscriptions]:
        """Получить все активные подписки (по статусу)"""
        return await self.get_all(status=SubscriptionStatus.ACTIVE)

    async def get_all_active_by_date(self) -> List[Subscriptions]:
        """Получить все активные подписки (по дате expires_at)"""
        now = datetime.now()
        result = await self.session.execute(
            select(Subscriptions).where(
                Subscriptions.status == SubscriptionStatus.ACTIVE,
                Subscriptions.expires_at > now
            )
        )
        return result.scalars().all()

    async def get_expiring_soon(self, days: int = 7) -> List[Subscriptions]:
        """Получить подписки, истекающие в ближайшие N дней"""
        now = datetime.now()
        soon = now.replace(days=days) if hasattr(now, 'replace') else now + timedelta(days=days)
        result = await self.session.execute(
            select(Subscriptions).where(
                Subscriptions.status == SubscriptionStatus.ACTIVE,
                Subscriptions.expires_at <= soon,
                Subscriptions.expires_at > now
            )
        )
        return result.scalars().all()

    async def update_subscription_after_payment(
        self, 
        sub_id: str, 
        new_rate_id: int, 
        additional_days: int
    ) -> Optional[Subscriptions]:
        """
        Обновляет подписку после успешного продления
        """
        subscription = await self.get_by_sub_id(sub_id)
        if not subscription:
            return None
        
        # Обновляем дату истечения
        if subscription.expires_at and subscription.expires_at > datetime.now():
            new_expiry = subscription.expires_at + timedelta(days=additional_days)
        else:
            new_expiry = datetime.now() + timedelta(days=additional_days)
        
        return await self.update(
            sub_id,
            rate_id=new_rate_id,
            expires_at=new_expiry,
            status=SubscriptionStatus.ACTIVE
        )