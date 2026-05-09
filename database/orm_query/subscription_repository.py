# database/orm_query/subscription_repository.py
from typing import Optional, List
from sqlalchemy import select
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
        return await self.get(sub_id, id_column="sub_id")

    async def get_by_user_id(self, user_id: int) -> List[Subscriptions]:
        """Получить все подписки пользователя"""
        return await self.get_all(user_id=user_id)

    async def get_active_subscription(self, user_id: int) -> Optional[Subscriptions]:
        """Получить активную подписку пользователя"""
        result = await self.session.execute(
            select(Subscriptions).where(
                Subscriptions.user_id == user_id,
                Subscriptions.status == SubscriptionStatus.ACTIVE
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(self, sub_id: str, status: SubscriptionStatus) -> Optional[Subscriptions]:
        """Обновить статус подписки"""
        return await self.update(sub_id, status=status)

    async def expire_subscription(self, sub_id: str) -> Optional[Subscriptions]:
        """Истекшая подписка"""
        return await self.update_status(sub_id, SubscriptionStatus.EXPIRED)

    async def block_subscription(self, sub_id: str) -> Optional[Subscriptions]:
        """Заблокировать подписку"""
        return await self.update_status(sub_id, SubscriptionStatus.BLOCKED)

    async def get_all_active(self) -> List[Subscriptions]:
        """Получить все активные подписки"""
        return await self.get_all(status=SubscriptionStatus.ACTIVE)
    
    # database/orm_query/subscription_repository.py (добавить)

    async def get_by_user_id(self, user_id: int) -> List[Subscriptions]:
        """Получить все подписки пользователя по user_id"""
        return await self.get_all(user_id=user_id)