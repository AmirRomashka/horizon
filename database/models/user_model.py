# database/models/user_model.py
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from database.models.base_model import Base
from database.enumerate.user_enum import UserStatus


class Users(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True, 
        autoincrement=False
    )
    status: Mapped[UserStatus] = mapped_column(
        String(20), 
        default=UserStatus.USER
    )

    def __repr__(self) -> str:
        return f"<BotUser(tg_id={self.user_id}, status={self.status.value})>"

    def is_admin(self) -> bool:
        """Проверка, является ли пользователь администратором"""
        return self.status == UserStatus.ADMIN

    def is_banned(self) -> bool:
        """Проверка, заблокирован ли пользователь"""
        return self.status == UserStatus.BANNED

    def is_user(self) -> bool:
        """Проверка, является ли пользователь обычным"""
        return self.status == UserStatus.USER