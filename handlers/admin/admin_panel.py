# handlers/admin/admin_panel.py
import os
from typing import Union
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from States.user_states import AdminStates
from tools import send_clean_message

AdminPanelRouter = Router(name="admin_panel_router")


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    admin_id = os.getenv("admin_id")
    return str(user_id) == str(admin_id)


@AdminPanelRouter.message(Command("panel"))
async def admin_panel_message(
    message: types.Message, 
    state: FSMContext, 
    session: AsyncSession
):
    """Обработчик команды /panel"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    await _show_admin_panel(message, state, session)


@AdminPanelRouter.callback_query(F.data == "admin_panel")
async def admin_panel_callback(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Обработчик кнопки 'Админ-панель'"""
    if not is_admin(call.from_user.id):
        await call.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await _show_admin_panel(call, state, session)


async def _show_admin_panel(
    target: Union[types.Message, types.CallbackQuery],
    state: FSMContext,
    session: AsyncSession
):
    """Внутренняя функция для отображения админ-панели"""
    await state.clear()
    await state.set_state(AdminStates.admin_panel)
    
    btns = {
        "📋 Тарифы": "admin_rates_set",
        "🖥 Хосты": "admin_hosts_set"
    }
    
    sizes = (1, 1)
    
    text = (
        "👑 <b>Панель администратора</b>\n\n"
        "Выберите раздел для управления:"
    )
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=btns,
        sizes=sizes
    )