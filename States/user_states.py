# States/user_states.py
from aiogram.fsm.state import StatesGroup, State


class MenuStates(StatesGroup):
    """Состояния главного меню"""
    start = State()


class AdminStates(StatesGroup):
    """Состояния админ-панели"""
    
    # ===== Основные состояния =====
    admin_panel = State()
    
    # ===== Управление тарифами =====
    admin_set_rates = State()           # Список тарифов
    admin_rate_edit = State()           # Редактирование тарифа
    admin_rate_confirm_delete = State() # Подтверждение удаления
    admin_rate_create_name = State()    # Создание: ввод названия
    admin_rate_create_price = State()   # Создание: ввод цены
    admin_rate_create_days = State()    # Создание: ввод дней
    
    # ===== Управление хостами =====
    admin_set_hosts = State()           # Список хостов
    admin_host_edit = State()           # Редактирование хоста
    admin_host_confirm_delete = State() # Подтверждение удаления
    admin_host_create_name = State()    # Создание: ввод названия
    admin_host_create_location = State() # Создание: ввод локации
    admin_host_create_api_url = State()  # Создание: ввод API URL
    admin_host_create_api_path = State() # Создание: ввод пути API (НОВОЕ)
    admin_host_create_username = State() # Создание: ввод username
    admin_host_create_password = State() # Создание: ввод password
    admin_host_create_inbound_id = State() # Создание: ввод inbound_id
    admin_host_create_max_clients = State() # Создание: ввод max_clients
    
    # ===== Редактирование хоста (поля) =====
    admin_host_edit_name = State()
    admin_host_edit_location = State()
    admin_host_edit_api_url = State()
    admin_host_edit_api_path = State()   # Редактирование пути API (НОВОЕ)
    admin_host_edit_username = State()
    admin_host_edit_password = State()
    admin_host_edit_inbound_id = State()
    admin_host_edit_max_clients = State()


class UserStates(StatesGroup):
    """Состояния пользовательской части"""
    
    # ===== Профиль =====
    user_profile = State()
    
    # ===== Покупка подписки =====
    buy_subscription = State()          # Выбор тарифа
    enter_promocode = State()           # Ввод промокода
    payment_waiting = State()           # Ожидание оплаты
    subscription_confirm = State()      # Подтверждение подписки
    payment_pending = State()           # Ожидание платежа (НОВОЕ)
    
    # ===== Поддержка =====
    support_message = State()           # Написание сообщения поддержке
    support_waiting = State()           # Ожидание ответа


class SubscriptionStates(StatesGroup):
    """Состояния для работы с подпиской"""
    get_vless = State()                 # Получение VLESS ссылки
    extend_subscription = State()       # Продление подписки
    check_status = State()              # Проверка статуса