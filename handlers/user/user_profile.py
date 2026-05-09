# handlers/user/user_profile.py
from typing import Union
from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from config import WORK_DIR
from tools import send_clean_message
from database.orm_query import UserRepository, SubscriptionRepository, RateRepository
from database.enumerate.rate_enum import RateStatus

UserProfileRouter = Router(name="user_profile")


# =============================================================================
# HELPERS
# =============================================================================

def get_profile_keyboard(has_active_subscription: bool) -> dict:
    """Возвращает кнопки профиля"""
    btns = {
        "❓ Помощь": "help"
    }
    return btns


async def get_tariffs_keyboard(session: AsyncSession) -> dict:
    """
    Возвращает кнопки с тарифами из БД
    Каждая кнопка вызывает callback для покупки (обрабатывается в user_payment.py)
    """
    rate_repo = RateRepository(session)
    rates = await rate_repo.get_active_rates()
    
    btns = {}
    emojis = ["⭐", "⚡", "🔥", "💎", "🎁"]
    
    for i, rate in enumerate(rates):
        emoji = emojis[i % len(emojis)]
        # Callback для покупки — будет обработан в user_payment.py
        btns[f"{emoji} {rate.name} - {rate.price}₽"] = f"buy_rate_{rate.id}"
    
    return btns


def get_profile_photo_path() -> FSInputFile:
    """Возвращает путь к фото профиля"""
    photo_path = WORK_DIR / "image" / "user_images" / "profile_image.jpg"
    return FSInputFile(str(photo_path))


def get_sizes_for_rates(rates_count: int) -> tuple:
    """
    Возвращает размеры кнопок в зависимости от количества тарифов
    По умолчанию: по одному в ряд
    """
    return tuple(1 for _ in range(rates_count))


# =============================================================================
# HANDLERS
# =============================================================================

@UserProfileRouter.message(CommandStart())
@UserProfileRouter.callback_query(F.data == "user_profile")
async def user_profile(
    event: Union[types.Message, types.CallbackQuery],
    state: FSMContext,
    session: AsyncSession
):
    """Обработчик профиля пользователя"""
    await state.clear()
    
    user_id = event.from_user.id
    username = event.from_user.full_name or "гость"
    
    # Обработка удаления/ответа
    if isinstance(event, types.Message):
        message = event
        await message.delete()
    elif isinstance(event, types.CallbackQuery):
        message = event.message
        await event.answer()
    
    # Получаем или создаём пользователя
    user_repo = UserRepository(session)
    user_data = await user_repo.get_by_tg_id(user_id)
    
    if not user_data:
        user_data = await user_repo.create(user_id=user_id)
        await session.commit()
    
    # Проверяем активную подписку
    subscription_repo = SubscriptionRepository(session)
    active_sub = await subscription_repo.get_active_subscription(user_data.user_id)
    has_subscription = active_sub is not None
    
    # Получаем кнопки тарифов из БД
    tariffs_btns = await get_tariffs_keyboard(session)
    rates_count = len(tariffs_btns)
    
    # Формируем текст
    if has_subscription:
        text = (
            f"👤 <b>Ваш профиль</b>\n\n"
            f"🆔 <b>Имя:</b> {username}\n"
            f"📡 <b>Статус:</b> ✅ Активна\n\n"
            f"⬇️ Ниже вы можете выбрать тариф\n"
            f"для продления подписки\n\n"
            f"📢 <b>Наш канал:</b> @hor1zon_vpn\n"
            f"💬 <b>Поддержка:</b> @Ilya_Nester0v"
        )
    else:
        text = (
            f"👋 <b>Добро пожаловать, {username}!</b>\n\n"
            f"🌍 <b>Horizon VPN</b> — надёжный и быстрый доступ к открытому интернету.\n\n"
            f"✅ Безлимитная скорость\n"
            f"✅ Защита ваших данных\n"
            f"✅ Поддержка 24/7\n\n"
            f"🔥 <b>Выберите подходящий тариф:</b>\n\n"
            f"📢 <b>Наш канал:</b> @hor1zon_vpn\n"
            f"💬 <b>Поддержка:</b> @Ilya_Nester0v"
        )
    
    # Формируем кнопки
    profile_btns = get_profile_keyboard(has_subscription)
    all_btns = {**tariffs_btns, **profile_btns}
    
    # Размеры: сначала все тарифы по одному, потом кнопки профиля (1 в ряд)
    sizes = get_sizes_for_rates(rates_count) + (1,)
    
    photo = get_profile_photo_path()
    
    await send_clean_message(
        target=event,
        text=text,
        buttons=all_btns,
        sizes=sizes,
        photo=photo
    )


@UserProfileRouter.callback_query(F.data == "help")
async def help_handler(call: types.CallbackQuery, state: FSMContext):
    """Помощь"""
    await state.clear()
    
    text = (
        "❓ <b>Помощь по боту Horizon VPN</b>\n\n"
        "🔹 <b>Как подключиться?</b>\n"
        "1. Выберите тариф и оплатите\n"
        "2. Получите VLESS ссылку\n"
        "3. Скачайте клиент (V2Ray, Nekobox, Hiddify)\n"
        "4. Импортируйте ссылку\n\n"
        "🔹 <b>Проблемы с подключением?</b>\n"
        "Проверьте интернет, смените протокол\n\n"
        f"📢 <b>Наш канал:</b> @hor1zon_vpn\n"
        f"💬 <b>Поддержка:</b> @Ilya_Nester0v"
    )
    
    await send_clean_message(
        target=call,
        text=text,
        buttons={"🔙 Назад": "user_profile"},
        sizes=(1,)
    )