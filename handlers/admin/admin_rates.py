# handlers/admin/admin_rates.py
from typing import Union

from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from States.user_states import AdminStates
from database.orm_query.rate_repository import RateRepository
from database.enumerate.rate_enum import RateStatus
from tools import send_clean_message

AdminRatesRouter = Router(name="admin_rates_router")


# =============================================================================
# ОБРАБОТЧИКИ ВОЗВРАТА (без проверки состояния)
# =============================================================================

@AdminRatesRouter.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(call: types.CallbackQuery, state: FSMContext):
    """Возврат в админ-панель из любого состояния"""
    from handlers.admin.admin_panel import _show_admin_panel
    await state.clear()
    await _show_admin_panel(call, state, call.bot)


@AdminRatesRouter.callback_query(F.data == "admin_rates_set")
async def back_to_rates_list(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку тарифов из любого состояния"""
    await state.clear()
    await set_rates_logic(call, session)


# =============================================================================
# ОСНОВНЫЕ ОБРАБОТЧИКИ
# =============================================================================

@AdminRatesRouter.callback_query(F.data == "admin_rates_set", StateFilter(AdminStates.admin_panel))
async def set_rates(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """Управление тарифами — показывает список существующих тарифов и кнопку создания"""
    await set_rates_logic(call, session, state)


async def set_rates_logic(target: Union[types.Message, types.CallbackQuery], session: AsyncSession, state: FSMContext = None):
    """Логика показа списка тарифов"""
    if state:
        await state.set_state(AdminStates.admin_set_rates)
    
    rate_repo = RateRepository(session)
    rates = await rate_repo.get_all()
    
    btns = {}
    
    for rate in rates:
        status_emoji = "✅" if rate.status == RateStatus.ACTIVE else "❌"
        btns[f"{status_emoji} {rate.name} - {rate.price}₽"] = f"admin_rate_edit_{rate.id}"  # ← rate.id
    
    btns["➕ Создать новый тариф"] = "admin_rate_create"
    btns["🔙 Назад в админ-панель"] = "admin_panel"
    
    if rates:
        text = (
            "📋 <b>Управление тарифами</b>\n\n"
            f"📊 <b>Всего тарифов:</b> {len(rates)}\n"
            f"✅ <b>Активных:</b> {sum(1 for r in rates if r.status == RateStatus.ACTIVE)}\n"
            f"❌ <b>Неактивных:</b> {sum(1 for r in rates if r.status == RateStatus.INACTIVE)}\n\n"
            "⬇️ <b>Список тарифов:</b>\n"
            "Нажмите на тариф для редактирования"
        )
    else:
        text = (
            "📋 <b>Управление тарифами</b>\n\n"
            "❌ Тарифов пока нет\n\n"
            "Нажмите «Создать новый тариф» для добавления"
        )
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=btns,
        sizes=(1,)
    )


@AdminRatesRouter.callback_query(F.data.startswith("admin_rate_edit_"))
async def edit_rate(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """Редактирование конкретного тарифа"""
    rate_id = int(call.data.split("_")[-1])  # это id (первичный ключ)
    
    rate_repo = RateRepository(session)
    rate = await rate_repo.get(rate_id)  # поиск по id
    
    if not rate:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    
    await state.update_data(rate_id=rate.id)  # сохраняем id
    await state.set_state(AdminStates.admin_rate_edit)
    
    status_text = "Активен ✅" if rate.status == RateStatus.ACTIVE else "Неактивен ❌"
    
    text = (
        f"📝 <b>Редактирование тарифа</b>\n\n"
        f"🏷 <b>Название:</b> {rate.name}\n"
        f"💰 <b>Цена:</b> {rate.price}₽\n"
        f"📅 <b>Дней:</b> {rate.days}\n"
        f"📡 <b>Статус:</b> {status_text}\n\n"
        "⬇️ Выберите действие:"
    )
    
    btns = {
        "✏️ Изменить название": f"admin_rate_edit_name_{rate.id}",      # ← rate.id
        "💰 Изменить цену": f"admin_rate_edit_price_{rate.id}",         # ← rate.id
        "📅 Изменить дни": f"admin_rate_edit_days_{rate.id}",           # ← rate.id
        "🔄 Сменить статус": f"admin_rate_toggle_status_{rate.id}",     # ← rate.id
        "🗑 Удалить тариф": f"admin_rate_delete_{rate.id}",             # ← rate.id
        "🔙 Назад к списку": "admin_rates_set"
    }
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=btns,
        sizes=(1,)
    )


@AdminRatesRouter.callback_query(F.data.startswith("admin_rate_toggle_status_"))
async def toggle_rate_status(call: types.CallbackQuery, session: AsyncSession):
    """Переключение статуса тарифа (активен/неактивен)"""
    rate_id = int(call.data.split("_")[-1])  # это id
    
    rate_repo = RateRepository(session)
    rate = await rate_repo.get(rate_id)
    
    if not rate:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    
    new_status = RateStatus.INACTIVE if rate.status == RateStatus.ACTIVE else RateStatus.ACTIVE
    await rate_repo.update(rate_id, status=new_status)
    
    status_text = "активирован ✅" if new_status == RateStatus.ACTIVE else "деактивирован ❌"
    await call.answer(f"✅ Тариф {status_text}", show_alert=True)
    
    # Возвращаемся к списку тарифов
    await set_rates_logic(call, session)


@AdminRatesRouter.callback_query(F.data.startswith("admin_rate_delete_"))
async def delete_rate(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    """Удаление тарифа (с подтверждением)"""
    rate_id = int(call.data.split("_")[-1])  # это id
    
    await state.update_data(delete_rate_id=rate_id)
    await state.set_state(AdminStates.admin_rate_confirm_delete)
    
    btns = {
        "✅ Да, удалить": f"admin_rate_confirm_delete_{rate_id}",
        "❌ Нет, отмена": "admin_rates_set"
    }
    
    await send_clean_message(
        target=call,
        text="⚠️ <b>Внимание!</b>\n\nВы действительно хотите удалить этот тариф?\n\nЭто действие нельзя отменить.",
        buttons=btns,
        sizes=(1,)
    )


@AdminRatesRouter.callback_query(F.data.startswith("admin_rate_confirm_delete_"))
async def confirm_delete_rate(call: types.CallbackQuery, session: AsyncSession):
    """Подтверждение удаления тарифа"""
    rate_id = int(call.data.split("_")[-1])  # это id
    
    rate_repo = RateRepository(session)
    rate = await rate_repo.get(rate_id)
    
    if not rate:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    
    rate_name = rate.name
    await rate_repo.delete(rate_id)
    
    await call.answer(f"✅ Тариф «{rate_name}» удалён", show_alert=True)
    
    # Возвращаемся к списку тарифов
    await set_rates_logic(call, session)


# =============================================================================
# СОЗДАНИЕ ТАРИФА
# =============================================================================

@AdminRatesRouter.callback_query(F.data == "admin_rate_create")
async def create_rate_start(call: types.CallbackQuery, state: FSMContext):
    """Начало создания нового тарифа — запрос названия"""
    await state.set_state(AdminStates.admin_rate_create_name)
    
    text = (
        "➕ <b>Создание нового тарифа</b>\n\n"
        "Введите <b>название</b> тарифа:\n"
        "📌 Пример: «1 месяц», «3 месяца», «Premium»"
    )
    
    btns = {"🔙 Отмена": "admin_rates_set"}
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=btns,
        sizes=(1,)
    )


@AdminRatesRouter.message(StateFilter(AdminStates.admin_rate_create_name))
async def create_rate_get_name(message: types.Message, state: FSMContext):
    """Получение названия тарифа"""
    name = message.text.strip()
    
    if len(name) < 2:
        await message.answer("❌ Название слишком короткое. Введите минимум 2 символа:")
        return
    
    if len(name) > 100:
        await message.answer("❌ Название слишком длинное. Максимум 100 символов:")
        return
    
    await state.update_data(rate_name=name)
    await state.set_state(AdminStates.admin_rate_create_price)
    
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "💰 Введите <b>цену</b> тарифа (в рублях):\n"
        "📌 Пример: 89, 249, 429",
        parse_mode="HTML"
    )


@AdminRatesRouter.message(StateFilter(AdminStates.admin_rate_create_price))
async def create_rate_get_price(message: types.Message, state: FSMContext):
    """Получение цены тарифа"""
    try:
        price = float(message.text.strip().replace(",", "."))
        
        if price < 0:
            await message.answer("❌ Цена не может быть отрицательной. Введите корректную цену:")
            return
        
        if price > 100000:
            await message.answer("❌ Слишком большая цена. Максимум 100 000 ₽:")
            return
        
        await state.update_data(rate_price=price)
        await state.set_state(AdminStates.admin_rate_create_days)
        
        await message.answer(
            f"✅ Цена: <b>{price}₽</b>\n\n"
            "📅 Введите <b>количество дней</b> действия тарифа:\n"
            "📌 Пример: 30, 90, 365",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите корректное число (например: 89, 249, 429):")


@AdminRatesRouter.message(StateFilter(AdminStates.admin_rate_create_days))
async def create_rate_get_days(message: types.Message, state: FSMContext, session: AsyncSession):
    """Получение количества дней и создание тарифа"""
    try:
        days = int(message.text.strip())
        
        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0:")
            return
        
        if days > 1095:
            await message.answer("❌ Слишком много дней. Максимум 1095 дней (3 года):")
            return
        
        data = await state.get_data()
        name = data.get("rate_name")
        price = data.get("rate_price")
        
        rate_repo = RateRepository(session)
        rate = await rate_repo.create(
            name=name,
            price=price,
            days=days,
            status=RateStatus.ACTIVE
        )
        result = await session.commit()
        
        if not result:
            await message.answer("❌ Ошибка при создании тарифа.")
            return
        
        await message.answer(
            f"✅ <b>Тариф успешно создан!</b>\n\n"
            f"🏷 Название: {rate.name}\n"
            f"💰 Цена: {rate.price}₽\n"
            f"📅 Дней: {rate.days}\n"
            f"📡 Статус: Активен ✅",
            parse_mode="HTML"
        )
        
        await state.clear()
        
        # Возвращаемся к списку тарифов
        await set_rates_logic(message, session)
        
    except ValueError:
        await message.answer("❌ Введите целое число (например: 30, 90, 365):")