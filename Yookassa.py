# services/Yookassa.py
import os
import uuid
import asyncio
import json
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
from database.redis_client import redis_client as global_redis
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
                
                # Получаем данные из Redis перед обработкой
                redis = global_redis
                payment_data = await redis.get(f"payment:{user_id}", as_json=True)
                
                amount = int(Decimal(str(response.amount.value)))
                success = await _process_successful_payment(payment, user_id, session, amount, payment_data)
                
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
    amount: int,
    payment_data: Optional[dict] = None
) -> bool:
    """Обработка успешного платежа (поддержка покупки и продления)"""
    
    bot = get_bot_instance()
    redis = global_redis
    
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
        
        # 4. Определяем тип платежа (покупка или продление)
        payment_type = payment_data.get("type", "buy") if payment_data else "buy"
        
        subscription_repo = SubscriptionRepository(session)
        
        if payment_type == "extend":
            # ========== ПРОДЛЕНИЕ ПОДПИСКИ ==========
            subscription_uuid = payment_data.get("subscription_uuid")
            inbound_id = payment_data.get("inbound_id", host.inbound_id)
            
            ic(f"Processing EXTEND for subscription {subscription_uuid}")
            
            # Получаем существующую подписку
            existing_sub = await subscription_repo.get_by_sub_id(subscription_uuid)
            
            if not existing_sub:
                ic(f"Subscription {subscription_uuid} not found")
                return False
            
            # Обновляем клиента через API
            def update_client_sync():
                client = XUIClient(host)
                success, _ = client.extend_client_subscription(
                    inbound_id=inbound_id,
                    client_uuid=subscription_uuid,
                    additional_days=rate.days
                )
                client.close()
                return success
            
            success = await asyncio.to_thread(update_client_sync)
            
            if not success:
                ic(f"Failed to extend subscription {subscription_uuid}")
                await bot.send_message(
                    user_id,
                    "❌ <b>Ошибка продления подписки</b>\n\nНе удалось продлить подписку на сервере.\n"
                    "Свяжитесь с поддержкой: @hor1zon_support",
                    parse_mode="HTML"
                )
                return False
            
            # Обновляем подписку в БД
            await subscription_repo.update(
                existing_sub.sub_id,
                rate_id=rate.id,
                status=SubscriptionStatus.ACTIVE
            )
            
            # Отмечаем платеж как оплаченный
            payment.mark_as_paid()
            await session.commit()
            
            # Отправляем сообщение об успешном продлении
            success_text = (
                f"✅ <b>Подписка успешно продлена!</b>\n\n"
                f"📋 <b>Тариф:</b> {rate.name}\n"
                f"📅 <b>Дней добавлено:</b> {rate.days}\n"
                f"💰 <b>Оплачено:</b> {amount}₽\n\n"
                f"🖥 <b>Сервер:</b> {host.name}\n\n"
                f"🔗 <b>Ваша VLESS ссылка (осталась без изменений):</b>\n"
                f"<code>{existing_sub.vless_url}</code>"
            )
            
            await bot.send_message(user_id, success_text, parse_mode="HTML")
            
            ic(f"Subscription extended for user {user_id}")
            return True
        
        else:
            # ========== НОВАЯ ПОДПИСКА (ПОКУПКА) ==========
            ic(f"Processing NEW subscription for user {user_id}")
            
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
            
            client_id = client_data.get("id")
            
            def get_inbound_sync():
                client = XUIClient(host)
                inbound = client.get_inbound_by_id(host.inbound_id)
                client.close()
                return inbound
            
            inbound = await asyncio.to_thread(get_inbound_sync)
            
            if inbound:
                hostname = host.api_url.split('//')[-1].split(':')[0]
                port = inbound.get("port", 443)
                
                stream_settings = inbound.get("streamSettings", {})
                if isinstance(stream_settings, str):
                    try:
                        stream_settings = json.loads(stream_settings)
                    except:
                        stream_settings = {}
                
                reality = stream_settings.get("realitySettings", {})
                reality_settings = reality.get("settings", {})
                public_key = reality_settings.get("publicKey", "")
                server_name = reality.get("serverNames", ["www.amazon.com"])[0] if reality.get("serverNames") else "www.amazon.com"
                short_ids = reality.get("shortIds", [""])
                short_id = short_ids[0] if short_ids else ""
                
                vless_url = (
                    f"vless://{client_id}@{hostname}:{port}"
                    f"?type=tcp&encryption=none&security=reality"
                    f"&pbk={public_key}&fp=chrome&sni={server_name}"
                )
                
                if short_id:
                    vless_url += f"&sid={short_id}"
                
                vless_url += f"&flow=xtls-rprx-vision#HorizonVPN"
            else:
                vless_url = client_data.get("vless_url", "")
            
            if not vless_url:
                ic("No vless_url generated")
                return False
            
            await subscription_repo.create(
                sub_id=client_id,
                user_id=user.user_id,
                host_id=host.host_id,
                rate_id=rate.id,
                vless_url=vless_url,
                status=SubscriptionStatus.ACTIVE
            )
            
            payment.mark_as_paid()
            host.current_clients += 1
            await session.commit()
            
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
            
            ic(f"New subscription created for user {user_id}")
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
    finally:
        # Удаляем временные данные из Redis
        await redis.delete(f"payment:{user_id}")