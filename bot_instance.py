# bot_instance.py
from aiogram import Bot

# Создаем переменную для хранения экземпляра бота
_bot_instance = None

def set_bot_instance(bot: Bot):
    """Установить экземпляр бота"""
    global _bot_instance
    _bot_instance = bot

def get_bot_instance() -> Bot:
    """Получить экземпляр бота"""
    if _bot_instance is None:
        raise RuntimeError("Bot instance not initialized. Call set_bot_instance() first.")
    return _bot_instance