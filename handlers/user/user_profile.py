# handlers/user/user_profile.py
from typing import Union
from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from config import WORK_DIR
from tools import send_clean_message
from database.orm_query import UserRepository, SubscriptionRepository, RateRepository
from database.enumerate.rate_enum import RateStatus
from database.redis_client import RedisClient

UserProfileRouter = Router(name="user_profile")


# =============================================================================
# HELPERS
# =============================================================================

def get_profile_keyboard(has_active_subscription: bool) -> dict:
    """Возвращает кнопки профиля"""
    btns = {}
    if has_active_subscription:
        btns["📡 Моя подписка"] = "my_subscription"
    btns["❓ Помощь"] = "help"
    return btns


async def get_tariffs_keyboard(session: AsyncSession, has_subscription: bool = False) -> dict:
    """Возвращает кнопки с тарифами из БД"""
    rate_repo = RateRepository(session)
    rates = await rate_repo.get_active_rates()
    
    btns = {}
    emojis = ["⭐", "⚡", "🔥", "💎", "🎁"]
    
    callback_prefix = "extend_rate_" if has_subscription else "buy_rate_"
    
    for i, rate in enumerate(rates):
        emoji = emojis[i % len(emojis)]
        btns[f"{emoji} {rate.name} - {rate.price}₽"] = f"{callback_prefix}{rate.id}"
    
    return btns


def get_profile_photo_path() -> FSInputFile:
    """Возвращает путь к фото профиля"""
    photo_path = WORK_DIR / "image" / "user_images" / "profile_image.png"
    # image\user_images\profile_image.png
    ic(photo_path)
    return FSInputFile(str(photo_path))


def get_sizes_for_rates(rates_count: int) -> tuple:
    """Возвращает размеры кнопок в зависимости от количества тарифов"""
    return tuple(1 for _ in range(rates_count))


def format_vless_link(vless_url: str, max_length: int = 50) -> str:
    """Форматирует VLESS ссылку для отображения (скрывает часть)"""
    if len(vless_url) <= max_length:
        return vless_url
    return f"{vless_url[:max_length]}..."


def get_subscription_status(days_left: int) -> tuple:
    """Возвращает статус подписки и эмодзи"""
    if days_left <= 0:
        return "❌ Истекла", "🔴"
    elif days_left <= 3:
        return f"⚠️ Истекает ({days_left} дн.)", "⚠️"
    else:
        return "✅ Активна", "🟢"


# =============================================================================
# HANDLERS
# =============================================================================

@UserProfileRouter.message(CommandStart())
@UserProfileRouter.callback_query(F.data == "user_profile")
async def user_profile(
    event: Union[types.Message, types.CallbackQuery],
    state: FSMContext,
    session: AsyncSession,
    redis: RedisClient
):
    """Обработчик профиля пользователя"""
    await state.clear()
    
    user_id = event.from_user.id
    username = event.from_user.full_name or "гость"
    
    if isinstance(event, types.Message):
        message = event
        await message.delete()
    elif isinstance(event, types.CallbackQuery):
        message = event.message
        await event.answer()
    
    user_repo = UserRepository(session)
    user_data = await user_repo.get_by_tg_id(user_id)
    
    if not user_data:
        user_data = await user_repo.create(user_id=user_id)
        await session.commit()
    
    subscription_repo = SubscriptionRepository(session)
    active_sub = await subscription_repo.get_active_subscription(user_data.user_id)
    has_subscription = active_sub is not None
    
    tariffs_btns = await get_tariffs_keyboard(session, has_subscription)
    rates_count = len(tariffs_btns)
    
    if has_subscription:
        rate_repo = RateRepository(session)
        current_rate = await rate_repo.get(active_sub.rate_id)
        current_rate_name = current_rate.name if current_rate else "Неизвестный"
        
        # Используем expires_at из подписки (если есть), иначе вычисляем из created
        if active_sub.expires_at:
            expiry_date = active_sub.expires_at.date()
            days_left = (expiry_date - datetime.now().date()).days
            expiry_text = expiry_date.strftime('%d.%m.%Y')
        else:
            # Fallback для старых подписок
            expiry_date = (active_sub.created + timedelta(days=current_rate.days)).date()
            days_left = (expiry_date - datetime.now().date()).days
            expiry_text = expiry_date.strftime('%d.%m.%Y')
        
        status_text, status_emoji = get_subscription_status(days_left)
        
        text = (
                f"<b>{username}</b>\n\n"
                f"Статус: {status_emoji} {status_text}\n"
                f"Тариф: {current_rate_name}\n"
                f"Действует до: {expiry_text}\n"
                f"Осталось: {days_left} дн.\n\n"
                f"<b>VLESS</b>\n"
                f"<code>{format_vless_link(active_sub.vless_url)}</code>\n\n"
                f"<b>Продлить ↓</b>\n\n"
                f"@hor1zon_vpn  |  @Ilya_Nester0v"
)
    else:
        text = (
                f"Добро пожаловать, {username}.\n\n"
                f"<b>Horizon VPN.</b>\n"
                f"Ваша приватность — наша архитектура.\n\n"
                f"▸ Технология подключения:\n"
                f"  VLESS + REALITY\n"
                f"▸ Маскировка трафика\n"
                f"▸ Обход блокировок\n\n"
                f"<b>Доступные тарифы ↓</b>\n\n"
                f"▪️ Канал: @hor1zon_vpn\n"
                f"▪️ Поддержка: @Ilya_Nester0v"
)
    
    profile_btns = get_profile_keyboard(has_subscription)
    all_btns = {**tariffs_btns, **profile_btns}
    sizes = get_sizes_for_rates(rates_count) + (1,)
    photo = get_profile_photo_path()
    
    await send_clean_message(
        target=event,
        text=text,
        buttons=all_btns,
        sizes=sizes,
        photo=photo
    )


@UserProfileRouter.callback_query(F.data == "my_subscription")
async def my_subscription(
    call: types.CallbackQuery,
    session: AsyncSession,
    redis: RedisClient
):
    """Показывает подробную информацию о текущей подписке с полной VLESS ссылкой"""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_tg_id(call.from_user.id)
    
    if not user:
        await call.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    subscription_repo = SubscriptionRepository(session)
    active_sub = await subscription_repo.get_active_subscription(user.user_id)
    
    if not active_sub:
        await call.answer("❌ У вас нет активной подписки", show_alert=True)
        return
    
    rate_repo = RateRepository(session)
    rate = await rate_repo.get(active_sub.rate_id)
    
    if not rate:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    
    # Используем expires_at из подписки
    if active_sub.expires_at:
        expiry_date = active_sub.expires_at.date()
        days_left = (expiry_date - datetime.now().date()).days
    else:
        # Fallback для старых подписок
        expiry_date = (active_sub.created + timedelta(days=rate.days)).date()
        days_left = (expiry_date - datetime.now().date()).days
    
    # Статус с эмодзи
    if days_left <= 0:
        status_text = "❌ Истекла"
        status_emoji = "🔴"
    elif days_left <= 3:
        status_text = f"⚠️ СКОРО ИСТЕКАЕТ (осталось {days_left} дн.)"
        status_emoji = "⚠️"
    else:
        status_text = "✅ Активна"
        status_emoji = "🟢"
    
    text = (
        f"<b>Подписка Horizon</b>\n\n"
        f"Тариф: {rate.name}\n"
        f"Цена: {rate.price}₽\n"
        f"Дней: {rate.days}\n"
        f"Лимит: ∞\n\n"
        f"Начало: {active_sub.created.strftime('%d.%m.%Y')}\n"
        f"Окончание: {expiry_date.strftime('%d.%m.%Y')}\n"
        f"Осталось: {days_left} дн.\n"
        f"Статус: {status_emoji} {status_text}\n\n"
        f"<b>VLESS ссылка</b>\n"
        f"<code>{active_sub.vless_url}</code>\n\n"
        f"<i>Нажмите для копирования</i>"
)

    
    btns = {"🔙 Назад в профиль": "user_profile"}
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=btns,
        sizes=(1,)
    )
    await call.answer()


@UserProfileRouter.callback_query(F.data == "help")
async def help_handler(call: types.CallbackQuery, state: FSMContext, redis: RedisClient):
    """Помощь"""
    await state.clear()
    
    text = (
        f"<b>Horizon VPN</b>\n\n"
        f"Подключение:\n"
        f"1. Выберите тариф\n"
        f"2. Оплатите\n"
        f"3. Получите ссылку\n"
        f"4. Импортируйте в клиент\n\n"
        f"Клиенты:\n"
        f"V2Ray, Nekobox, Hiddify\n\n"
        f"Канал: @hor1zon_vpn\n"
        f"Поддержка: @Ilya_Nester0v"
)
    
    await send_clean_message(
        target=call,
        text=text,
        buttons={"🔙 Назад": "user_profile"},
        sizes=(1,)
    )