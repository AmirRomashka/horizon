# services/Yookassa.py
import os
import uuid
import asyncio
import json
from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta

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
        "confirmation": {"type": "redirect", "return_url": "https://t.me/OfficialHorizonBot"},
        "description": f"{rate_name} · {rate_days} days",
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
                
                redis = global_redis
                payment_data = await redis.get(f"payment:{user_id}", as_json=True)
                
                amount = int(Decimal(str(response.amount.value)))
                success = await _process_successful_payment(payment, user_id, session, amount, payment_data)
                
                if success:
                    await bot.send_message(
                        user_id,
                        "<b>Horizon VPN</b>\n\nОплата прошла.\nПодписка активирована.\n\n↓ ссылка ниже",
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
                    "<b>Платёж отменён</b>\n\nВыберите другой тариф в профиле.",
                    parse_mode="HTML"
                )
                return False
                
        except Exception as e:
            ic(f"Payment check error (attempt {attempt}): {str(e)}")
        
        await asyncio.sleep(check_interval)
    
    await bot.send_message(
        user_id,
        "<b>Не удалось подтвердить платёж</b>\n\nЕсли деньги списаны, они вернутся в течение нескольких дней.\n\nПоддержка: @Ilya_Nester0v",
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
        # ======================================================================
        # 1. ПОЛУЧАЕМ ТАРИФ
        # ======================================================================
        rate_repo = RateRepository(session)
        rate = await rate_repo.get(payment.rate_id)
        if not rate:
            ic(f"Rate {payment.rate_id} not found")
            return False
        
        # ======================================================================
        # 2. ПОЛУЧАЕМ ХОСТ
        # ======================================================================
        host_repo = HostRepository(session)
        host = await host_repo.get_host_for_new_client()
        if not host:
            ic("No available hosts found")
            await bot.send_message(
                user_id,
                "<b>Ошибка активации</b>\n\nНет доступных серверов. Платёж зарегистрирован.\n\nПоддержка: @Ilya_Nester0v",
                parse_mode="HTML"
            )
            return False
        
        # ======================================================================
        # 3. ПОЛУЧАЕМ ПОЛЬЗОВАТЕЛЯ
        # ======================================================================
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(user_id)
        if not user:
            ic(f"User {user_id} not found")
            return False
        
        # ======================================================================
        # 4. ОПРЕДЕЛЯЕМ ТИП ПЛАТЕЖА
        # ======================================================================
        payment_type = payment_data.get("type", "buy") if payment_data else "buy"
        subscription_repo = SubscriptionRepository(session)
        
        # ======================================================================
        # 5. ПРОДЛЕНИЕ ПОДПИСКИ
        # ======================================================================
        if payment_type == "extend":
            subscription_uuid = payment_data.get("subscription_uuid")
            inbound_id = payment_data.get("inbound_id", host.inbound_id)
            
            ic(f"Processing EXTEND for subscription {subscription_uuid}")
            
            # Получаем существующую подписку
            existing_sub = await subscription_repo.get_by_sub_id(subscription_uuid)
            
            if not existing_sub:
                ic(f"Subscription {subscription_uuid} not found")
                return False
            
            # Получаем текущую дату окончания из БД
            current_expiry = existing_sub.expires_at
            now = datetime.now()
            
            # Рассчитываем новую дату окончания
            if current_expiry and current_expiry > now:
                # Подписка активна → добавляем дни к существующей дате
                new_expiry_date = current_expiry + timedelta(days=rate.days)
                ic(f"Active subscription: current expiry={current_expiry}, adding {rate.days} days → new expiry={new_expiry_date}")
            else:
                # Подписка истекла или нет даты → от текущего момента
                new_expiry_date = now + timedelta(days=rate.days)
                ic(f"Expired or no subscription: starting from now, new expiry={new_expiry_date}")
            
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
                    "<b>Ошибка продления</b>\n\nПоддержка: @Ilya_Nester0v",
                    parse_mode="HTML"
                )
                return False
            
            # Обновляем подписку в БД
            await subscription_repo.update(
                existing_sub.sub_id,
                rate_id=rate.id,
                status=SubscriptionStatus.ACTIVE,
                expires_at=new_expiry_date
            )
            
            payment.mark_as_paid()
            await session.commit()
            
            # Формируем сообщение об успешном продлении
            new_date_str = new_expiry_date.strftime('%d.%m.%Y')
            
            success_text = (
                f"<b>Подписка продлена</b>\n\n"
                f"{rate.name} · +{rate.days} дн.\n"
                f"{amount}₽\n\n"
                f"Сервер: {host.name}\n"
                f"Действует до: {new_date_str}\n\n"
                f"<code>{existing_sub.vless_url}</code>"
            )
            
            await bot.send_message(user_id, success_text, parse_mode="HTML")
            
            ic(f"Subscription extended for user {user_id}, new expiry: {new_expiry_date}")
            return True
        
        # ======================================================================
        # 6. НОВАЯ ПОДПИСКА (ПОКУПКА)
        # ======================================================================
        else:
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
                    "<b>Ошибка активации</b>\n\nНе удалось создать клиента.\n\nПоддержка: @Ilya_Nester0v",
                    parse_mode="HTML"
                )
                return False
            
            client_id = client_data.get("id")
            
            # Получаем информацию для VLESS ссылки
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
            
            # Устанавливаем дату истечения
            expires_at = datetime.now() + timedelta(days=rate.days)
            
            await subscription_repo.create(
                sub_id=client_id,
                user_id=user.user_id,
                host_id=host.host_id,
                rate_id=rate.id,
                vless_url=vless_url,
                status=SubscriptionStatus.ACTIVE,
                expires_at=expires_at
            )
            
            payment.mark_as_paid()
            host.current_clients += 1
            await session.commit()
            
            vless_text = (
                f"<b>Horizon VPN</b>\n\n"
                f"{rate.name} · {rate.days} дн.\n"
                f"{amount}₽\n\n"
                f"Сервер: {host.name}\n"
                f"Действует до: {expires_at.strftime('%d.%m.%Y')}\n\n"
                f"<code>{vless_url}</code>\n\n"
                f"Нажмите для копирования"
            )
            
            await bot.send_message(user_id, vless_text, parse_mode="HTML")
            
            ic(f"New subscription created for user {user_id}, expires at: {expires_at}")
            return True
        
    except Exception as e:
        ic(f"Error processing successful payment: {e}")
        await session.rollback()
        
        await bot.send_message(
            user_id,
            f"<b>Ошибка активации</b>\n\nПлатёж подтверждён, но произошла ошибка.\n\nПоддержка: @Ilya_Nester0v",
            parse_mode="HTML"
        )
        return False
    finally:
        await redis.delete(f"payment:{user_id}")