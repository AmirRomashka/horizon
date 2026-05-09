# database/enumerate/payment_enum.py
from enum import Enum


class PaymentStatus(str, Enum):
    """Статусы платежей"""
    PENDING = "pending"      # Ожидает оплаты
    PAID = "paid"            # Оплачен
    FAILED = "failed"        # Ошибка оплаты
    REFUNDED = "refunded"    # Возвращен

    @classmethod
    def get_all_values(cls) -> list:
        return [status.value for status in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.get_all_values()


class PaymentSystem(str, Enum):
    """Платежные системы"""
    STARS = "stars"          # Telegram Stars
    YOOKASSA = "yookassa"    # ЮKassa
    CRYPTOMUS = "cryptomus"  # Cryptomus
    MANUAL = "manual"        # Ручное зачисление

    @classmethod
    def get_all_values(cls) -> list:
        return [system.value for system in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        return value in cls.get_all_values()