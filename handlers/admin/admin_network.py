import os
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from services.network_monitor import get_network_monitor

AdminNetworkRouter = Router(name="admin_network_router")


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    admin_id = os.getenv("admin_id")
    return str(user_id) == str(admin_id)


@AdminNetworkRouter.callback_query(F.data == "network_stats")
async def show_network_stats(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Показать статистику сети"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    monitor = get_network_monitor()
    
    if not monitor:
        await call.message.edit_text(
            "❌ Мониторинг сети не инициализирован\n\n"
            "Проверьте логи бота.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")]
                ]
            )
        )
        await call.answer()
        return
    
    # Получаем отчет
    report = monitor.get_uptime_report()
    
    # Кнопки для обновления и возврата
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="network_stats_refresh")],
            [types.InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")]
        ]
    )
    
    await call.message.edit_text(
        report,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await call.answer()


@AdminNetworkRouter.callback_query(F.data == "network_stats_refresh")
async def refresh_network_stats(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Обновить статистику сети"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    monitor = get_network_monitor()
    
    if not monitor:
        await call.answer("❌ Мониторинг не доступен", show_alert=True)
        return
    
    report = monitor.get_uptime_report()
    
    await call.message.edit_text(
        report,
        reply_markup=call.message.reply_markup,
        parse_mode="HTML"
    )
    
    await call.answer("🔄 Статистика обновлена")


@AdminNetworkRouter.message(Command("network"))
async def cmd_network_stats(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession
):
    """Команда /network - быстрая проверка сети"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа")
        return
    
    monitor = get_network_monitor()
    
    if not monitor:
        await message.answer("❌ Мониторинг сети не инициализирован")
        return
    
    report = monitor.get_uptime_report()
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 Обновить", callback_data="network_stats_refresh")],
            [types.InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_panel")]
        ]
    )
    
    await message.answer(
        report,
        reply_markup=keyboard,
        parse_mode="HTML"
    )