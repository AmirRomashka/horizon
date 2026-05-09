# database/repositories/promocode_repository.py
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from database.orm_query.base_repository import BaseRepository
from database.models.promocode_model import Promocodes
from database.models.promocode_rate_model import PromocodeRates
from database.enumerate.promocode_enum import PromocodeStatus


class PromocodeRepository(BaseRepository[Promocodes]):
    """Репозиторий для работы с промокодами"""

    def __init__(self, session: AsyncSession):
        super().__init__(Promocodes, session)

    async def get_by_code(self, code: str) -> Optional[Promocodes]:
        """Получить промокод по коду"""
        return await self.get_by(code=code.upper())

    async def get_active_promocodes(self) -> List[Promocodes]:
        """Получить все активные промокоды"""
        now = datetime.now()
        result = await self.session.execute(
            select(Promocodes).where(
                Promocodes.status == PromocodeStatus.ACTIVE,
                Promocodes.uses_left > 0,
                (Promocodes.expires_at == None) | (Promocodes.expires_at > now)
            )
        )
        return result.scalars().all()

    async def use_promocode(self, promocode_id: int) -> Optional[Promocodes]:
        """Использовать промокод (уменьшить uses_left)"""
        promocode = await self.get(promocode_id)
        if promocode:
            promocode.use()
            await self.session.flush()
        return promocode

    async def get_promocode_rates(self, promocode_id: int) -> List[int]:
        """Получить список rate_id для промокода"""
        result = await self.session.execute(
            select(PromocodeRates.rate_id).where(
                PromocodeRates.promocode_id == promocode_id
            )
        )
        return result.scalars().all()

    async def add_rate_to_promocode(self, promocode_id: int, rate_id: int) -> None:
        """Привязать тариф к промокоду"""
        link = PromocodeRates(promocode_id=promocode_id, rate_id=rate_id)
        self.session.add(link)
        await self.session.flush()

    async def remove_rate_from_promocode(self, promocode_id: int, rate_id: int) -> None:
        """Отвязать тариф от промокода"""
        await self.session.execute(
            select(PromocodeRates).where(
                PromocodeRates.promocode_id == promocode_id,
                PromocodeRates.rate_id == rate_id
            )
        )