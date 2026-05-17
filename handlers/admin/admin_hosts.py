import asyncio
from typing import Union
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from States.user_states import AdminStates
from database.models.host_model import Hosts
from database.orm_query.host_repository import HostRepository
from database.enumerate.host_enum import HostStatus
from tools import send_clean_message
from services.xui_client import XUIClient

AdminHostsRouter = Router(name="admin_hosts_router")


# =============================================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТОБРАЖЕНИЯ ФОРМЫ РЕДАКТИРОВАНИЯ
# =============================================================================

async def show_host_edit_form(
    target: Union[types.Message, types.CallbackQuery],
    host_id: int,
    session: AsyncSession,
    state: FSMContext = None
):
    ic(f"show_host_edit_form called, host_id={host_id}")
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    if not host:
        if isinstance(target, types.CallbackQuery):
            await target.answer("❌ Хост не найден", show_alert=True)
        else:
            await target.answer("❌ Хост не найден")
        return
    
    client = XUIClient(host)
    is_connected, connection_status = await asyncio.to_thread(client.test_connection)
    await asyncio.to_thread(client.close)
    
    if state:
        await state.update_data(host_id=host.host_id)
        await state.set_state(AdminStates.admin_host_edit)
    
    status_text = {
        HostStatus.ACTIVE: "Активен ✅",
        HostStatus.INACTIVE: "Неактивен ❌",
        HostStatus.MAINTENANCE: "На обслуживании 🔧"
    }.get(host.status, "Неизвестно")
    
    available_text = "Да" if host.is_available() else "Нет"
    api_status = "✅ Online" if is_connected else f"❌ Offline: {connection_status}"
    token_status = "✅ Есть" if host.api_token else "❌ Нет"
    
    text = (
        f"🖥 <b>Редактирование хоста</b>\n\n"
        f"🏷 <b>Название:</b> {host.name}\n"
        f"🌍 <b>Локация:</b> {host.location or 'Не указана'}\n"
        f"🔗 <b>API URL:</b> <code>{host.api_url}</code>\n"
        f"🔧 <b>API Path:</b> <code>{host.api_path or 'xui/API'}</code>\n"
        f"🔑 <b>API Token:</b> {token_status}\n"
        f"👤 <b>Username:</b> {host.username}\n"
        f"🔑 <b>Password:</b> {'*' * 10}\n"
        f"📡 <b>Inbound ID:</b> {host.inbound_id}\n"
        f"📊 <b>Статус:</b> {status_text}\n"
        f"📈 <b>Клиенты:</b> {host.current_clients} / {host.max_clients}\n"
        f"🟢 <b>Доступен для подключения:</b> {available_text}\n"
        f"🔌 <b>API статус:</b> {api_status}\n\n"
        "⬇️ Выберите действие:"
    )
    
    btns = {
        "✏️ Изменить название": f"admin_host_edit_name_{host.host_id}",
        "🌍 Изменить локацию": f"admin_host_edit_location_{host.host_id}",
        "🔗 Изменить API URL": f"admin_host_edit_url_{host.host_id}",
        "🔧 Изменить API Path": f"admin_host_edit_api_path_{host.host_id}",
        "🔑 Изменить API Token": f"admin_host_edit_api_token_{host.host_id}",
        "👤 Изменить username": f"admin_host_edit_username_{host.host_id}",
        "🔑 Изменить password": f"admin_host_edit_password_{host.host_id}",
        "📡 Изменить inbound_id": f"admin_host_edit_inbound_{host.host_id}",
        "📊 Изменить max_clients": f"admin_host_edit_maxclients_{host.host_id}",
        "🔄 Сменить статус": f"admin_host_toggle_status_{host.host_id}",
        "🔌 Проверить API": f"admin_host_check_api_{host.host_id}",
        "🔄 Синхронизировать клиентов": f"admin_host_sync_clients_{host.host_id}",
        "🗑 Удалить хост": f"admin_host_delete_{host.host_id}",
        "🔙 Назад к списку": "admin_hosts_set"
    }
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=btns,
        sizes=(1,)
    )


# =============================================================================
# ОБРАБОТЧИКИ ВОЗВРАТА
# =============================================================================

@AdminHostsRouter.callback_query(F.data == "admin_panel")
async def back_to_admin_panel(call: types.CallbackQuery, state: FSMContext):
    ic("Back to admin panel")
    from handlers.admin.admin_panel import _show_admin_panel
    await state.clear()
    await _show_admin_panel(call, state, call.bot)


@AdminHostsRouter.callback_query(F.data == "admin_hosts_set")
async def back_to_hosts_list(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    ic("Back to hosts list")
    await state.clear()
    await set_hosts_logic(call, session)


# =============================================================================
# ОСНОВНЫЕ ОБРАБОТЧИКИ
# =============================================================================

@AdminHostsRouter.callback_query(F.data == "admin_hosts_set", StateFilter(AdminStates.admin_panel))
async def set_hosts(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    ic("Set hosts called")
    await set_hosts_logic(call, session)


async def set_hosts_logic(target: Union[types.Message, types.CallbackQuery], session: AsyncSession, state: FSMContext = None):
    ic(f"Set hosts logic, target_type={type(target).__name__}")
    
    if state:
        await state.set_state(AdminStates.admin_set_hosts)
    
    host_repo = HostRepository(session)
    hosts = await host_repo.get_all()
    ic(f"Found {len(hosts)} hosts")
    
    btns = {}
    
    for host in hosts:
        status_emoji = "✅" if host.status == HostStatus.ACTIVE else "❌"
        btns[f"{status_emoji} {host.name}"] = f"admin_host_edit_{host.host_id}"
    
    btns["➕ Создать новый хост"] = "admin_host_create"
    btns["🔙 Назад в админ-панель"] = "admin_panel"
    
    if hosts:
        active_count = sum(1 for h in hosts if h.status == HostStatus.ACTIVE)
        inactive_count = sum(1 for h in hosts if h.status == HostStatus.INACTIVE)
        maintenance_count = sum(1 for h in hosts if h.status == HostStatus.MAINTENANCE)
        
        text = (
            "🖥 <b>Управление хостами</b>\n\n"
            f"📊 <b>Всего хостов:</b> {len(hosts)}\n"
            f"✅ <b>Активных:</b> {active_count}\n"
            f"❌ <b>Неактивных:</b> {inactive_count}\n"
            f"🔧 <b>На обслуживании:</b> {maintenance_count}\n\n"
            "⬇️ <b>Список хостов:</b>\n"
            "Нажмите на хост для редактирования"
        )
    else:
        text = (
            "🖥 <b>Управление хостами</b>\n\n"
            "❌ Хостов пока нет\n\n"
            "Нажмите «Создать новый хост» для добавления"
        )
    
    await send_clean_message(
        target=target,
        text=text,
        buttons=btns,
        sizes=(1,)
    )


@AdminHostsRouter.callback_query(F.data.startswith("admin_host_edit_"))
async def edit_host(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    host_id = int(call.data.split("_")[-1])
    ic(f"Edit host: {host_id}")
    await show_host_edit_form(call, host_id, session, state)


# =============================================================================
# РЕДАКТИРОВАНИЕ API TOKEN
# =============================================================================

@AdminHostsRouter.callback_query(F.data.startswith("admin_host_edit_api_token_"))
async def edit_host_api_token_start(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    host_id = int(call.data.split("_")[-1])
    ic(f"Edit API token start: host_id={host_id}")
    
    await state.update_data(edit_host_id=host_id)
    await state.set_state(AdminStates.admin_host_edit_api_token)
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    current_token_status = "есть" if host and host.api_token else "отсутствует"
    
    await call.message.answer(
        "🔑 Введите <b>API Token</b> для авторизации в 3x-ui:\n\n"
        "📌 Где взять токен:\n"
        "1. Войдите в админ-панель 3x-ui\n"
        "2. Перейдите в Settings → Security\n"
        "3. Создайте новый API Token (например, «horizon_bot»)\n"
        "4. Скопируйте сгенерированный токен\n\n"
        f"🔐 Текущий статус: {current_token_status}\n\n"
        "⚠️ Отправьте «-» чтобы удалить токен\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )
    await call.answer()


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_edit_api_token))
async def edit_host_api_token_save(message: types.Message, state: FSMContext, session: AsyncSession):
    api_token = message.text.strip()
    ic(f"Edit API token save: token={'*' * len(api_token) if api_token else 'empty'}")
    
    data = await state.get_data()
    host_id = data.get("edit_host_id")
    
    if not host_id:
        await message.answer("❌ Ошибка: ID хоста не найден")
        await state.clear()
        return
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    if not host:
        await message.answer("❌ Хост не найден")
        await state.clear()
        return
    
    # Если "-" - удаляем токен
    if api_token == "-":
        api_token = None
        await host_repo.update(host_id, api_token=api_token)
        await session.commit()
        await message.answer(f"✅ API Token удалён для хоста <b>{host.name}</b>", parse_mode="HTML")
    elif api_token:
        await host_repo.update(host_id, api_token=api_token)
        await session.commit()
        await message.answer(f"✅ API Token сохранён для хоста <b>{host.name}</b>", parse_mode="HTML")
    else:
        await message.answer("❌ Неверный формат. Отправьте токен или «-» для удаления")
        return
    
    await state.clear()
    await show_host_edit_form(message, host_id, session)


# =============================================================================
# РЕДАКТИРОВАНИЕ API PATH
# =============================================================================

@AdminHostsRouter.callback_query(F.data.startswith("admin_host_edit_api_path_"))
async def edit_host_api_path_start(call: types.CallbackQuery, state: FSMContext):
    host_id = int(call.data.split("_")[-1])
    ic(f"Edit API path start: host_id={host_id}")
    
    await state.update_data(edit_host_id=host_id)
    await state.set_state(AdminStates.admin_host_edit_api_path)
    
    await call.message.answer(
        "🔧 Введите <b>новый путь к API</b>:\n\n"
        "• <code>xui/API</code> - стандартный путь\n"
        "• <code>panel/api</code> - для новых версий\n\n"
        "📌 Оставьте пустым для значения по умолчанию",
        parse_mode="HTML"
    )
    await call.answer()


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_edit_api_path))
async def edit_host_api_path_save(message: types.Message, state: FSMContext, session: AsyncSession):
    api_path = message.text.strip()
    ic(f"Edit API path save: api_path={api_path}")
    
    if not api_path:
        api_path = "xui/API"
    
    api_path = api_path.strip('/')
    
    data = await state.get_data()
    host_id = data.get("edit_host_id")
    ic(f"Edit API path: host_id={host_id}")
    
    if not host_id:
        await message.answer("❌ Ошибка: ID хоста не найден")
        await state.clear()
        return
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    if not host:
        ic(f"Edit API path: host not found, host_id={host_id}")
        await message.answer("❌ Хост не найден")
        await state.clear()
        return
    
    await host_repo.update(host_id, api_path=api_path)
    await session.commit()
    ic(f"Edit API path: updated host_id={host_id}")
    
    await message.answer(f"✅ Путь API изменён на: <code>{api_path}</code>", parse_mode="HTML")
    await state.clear()
    await show_host_edit_form(message, host_id, session)


# =============================================================================
# ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (ПРОВЕРКА API, СИНХРОНИЗАЦИЯ, СТАТУС, УДАЛЕНИЕ)
# =============================================================================

@AdminHostsRouter.callback_query(F.data.startswith("admin_host_check_api_"))
async def check_host_api(call: types.CallbackQuery, session: AsyncSession):
    host_id = int(call.data.split("_")[-1])
    ic(f"Check API for host: {host_id}")
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    if not host:
        await call.answer("❌ Хост не найден", show_alert=True)
        return
    
    await call.answer("🔄 Проверяем подключение...", show_alert=False)
    
    client = XUIClient(host)
    is_connected, message = await asyncio.to_thread(client.test_connection)
    await asyncio.to_thread(client.close)
    
    if is_connected:
        if host.status != HostStatus.ACTIVE:
            await host_repo.update(host_id, status=HostStatus.ACTIVE, is_active=True)
            await session.commit()
        await call.answer(f"✅ API доступен!", show_alert=True)
    else:
        await call.answer(f"❌ Ошибка: {message[:50]}", show_alert=True)
    
    await show_host_edit_form(call, host_id, session)


@AdminHostsRouter.callback_query(F.data.startswith("admin_host_sync_clients_"))
async def sync_host_clients(call: types.CallbackQuery, session: AsyncSession):
    host_id = int(call.data.split("_")[-1])
    ic(f"Sync clients for host: {host_id}")
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    if not host:
        await call.answer("❌ Хост не найден", show_alert=True)
        return
    
    await call.answer("🔄 Синхронизируем клиентов...", show_alert=False)
    
    client = XUIClient(host)
    is_connected, _ = await asyncio.to_thread(client.test_connection)
    
    if not is_connected:
        await call.answer("❌ API недоступен, синхронизация невозможна", show_alert=True)
        await asyncio.to_thread(client.close)
        return
    
    clients_count = await asyncio.to_thread(client.get_clients_count)
    await asyncio.to_thread(client.close)
    
    if clients_count >= 0:
        await host_repo.update(host_id, current_clients=clients_count)
        await session.commit()
        await call.answer(f"✅ Синхронизировано! Клиентов: {clients_count}", show_alert=True)
    else:
        await call.answer("❌ Ошибка при получении данных", show_alert=True)
    
    await show_host_edit_form(call, host_id, session)


@AdminHostsRouter.callback_query(F.data.startswith("admin_host_toggle_status_"))
async def toggle_host_status(call: types.CallbackQuery, session: AsyncSession):
    host_id = int(call.data.split("_")[-1])
    ic(f"Toggle status for host: {host_id}")
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    if not host:
        await call.answer("❌ Хост не найден", show_alert=True)
        return
    
    status_cycle = {
        HostStatus.ACTIVE: HostStatus.MAINTENANCE,
        HostStatus.MAINTENANCE: HostStatus.INACTIVE,
        HostStatus.INACTIVE: HostStatus.ACTIVE
    }
    
    new_status = status_cycle.get(host.status, HostStatus.ACTIVE)
    await host_repo.update(host_id, status=new_status)
    await session.commit()
    
    status_text = {
        HostStatus.ACTIVE: "активирован ✅",
        HostStatus.INACTIVE: "деактивирован ❌",
        HostStatus.MAINTENANCE: "переведён на обслуживание 🔧"
    }.get(new_status, "изменён")
    
    await call.answer(f"✅ Хост {status_text}", show_alert=True)
    await set_hosts_logic(call, session)


@AdminHostsRouter.callback_query(F.data.startswith("admin_host_delete_"))
async def delete_host(call: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    host_id = int(call.data.split("_")[-1])
    ic(f"Delete host: {host_id}")
    
    await state.update_data(delete_host_id=host_id)
    await state.set_state(AdminStates.admin_host_confirm_delete)
    
    btns = {
        "✅ Да, удалить": f"admin_host_confirm_delete_{host_id}",
        "❌ Нет, отмена": "admin_hosts_set"
    }
    
    await send_clean_message(
        target=call,
        text="⚠️ <b>Внимание!</b>\n\nВы действительно хотите удалить этот хост?\n\nЭто действие нельзя отменить.",
        buttons=btns,
        sizes=(1,)
    )


@AdminHostsRouter.callback_query(F.data.startswith("admin_host_confirm_delete_"))
async def confirm_delete_host(call: types.CallbackQuery, session: AsyncSession):
    host_id = int(call.data.split("_")[-1])
    ic(f"Confirm delete host: {host_id}")
    
    host_repo = HostRepository(session)
    host = await host_repo.get(host_id)
    
    if not host:
        await call.answer("❌ Хост не найден", show_alert=True)
        return
    
    host_name = host.name
    await host_repo.delete(host_id)
    await session.commit()
    
    await call.answer(f"✅ Хост «{host_name}» удалён", show_alert=True)
    await set_hosts_logic(call, session)


# =============================================================================
# СОЗДАНИЕ ХОСТА
# =============================================================================

@AdminHostsRouter.callback_query(F.data == "admin_host_create")
async def create_host_start(call: types.CallbackQuery, state: FSMContext):
    ic("Create host started")
    await state.set_state(AdminStates.admin_host_create_name)
    
    text = (
        "➕ <b>Создание нового хоста</b>\n\n"
        "Введите <b>название</b> хоста:\n"
        "📌 Пример: «Amsterdam», «Frankfurt», «Singapore»"
    )
    
    btns = {"🔙 Отмена": "admin_hosts_set"}
    
    await send_clean_message(
        target=call,
        text=text,
        buttons=btns,
        sizes=(1,)
    )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_name))
async def create_host_get_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    ic(f"Create host: name={name}")
    
    if len(name) < 2:
        await message.answer("❌ Название слишком короткое. Введите минимум 2 символа:")
        return
    
    if len(name) > 100:
        await message.answer("❌ Название слишком длинное. Максимум 100 символов:")
        return
    
    await state.update_data(host_name=name)
    await state.set_state(AdminStates.admin_host_create_location)
    
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "🌍 Введите <b>локацию</b> хоста (или отправьте «-» для пропуска):\n"
        "📌 Пример: «Нидерланды, Амстердам», «Германия, Франкфурт»",
        parse_mode="HTML"
    )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_location))
async def create_host_get_location(message: types.Message, state: FSMContext):
    location = message.text.strip()
    ic(f"Create host: location={location}")
    
    if location == "-":
        location = None
    
    await state.update_data(host_location=location)
    await state.set_state(AdminStates.admin_host_create_api_url)
    
    location_text = location if location else "не указана"
    
    await message.answer(
        f"✅ Локация: <b>{location_text}</b>\n\n"
        "🔗 Введите <b>API URL</b> хоста:\n"
        "📌 Пример: https://ams.horizon-vpn.com:443\n"
        "⚠️ URL должен включать протокол (http:// или https://)",
        parse_mode="HTML"
    )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_api_url))
async def create_host_get_api_url(message: types.Message, state: FSMContext):
    api_url = message.text.strip()
    ic(f"Create host: API URL={api_url}")
    
    if not api_url.startswith(("http://", "https://")):
        await message.answer("❌ URL должен начинаться с http:// или https://:")
        return
    
    await state.update_data(host_api_url=api_url)
    await state.set_state(AdminStates.admin_host_create_api_path)
    
    await message.answer(
        f"✅ API URL: <code>{api_url}</code>\n\n"
        "🔧 Введите <b>путь к API</b> 3x-ui:\n"
        "• <code>xui/API</code> - стандартный путь\n"
        "• <code>panel/api</code> - для новых версий\n"
        "• <code>api</code> - альтернативный вариант\n\n"
        "📌 Оставьте пустым для значения по умолчанию",
        parse_mode="HTML"
    )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_api_path))
async def create_host_get_api_path(message: types.Message, state: FSMContext):
    api_path = message.text.strip()
    ic(f"Create host: API path={api_path}")
    
    if not api_path:
        api_path = "xui/API"
    
    api_path = api_path.strip('/')
    
    await state.update_data(host_api_path=api_path)
    await state.set_state(AdminStates.admin_host_create_api_token)
    
    await message.answer(
        f"✅ Путь API: <code>{api_path}</code>\n\n"
        "🔑 Введите <b>API Token</b> для авторизации в панели 3x-ui:\n\n"
        "📌 Где взять токен:\n"
        "1. Войдите в админ-панель 3x-ui\n"
        "2. Перейдите в Settings → Security\n"
        "3. Создайте новый API Token (например, «horizon_bot»)\n"
        "4. Скопируйте сгенерированный токен\n\n"
        "💡 <b>Это поле НЕ обязательно</b>. Если оставить пустым, будет использоваться логин/пароль.\n"
        "⚠️ Отправьте «-» чтобы пропустить\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_api_token))
async def create_host_get_api_token(message: types.Message, state: FSMContext):
    api_token = message.text.strip()
    ic(f"Create host: API token={'*' * len(api_token) if api_token else 'empty'}")
    
    # Если "-", значит пропускаем (оставляем пустой)
    if api_token == "-":
        api_token = None
    elif api_token == "":
        api_token = None
    
    await state.update_data(host_api_token=api_token)
    await state.set_state(AdminStates.admin_host_create_username)
    
    if api_token:
        await message.answer(
            f"✅ API Token сохранён\n\n"
            "👤 Введите <b>username</b> для авторизации в панели 3x-ui:\n"
            "📌 Обычно admin\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "⚠️ API Token не указан. Будет использоваться авторизация по логину/паролю.\n\n"
            "👤 Введите <b>username</b> для авторизации в панели 3x-ui:\n"
            "📌 Обычно admin\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_username))
async def create_host_get_username(message: types.Message, state: FSMContext):
    username = message.text.strip()
    ic(f"Create host: username={username}")
    
    if len(username) < 2:
        await message.answer("❌ Username слишком короткий:")
        return
    
    await state.update_data(host_username=username)
    await state.set_state(AdminStates.admin_host_create_password)
    
    await message.answer(
        f"✅ Username: <b>{username}</b>\n\n"
        "🔑 Введите <b>password</b> для авторизации в панели 3x-ui:\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_password))
async def create_host_get_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    ic(f"Create host: password_len={len(password)}")
    
    if len(password) < 2:
        await message.answer("❌ Password слишком короткий:")
        return
    
    await state.update_data(host_password=password)
    await state.set_state(AdminStates.admin_host_create_inbound_id)
    
    await message.answer(
        f"✅ Password: <b>{'*' * len(password)}</b>\n\n"
        "📡 Введите <b>inbound_id</b> (обычно 1):\n"
        "📌 Пример: 1, 2, 3\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_inbound_id))
async def create_host_get_inbound_id(message: types.Message, state: FSMContext):
    try:
        inbound_id = int(message.text.strip())
        ic(f"Create host: inbound_id={inbound_id}")
        
        if inbound_id < 1:
            await message.answer("❌ inbound_id должен быть больше 0:")
            return
        
        await state.update_data(host_inbound_id=inbound_id)
        await state.set_state(AdminStates.admin_host_create_max_clients)
        
        await message.answer(
            f"✅ inbound_id: <b>{inbound_id}</b>\n\n"
            "📊 Введите <b>max_clients</b> (максимальное количество клиентов на хосте):\n"
            "📌 Пример: 100, 200, 500\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )
        
    except ValueError:
        ic(f"Create host: invalid inbound_id={message.text.strip()}")
        await message.answer("❌ Введите целое число:")


@AdminHostsRouter.message(StateFilter(AdminStates.admin_host_create_max_clients))
async def create_host_get_max_clients(message: types.Message, state: FSMContext, session: AsyncSession):
    ic("Create host: get max_clients called")
    
    try:
        max_clients = int(message.text.strip())
        ic(f"Create host: max_clients={max_clients}")
        
        if max_clients < 1:
            await message.answer("❌ max_clients должен быть больше 0:")
            return
        
        if max_clients > 10000:
            await message.answer("❌ Слишком большое значение. Максимум 10000:")
            return
        
        data = await state.get_data()
        ic(f"Create host: collected data keys={list(data.keys())}")
        
        temp_host = Hosts(
            name=data.get("host_name"),
            api_url=data.get("host_api_url"),
            api_path=data.get("host_api_path", "xui/API"),
            api_token=data.get("host_api_token"),
            username=data.get("host_username"),
            password=data.get("host_password"),
            inbound_id=data.get("host_inbound_id", 1),
            location=data.get("host_location"),
            status=HostStatus.ACTIVE,
            is_active=True,
            max_clients=max_clients,
            current_clients=0
        )
        
        status_msg = await message.answer("🔄 Проверяем подключение к API... Подождите.")
        ic(f"Create host: testing connection to {temp_host.api_url}, path={temp_host.api_path}")
        
        client = XUIClient(temp_host)
        is_connected, connection_message = await asyncio.to_thread(client.test_connection)
        await asyncio.to_thread(client.close)
        ic(f"Create host: connection result={is_connected}, message={connection_message}")
        
        if not is_connected:
            await status_msg.edit_text(
                f"❌ <b>Ошибка подключения к API</b>\n\n"
                f"{connection_message}\n\n"
                f"Проверьте данные и попробуйте снова.\n\n"
                f"💡 Совет: используйте API Token вместо логина/пароля",
                parse_mode="HTML"
            )
            return
        
        await status_msg.edit_text("✅ Подключение успешно! Сохраняем хост...")
        
        host_repo = HostRepository(session)
        host = await host_repo.create(
            name=data.get("host_name"),
            api_url=data.get("host_api_url"),
            api_path=data.get("host_api_path", "xui/API"),
            api_token=data.get("host_api_token"),
            username=data.get("host_username"),
            password=data.get("host_password"),
            inbound_id=data.get("host_inbound_id", 1),
            location=data.get("host_location"),
            status=HostStatus.ACTIVE,
            is_active=True,
            max_clients=max_clients,
            current_clients=0
        )
        await session.commit()
        ic(f"Create host: created host_id={host.host_id}")
        
        text = (
            f"✅ <b>Хост успешно создан!</b>\n\n"
            f"🏷 Название: {host.name}\n"
            f"🌍 Локация: {host.location or 'Не указана'}\n"
            f"🔗 API URL: <code>{host.api_url}</code>\n"
            f"🔧 API Path: <code>{host.api_path}</code>\n"
            f"🔑 API Token: {'✅ Есть' if host.api_token else '❌ Нет'}\n"
            f"👤 Username: {host.username}\n"
            f"📡 inbound_id: {host.inbound_id}\n"
            f"📊 max_clients: {host.max_clients}\n"
            f"📡 Статус: Активен ✅\n"
            f"🟢 Доступен: {'Да' if host.is_available() else 'Нет'}\n\n"
            f"🔌 API статус: ✅ Подключено\n\n"
            f"<i>Хост готов к работе</i>"
        )
        
        await status_msg.edit_text(text, parse_mode="HTML")
        await state.clear()
        
        ic("Create host: returning to hosts list")
        await set_hosts_logic(message, session)
        
    except Exception as e:
        ic(f"Create host: ERROR = {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")


# =============================================================================
# ОБРАБОТЧИК ОТМЕНЫ
# =============================================================================

@AdminHostsRouter.message(F.text == "/cancel")
async def cancel_action(message: types.Message, state: FSMContext):
    ic("Cancel action")
    current_state = await state.get_state()
    
    if current_state and current_state.startswith("AdminStates.admin_host"):
        await state.clear()
        await message.answer("✅ Действие отменено\n\nИспользуйте /panel для входа в админ-панель")
    else:
        await message.answer("❌ Нет активного действия для отмены")