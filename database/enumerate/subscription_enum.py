# database/enumerate/subscription_enum.py
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Статусы подписок"""
    ACTIVE = "active"        # Активна
    EXPIRED = "expired"      # Истекла
    BLOCKED = "blocked"      # Заблокирована
    LIMITED = "limited"      # Лимит трафика исчерпан

    @classmethod
    def get_all_values(cls) -> list:
        return [status.value for status in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.get_all_values()

