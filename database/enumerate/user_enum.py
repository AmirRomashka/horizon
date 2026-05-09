# database/enumerate/user_enum.py
from enum import Enum


class UserStatus(str, Enum):
    """Статусы пользователей бота"""
    USER = "user"
    ADMIN = "admin"
    BANNED = "banned"

    @classmethod
    def get_all_values(cls) -> list:
        """Возвращает список всех значений статусов"""
        return [status.value for status in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Проверяет, существует ли такой статус"""
        return value in cls.get_all_values()