# database/orm_query/rate_repository.py
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.base_repository import BaseRepository
from database.models.rate_model import Rates
from database.enumerate.rate_enum import RateStatus


class RateRepository(BaseRepository[Rates]):
    """Репозиторий для работы с тарифами"""

    def __init__(self, session: AsyncSession):
        super().__init__(Rates, session)

    async def get_active_rates(self) -> List[Rates]:
        """Получить все активные тарифы"""
        return await self.get_all(status=RateStatus.ACTIVE)

    async def get_by_name(self, name: str) -> Optional[Rates]:
        """Получить тариф по имени"""
        return await self.get_by(name=name)
    
    # Добавить метод для поиска по rate_id (если нужно)
    async def get_by_rate_id(self, rate_id: int) -> Optional[Rates]:
        """Получить тариф по rate_id"""
        return await self.get_by(rate_id=rate_id)