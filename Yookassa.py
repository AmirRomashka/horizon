# services/yookassa_service.py
import os
import uuid
import asyncio
from decimal import Decimal
from typing import Optional
from datetime import datetime

from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession
from yookassa import Configuration, Payment as YooPayment

from bot_instance import get_bot_instance
from database.orm_query import (
    PaymentRepository, RateRepository, HostRepository, 
    SubscriptionRepository, UserRepository
)
from database.enumerate.payment_enum import PaymentStatus
from database.enumerate.subscription_enum import SubscriptionStatus
from services.xui_client import XUIClient

# ======================================================================
# YOOKASSA CONFIGURATION
# ======================================================================

Configuration.account_id = os.getenv("SHOP_ID")
Configuration.secret_key = os.getenv("SECRET_KEY")


# ======================================================================
# СОЗДАНИЕ ПЛАТЕЖА
# ======================================================================

def create_payment(amount: int, user_id: int, rate_name: str, rate_days: int) -> YooPayment:
    """Создание платежа на покупку подписки"""
    payment_request = {
        "amount": {"value": str(amount), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/horizon_vpn_bot"},
        "description": f"Оплата подписки {rate_name} на {rate_days} дней",
        "capture": True,
        "metadata": {"user_id": user_id, "payment_type": "subscription", "rate_name": rate_name}
    }
    
    idempotency_key = str(uuid.uuid4())
    payment = YooPayment.create(payment_request, idempotency_key)
    ic(f"Created payment: {payment.id}, amount: {amount} RUB")
    return payment


# ======================================================================
# ОТМЕНА ПЛАТЕЖА
# ======================================================================

async def cancel_payment_by_id(payment_id: str) -> bool:
    """Отменяет платёж в YooKassa"""
    try:
        loop = asyncio.get_event_loop()
        payment = await loop.run_in_executor(None, YooPayment.find_one, payment_id)
        
        if payment.status == "pending":
            await loop.run_in_executor(None, payment.cancel)
            ic(f"Payment {payment_id} cancelled")
            return True
        return False
    except Exception as e:
        ic(f"Error cancelling payment {payment_id}: {e}")
        return False


# ======================================================================
# ПРОВЕРКА СТАТУСА ПЛАТЕЖА
# ======================================================================

async def check_payment_status(
    payment_id: str,
    user_id: int,
    session: AsyncSession,
    max_attempts: int = 60,
    check_interval: int = 10
) -> bool:
    """Проверка статуса платежа с созданием подписки при успехе"""
    payment_repo = PaymentRepository(session)
    bot = get_bot_instance()
    
    for attempt in range(1, max_attempts + 1):
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, YooPayment.find_one, payment_id)
            ic(f"Attempt {attempt}: Payment {payment_id} status - {response.status}")
            
            if response.status == "succeeded":
                payment = await payment_repo.get_by_external_id(payment_id)
                if not payment or payment.is_paid():
                    return True
                
                amount = int(Decimal(str(response.amount.value)))
                success = await _process_successful_payment(payment, user_id, session, amount)
                
                if success:
                    await bot.send_message(
                        user_id,
                        "✅ <b>Оплата прошла успешно!</b>\n\nВаша подписка активирована. Ссылка будет ниже 👇",
                        parse_mode="HTML"
                    )
                return success
                
            elif response.status == "canceled":
                payment = await payment_repo.get_by_external_id(payment_id)
                if payment:
                    payment.mark_as_failed()
                    await session.commit()
                
                await bot.send_message(
                    user_id,
                    "❌ <b>Платёж был отменён</b>\n\nПопробуйте снова или выберите другой тариф.",
                    parse_mode="HTML"
                )
                return False
                
        except Exception as e:
            ic(f"Payment check error (attempt {attempt}): {str(e)}")
        
        await asyncio.sleep(check_interval)
    
    await bot.send_message(
        user_id,
        "❌ <b>Не удалось подтвердить платёж</b>\n\nЕсли деньги списались, они вернутся в течение нескольких дней.\nСвяжитесь с поддержкой: @hor1zon_support",
        parse_mode="HTML"
    )
    return False


# ======================================================================
# ОБРАБОТКА УСПЕШНОГО ПЛАТЕЖА
# ======================================================================

async def _process_successful_payment(
    payment,
    user_id: int,
    session: AsyncSession,
    amount: int
) -> bool:
    """Обработка успешного платежа и создание подписки через API 3x-ui"""
    bot = get_bot_instance()
    
    try:
        # 1. Получаем тариф
        rate_repo = RateRepository(session)
        rate = await rate_repo.get(payment.rate_id)
        if not rate:
            ic(f"Rate {payment.rate_id} not found")
            return False
        
        # 2. Получаем хост
        host_repo = HostRepository(session)
        host = await host_repo.get_host_for_new_client()
        if not host:
            ic("No available hosts found")
            await bot.send_message(
                user_id,
                "❌ <b>Ошибка активации</b>\n\nВременно нет доступных серверов. "
                "Ваш платёж зарегистрирован, подписка будет активирована позже.\n"
                "Свяжитесь с поддержкой: @hor1zon_support",
                parse_mode="HTML"
            )
            return False
        
        # 3. Получаем пользователя
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(user_id)
        if not user:
            ic(f"User {user_id} not found")
            return False
        
        # 4. Создаём клиента через API
        # Запускаем синхронный XUIClient в потоке
        def create_client_sync():
            client = XUIClient(host)
            expiry_time = int((datetime.now().timestamp() + rate.days * 86400) * 1000)
            client_email = f"user_{user.user_id}_{rate.id}_{int(datetime.now().timestamp())}"
            
            ic(f"Creating client on {host.name}: inbound={host.inbound_id}, email={client_email}")
            
            success, client_data = client.add_client(
                inbound_id=host.inbound_id,
                email=client_email,
                expiry_time=expiry_time,
                total_gb=0
            )
            client.close()
            return success, client_data
        
        success, client_data = await asyncio.to_thread(create_client_sync)
        
        if not success or not client_data:
            ic(f"Failed to create client on host {host.name}")
            await bot.send_message(
                user_id,
                "❌ <b>Ошибка активации подписки</b>\n\nНе удалось создать клиента на сервере.\n"
                "Свяжитесь с поддержкой: @hor1zon_support",
                parse_mode="HTML"
            )
            return False
        
        vless_url = client_data.get("vless_url")
        if not vless_url:
            ic("No vless_url in client_data")
            return False
        
        # 5. Создаём подписку в БД
        subscription_repo = SubscriptionRepository(session)
        await subscription_repo.create(
            sub_id=client_data.get("id"),
            user_id=user.user_id,
            host_id=host.host_id,
            rate_id=rate.id,
            vless_url=vless_url,
            status=SubscriptionStatus.ACTIVE
        )
        
        # 6. Отмечаем платеж как оплаченный
        payment.mark_as_paid()
        host.current_clients += 1
        await session.commit()
        
        # 7. Отправляем VLESS ссылку
        vless_text = (
            f"🔗 <b>Ваша VLESS ссылка для подключения</b>\n\n"
            f"📋 <b>Тариф:</b> {rate.name}\n"
            f"📅 <b>Дней:</b> {rate.days}\n"
            f"💰 <b>Оплачено:</b> {amount}₽\n"
            f"🖥 <b>Сервер:</b> {host.name}\n\n"
            f"<code>{vless_url}</code>\n\n"
            f"📌 <i>Нажмите на ссылку для копирования</i>"
        )
        
        await bot.send_message(user_id, vless_text, parse_mode="HTML")
        
        ic(f"Subscription created for user {user_id}")
        return True
        
    except Exception as e:
        ic(f"Error processing successful payment: {e}")
        await session.rollback()
        
        await bot.send_message(
            user_id,
            f"❌ <b>Ошибка активации подписки</b>\n\nВаш платёж подтверждён, но произошла ошибка.\n"
            f"Свяжитесь с поддержкой: @hor1zon_support",
            parse_mode="HTML"
        )
        return False