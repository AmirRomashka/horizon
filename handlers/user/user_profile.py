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
    """
    Возвращает кнопки с тарифами из БД
    Если есть активная подписка — кнопки ведут на продление (extend_rate_)
    Если нет подписки — кнопки ведут на покупку (buy_rate_)
    """
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
    photo_path = WORK_DIR / "image" / "user_images" / "profile_image.jpg"
    return FSInputFile(str(photo_path))


def get_sizes_for_rates(rates_count: int) -> tuple:
    """Возвращает размеры кнопок в зависимости от количества тарифов"""
    return tuple(1 for _ in range(rates_count))


def format_vless_link(vless_url: str, max_length: int = 50) -> str:
    """Форматирует VLESS ссылку для отображения (скрывает часть)"""
    if len(vless_url) <= max_length:
        return vless_url
    return f"{vless_url[:max_length]}..."


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
        
        from datetime import datetime, timedelta
        expiry_date = (active_sub.created + timedelta(days=current_rate.days)).date() if current_rate else None
        expiry_text = expiry_date.strftime('%d.%m.%Y') if expiry_date else "Неизвестно"
        days_left = (expiry_date - datetime.now().date()).days if expiry_date else 0
        
        # Формируем текст с информацией о подписке
        text = (
            f"👤 <b>Ваш профиль</b>\n\n"
            f"🆔 <b>Имя:</b> {username}\n"
            f"📡 <b>Статус:</b> ✅ Активна\n"
            f"📋 <b>Текущий тариф:</b> {current_rate_name}\n"
            f"⏰ <b>Действует до:</b> {expiry_text}\n"
            f"📅 <b>Осталось дней:</b> {days_left}\n\n"
            f"🔗 <b>VLESS ссылка:</b>\n"
            f"<code>{format_vless_link(active_sub.vless_url)}</code>\n\n"
            f"⬇️ <b>Выберите тариф для продления:</b>\n\n"
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
    """
    Показывает подробную информацию о текущей подписке с полной VLESS ссылкой
    """
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
    
    from datetime import datetime, timedelta
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
        f"📡 <b>Детали вашей подписки</b>\n\n"
        f"📋 <b>Тариф:</b> {rate.name}\n"
        f"💰 <b>Цена:</b> {rate.price}₽\n"
        f"📅 <b>Дней:</b> {rate.days}\n"
        f"📊 <b>Лимит:</b> Безлимит 🌊\n\n"
        f"📅 <b>Дата начала:</b> {active_sub.created.strftime('%d.%m.%Y')}\n"
        f"⏰ <b>Действует до:</b> {expiry_date.strftime('%d.%m.%Y')}\n"
        f"📆 <b>Осталось дней:</b> {days_left}\n"
        f"📡 <b>Статус:</b> {status_emoji} {status_text}\n\n"
        f"🔗 <b>Ваша VLESS ссылка для подключения:</b>\n"
        f"<code>{active_sub.vless_url}</code>\n\n"
        f"💡 <i>Нажмите на ссылку для копирования</i>\n\n"
        f"🔄 <b>Для продления</b> нажмите на любой тариф ниже"
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