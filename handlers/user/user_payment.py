# handlers/user/user_payment.py
import asyncio
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from States.user_states import UserStates
from database.orm_query import UserRepository, RateRepository, PaymentRepository, SubscriptionRepository, HostRepository
from database.enumerate.payment_enum import PaymentStatus, PaymentSystem
from database.enumerate.rate_enum import RateStatus
from database.enumerate.subscription_enum import SubscriptionStatus
from database.redis_client import RedisClient
from tools import send_clean_message
from keybords.inline import get_inlineMix_btns
from Yookassa import create_payment, check_payment_status, cancel_payment_by_id
from services.xui_client import XUIClient

UserPaymentRouter = Router(name="user_payment_router")


@UserPaymentRouter.callback_query(F.data.startswith("buy_rate_"))
async def buy_rate(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    redis: RedisClient
):
    """
    Покупка тарифа — сразу создаём платёж без лишних подтверждений
    """
    await state.clear()
    
    rate_id = int(call.data.split("_")[-1])
    
    # Получаем тариф
    rate_repo = RateRepository(session)
    rate = await rate_repo.get(rate_id)
    
    if not rate:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    
    if rate.status != RateStatus.ACTIVE:
        await call.answer("❌ Этот тариф временно недоступен", show_alert=True)
        return
    
    # Получаем пользователя
    user_repo = UserRepository(session)
    user = await user_repo.get_by_tg_id(call.from_user.id)
    
    if not user:
        user = await user_repo.create(user_id=call.from_user.id)
        await session.commit()
    
    try:
        # Создаём платеж в YooKassa
        yoo_payment = await asyncio.to_thread(
            create_payment,
            int(rate.price),
            call.from_user.id,
            rate.name,
            rate.days
        )
        
        # Создаём платеж в БД
        payment_repo = PaymentRepository(session)
        payment = await payment_repo.create(
            user_id=user.user_id,
            rate_id=rate.id,
            amount=rate.price,
            payment_system=PaymentSystem.YOOKASSA,
            status=PaymentStatus.PENDING,
            external_id=yoo_payment.id,
            confirmation_url=yoo_payment.confirmation.confirmation_url
        )
        await session.commit()
        
        # Сохраняем данные в Redis
        await redis.set(
            f"payment:{call.from_user.id}",
            {
                "payment_id": payment.payment_id,
                "yoo_payment_id": yoo_payment.id,
                "rate_id": rate.id,
                "amount": rate.price,
                "type": "buy"
            },
            expire=3600
        )
        
        await state.set_state(UserStates.payment_pending)
        
        # Отправляем сообщение с кнопкой оплаты
        text = (
            f"💳 <b>Платёж создан!</b>\n\n"
            f"📋 <b>Тариф:</b> {rate.name}\n"
            f"💰 <b>Сумма:</b> {rate.price}₽\n"
            f"📅 <b>Дней:</b> {rate.days}\n\n"
            f"👇 Нажмите на кнопку для перехода к оплате\n\n"
            f"⚠️ <i>Не закрывайте это сообщение до завершения оплаты</i>"
        )
        
        btns = {
            "💳 Оплатить": yoo_payment.confirmation.confirmation_url,
            "❌ Отменить платёж": "cancel_payment"
        }
        
        reply_markup = get_inlineMix_btns(btns=btns, sizes=(1,))
        
        await call.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        await call.answer()
        
        asyncio.create_task(check_payment_status(
            payment_id=yoo_payment.id,
            user_id=call.from_user.id,
            session=session
        ))
        
    except Exception as e:
        ic(f"Payment creation error: {e}")
        await call.answer("❌ Ошибка при создании платежа. Попробуйте позже", show_alert=True)


@UserPaymentRouter.callback_query(F.data.startswith("extend_rate_"))
async def extend_rate(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    redis: RedisClient
):
    """
    Продление подписки — создаём платёж для существующего клиента
    """
    await state.clear()
    
    rate_id = int(call.data.split("_")[-1])
    
    # Получаем тариф
    rate_repo = RateRepository(session)
    rate = await rate_repo.get(rate_id)
    
    if not rate:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    
    if rate.status != RateStatus.ACTIVE:
        await call.answer("❌ Этот тариф временно недоступен", show_alert=True)
        return
    
    # Получаем пользователя
    user_repo = UserRepository(session)
    user = await user_repo.get_by_tg_id(call.from_user.id)
    
    if not user:
        user = await user_repo.create(user_id=call.from_user.id)
        await session.commit()
    
    # Получаем активную подписку
    subscription_repo = SubscriptionRepository(session)
    active_sub = await subscription_repo.get_active_subscription(user.user_id)
    
    if not active_sub:
        await call.answer("❌ У вас нет активной подписки для продления", show_alert=True)
        return
    
    # Получаем хост через host_id (исправление ошибки)
    host_repo = HostRepository(session)
    host = await host_repo.get(active_sub.host_id)
    
    try:
        # Создаём платеж в YooKassa
        yoo_payment = await asyncio.to_thread(
            create_payment,
            int(rate.price),
            call.from_user.id,
            rate.name,
            rate.days
        )
        
        # Создаём платеж в БД (с пометкой, что это продление)
        payment_repo = PaymentRepository(session)
        payment = await payment_repo.create(
            user_id=user.user_id,
            rate_id=rate.id,
            amount=rate.price,
            payment_system=PaymentSystem.YOOKASSA,
            status=PaymentStatus.PENDING,
            external_id=yoo_payment.id,
            confirmation_url=yoo_payment.confirmation.confirmation_url
        )
        await session.commit()
        
        # Сохраняем данные в Redis (с пометкой о продлении)
        await redis.set(
            f"payment:{call.from_user.id}",
            {
                "payment_id": payment.payment_id,
                "yoo_payment_id": yoo_payment.id,
                "rate_id": rate.id,
                "amount": rate.price,
                "type": "extend",
                "subscription_id": active_sub.sub_id,
                "subscription_uuid": active_sub.sub_id,
                "inbound_id": host.inbound_id if host else 1
            },
            expire=3600
        )
        
        await state.set_state(UserStates.payment_pending)
        
        # Отправляем сообщение с кнопкой оплаты
        text = (
            f"💳 <b>Платёж для продления создан!</b>\n\n"
            f"📋 <b>Тариф:</b> {rate.name}\n"
            f"💰 <b>Сумма:</b> {rate.price}₽\n"
            f"📅 <b>Дней:</b> {rate.days}\n\n"
            f"👇 Нажмите на кнопку для перехода к оплате\n\n"
            f"⚠️ <i>После оплаты ваша подписка будет продлена на {rate.days} дней</i>"
        )
        
        btns = {
            "💳 Оплатить продление": yoo_payment.confirmation.confirmation_url,
            "❌ Отменить": "cancel_payment"
        }
        
        reply_markup = get_inlineMix_btns(btns=btns, sizes=(1,))
        
        await call.message.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        await call.answer()
        
        asyncio.create_task(check_payment_status(
            payment_id=yoo_payment.id,
            user_id=call.from_user.id,
            session=session
        ))
        
    except Exception as e:
        ic(f"Payment creation error: {e}")
        await call.answer("❌ Ошибка при создании платежа для продления. Попробуйте позже", show_alert=True)

@UserPaymentRouter.callback_query(F.data == "cancel_payment", StateFilter(UserStates.payment_pending))
async def cancel_payment_handler(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    redis: RedisClient
):
    """Отмена платежа при нажатии на кнопку"""
    user_id = call.from_user.id
    
    payment_data = await redis.get(f"payment:{user_id}", as_json=True)
    
    if payment_data:
        payment_id = payment_data.get("payment_id")
        yoo_payment_id = payment_data.get("yoo_payment_id")
        
        if payment_id:
            payment_repo = PaymentRepository(session)
            payment = await payment_repo.get(payment_id)
            if payment and payment.is_pending():
                payment.mark_as_failed()
                await session.commit()
        
        if yoo_payment_id:
            await cancel_payment_by_id(yoo_payment_id)
        
        await redis.delete(f"payment:{user_id}")
    
    await state.clear()
    
    await call.message.edit_text(
        "❌ <b>Платёж отменён</b>\n\n"
        "Вы можете выбрать другой тариф в профиле.",
        parse_mode="HTML"
    )
    
    btns = {"🔙 Вернуться в профиль": "user_profile"}
    reply_markup = get_inlineMix_btns(btns=btns, sizes=(1,))
    
    await call.message.answer(
        "👤 Перейти в профиль:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    await call.answer("✅ Платёж отменён")


@UserPaymentRouter.callback_query(F.data == "user_profile", StateFilter(UserStates.payment_pending))
async def exit_from_payment(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    redis: RedisClient
):
    """При возврате в профиль отменяем платёж"""
    user_id = call.from_user.id
    
    payment_data = await redis.get(f"payment:{user_id}", as_json=True)
    
    if payment_data:
        payment_id = payment_data.get("payment_id")
        yoo_payment_id = payment_data.get("yoo_payment_id")
        
        if payment_id:
            payment_repo = PaymentRepository(session)
            payment = await payment_repo.get(payment_id)
            if payment and payment.is_pending():
                payment.mark_as_failed()
                await session.commit()
        
        if yoo_payment_id:
            await cancel_payment_by_id(yoo_payment_id)
        
        await redis.delete(f"payment:{user_id}")
    
    await state.clear()
    
    from handlers.user.user_profile import user_profile
    await user_profile(call, state, session, redis)