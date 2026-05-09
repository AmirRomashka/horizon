# database/repositories/payment_repository.py
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.base_repository import BaseRepository
from database.models.payment_model import Payments
from database.enumerate.payment_enum import PaymentStatus, PaymentSystem


class PaymentRepository(BaseRepository[Payments]):
    """Репозиторий для работы с платежами"""

    def __init__(self, session: AsyncSession):
        super().__init__(Payments, session)

    async def get_by_user_id(self, user_id: int, limit: int = 50) -> List[Payments]:
        """Получить платежи пользователя"""
        return await self.get_all(user_id=user_id, limit=limit)

    async def get_pending_payments(self) -> List[Payments]:
        """Получить все ожидающие платежи"""
        return await self.get_all(status=PaymentStatus.PENDING)

    async def get_by_external_id(self, external_id: str) -> Optional[Payments]:
        """Найти платёж по external_id (YooKassa)"""
        return await self.get_by(external_id=external_id)

    async def get_by_telegram_charge_id(self, charge_id: str) -> Optional[Payments]:
        """Найти платёж по telegram_payment_charge_id (Stars)"""
        return await self.get_by(telegram_payment_charge_id=charge_id)

    async def mark_as_paid(self, payment_id: int) -> Optional[Payments]:
        """Отметить платёж как оплаченный"""
        return await self.update(payment_id, status=PaymentStatus.PAID)

    async def mark_as_failed(self, payment_id: int) -> Optional[Payments]:
        """Отметить платёж как неудачный"""
        return await self.update(payment_id, status=PaymentStatus.FAILED)

    async def set_external_id(self, payment_id: int, external_id: str) -> Optional[Payments]:
        """Установить external_id для платежа"""
        return await self.update(payment_id, external_id=external_id)

    async def set_confirmation_url(self, payment_id: int, url: str) -> Optional[Payments]:
        """Установить confirmation_url для платежа"""
        return await self.update(payment_id, confirmation_url=url)