# database/enumerate/rate_enum.py
from enum import Enum


class RateStatus(str, Enum):
    """Статусы тарифных планов"""
    ACTIVE = "active"
    INACTIVE = "inactive"

    @classmethod
    def get_all_values(cls) -> list:
        return [status.value for status in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.get_all_values()