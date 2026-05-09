# database/enumerate/promocode_enum.py
from enum import Enum


class PromocodeDiscountType(str, Enum):
    """Типы скидок промокодов"""
    PERCENT = "percent"    # Процентная скидка
    FIXED = "fixed"        # Фиксированная скидка (в валюте)
    DAYS = "days"          # Добавление бесплатных дней

    @classmethod
    def get_all_values(cls) -> list:
        return [type_.value for type_ in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.get_all_values()


class PromocodeStatus(str, Enum):
    """Статусы промокодов"""
    ACTIVE = "active"      # Активен
    EXPIRED = "expired"    # Просрочен
    DISABLED = "disabled"  # Отключен вручную

    @classmethod
    def get_all_values(cls) -> list:
        return [status.value for status in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.get_all_values()