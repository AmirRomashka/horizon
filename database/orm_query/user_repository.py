# database/orm_query/user_repository.py
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.orm_query.base_repository import BaseRepository
from database.models.user_model import Users
from database.enumerate.user_enum import UserStatus


class UserRepository(BaseRepository[Users]):
    """Репозиторий для работы с пользователями"""

    def __init__(self, session: AsyncSession):
        super().__init__(Users, session)

    async def get_by_tg_id(self, tg_id: int) -> Optional[Users]:
        """Получить пользователя по Telegram ID"""
        return await self.get_by_field("user_id", tg_id)  # ← используем get_by_field

    async def get_admins(self) -> List[Users]:
        """Получить всех администраторов"""
        return await self.get_all(status=UserStatus.ADMIN)

    async def get_active_users(self) -> List[Users]:
        """Получить всех активных пользователей (не забаненных)"""
        result = await self.session.execute(
            select(Users).where(Users.status != UserStatus.BANNED)
        )
        return result.scalars().all()

    async def ban_user(self, tg_id: int) -> Optional[Users]:
        """Заблокировать пользователя"""
        user = await self.get_by_tg_id(tg_id)
        if user:
            return await self.update(user.user_id, status=UserStatus.BANNED)
        return None

    async def unban_user(self, tg_id: int) -> Optional[Users]:
        """Разблокировать пользователя"""
        user = await self.get_by_tg_id(tg_id)
        if user:
            return await self.update(user.user_id, status=UserStatus.USER)
        return None

    async def make_admin(self, tg_id: int) -> Optional[Users]:
        """Сделать пользователя администратором"""
        user = await self.get_by_tg_id(tg_id)
        if user:
            return await self.update(user.user_id, status=UserStatus.ADMIN)
        return None

    async def get_or_create(self, tg_id: int) -> Users:
        """Получить пользователя или создать если не существует"""
        user = await self.get_by_tg_id(tg_id)
        if not user:
            user = await self.create(user_id=tg_id, status=UserStatus.USER)
            await self.session.commit()
        return user