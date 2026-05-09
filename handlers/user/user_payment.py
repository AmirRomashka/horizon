# handlers/user/user_payment.py
import asyncio
from aiogram import F, Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from icecream import ic
from sqlalchemy.ext.asyncio import AsyncSession

from States.user_states import UserStates
from database.orm_query import UserRepository, RateRepository, PaymentRepository
from database.enumerate.payment_enum import PaymentStatus, PaymentSystem
from database.enumerate.rate_enum import RateStatus
from tools import send_clean_message
from keybords.inline import get_inlineMix_btns
from Yookassa import create_payment, check_payment_status, cancel_payment_by_id

UserPaymentRouter = Router(name="user_payment_router")


@UserPaymentRouter.callback_query(F.data.startswith("buy_rate_"))
async def buy_rate(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession
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
        
        # Сохраняем payment_id в состояние
        await state.update_data(payment_id=payment.payment_id, yoo_payment_id=yoo_payment.id)
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
        
        # Запускаем фоновую проверку статуса платежа
        asyncio.create_task(check_payment_status(
            payment_id=yoo_payment.id,
            user_id=call.from_user.id,
            session=session
        ))
        
    except Exception as e:
        ic(f"Payment creation error: {e}")
        await call.answer("❌ Ошибка при создании платежа. Попробуйте позже", show_alert=True)


@UserPaymentRouter.callback_query(F.data == "cancel_payment", StateFilter(UserStates.payment_pending))
async def cancel_payment_handler(
    call: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """Отмена платежа при нажатии на кнопку"""
    data = await state.get_data()
    payment_id = data.get("payment_id")
    yoo_payment_id = data.get("yoo_payment_id")
    
    if payment_id:
        # Отменяем платёж в БД
        payment_repo = PaymentRepository(session)
        payment = await payment_repo.get(payment_id)
        if payment and payment.is_pending():
            payment.mark_as_failed()
            await session.commit()
    
    if yoo_payment_id:
        # Отменяем платёж в YooKassa
        await cancel_payment_by_id(yoo_payment_id)
    
    await state.clear()
    
    await call.message.edit_text(
        "❌ <b>Платёж отменён</b>\n\n"
        "Вы можете выбрать другой тариф в профиле.",
        parse_mode="HTML"
    )
    
    # Отправляем кнопку возврата в профиль
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
    session: AsyncSession
):
    """При возврате в профиль отменяем платёж"""
    data = await state.get_data()
    payment_id = data.get("payment_id")
    yoo_payment_id = data.get("yoo_payment_id")
    
    if payment_id:
        payment_repo = PaymentRepository(session)
        payment = await payment_repo.get(payment_id)
        if payment and payment.is_pending():
            payment.mark_as_failed()
            await session.commit()
    
    if yoo_payment_id:
        await cancel_payment_by_id(yoo_payment_id)
    
    await state.clear()
    
    # Переходим в профиль через существующий обработчик
    from handlers.user.user_profile import user_profile
    await user_profile(call, state, session)