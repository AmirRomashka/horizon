# tools.py

import re
from functools import wraps
from typing import Callable, Dict, List, Optional, Tuple, Union, TypeVar
from icecream import ic
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto
from aiogram.enums.parse_mode import ParseMode
from aiogram.exceptions import TelegramBadRequest

from config import last_message_dict
from bot_instance import get_bot_instance
from keybords.inline import get_callback_btns


# =============================================================================
# УПРАВЛЕНИЕ СООБЩЕНИЯМИ
# =============================================================================

async def message_delete(user_id: int, last_message: dict = last_message_dict):
    """Удаляет все сообщения пользователя из истории."""
    bot = get_bot_instance()
    for msg_id in last_message.get(user_id, []):
        try:
            await bot.delete_message(chat_id=user_id, message_id=msg_id)
        except Exception as e:
            ic(e)
    last_message_dict[user_id] = []


async def send_clean_message(
    target: Union[Message, CallbackQuery],
    text: str,
    buttons: Optional[Dict[str, str]] = None,
    sizes: Optional[List[int]] = None,
    parse_mode: Optional[str] = ParseMode.HTML,
    photo: Optional[Union[str, FSInputFile]] = None,
    edit: bool = False
) -> Message:
    """Отправляет сообщение с управлением историей."""
    user_id = target.from_user.id
    
    reply_markup = None
    if buttons:
        sizes_tuple = tuple(sizes) if sizes else (1,)
        reply_markup = get_callback_btns(btns=buttons, sizes=sizes_tuple)
    
    try:
        if edit and isinstance(target, CallbackQuery):
            if photo:
                media = InputMediaPhoto(media=photo, caption=text, parse_mode=parse_mode)
                msg = await target.message.edit_media(media=media, reply_markup=reply_markup)
            else:
                msg = await target.message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
            await target.answer()
        else:
            if isinstance(target, CallbackQuery):
                msg = await target.message.answer_photo(photo, caption=text, reply_markup=reply_markup, parse_mode=parse_mode) if photo \
                    else await target.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
                await target.answer()
            else:
                msg = await target.answer_photo(photo, caption=text, reply_markup=reply_markup, parse_mode=parse_mode) if photo \
                    else await target.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        await message_delete(user_id)
        
        if user_id not in last_message_dict:
            last_message_dict[user_id] = []
        last_message_dict[user_id].append(msg.message_id)
        
        return msg
        
    except TelegramBadRequest as e:
        ic(f"Telegram error: {e}")
        msg = await (target.message.answer if isinstance(target, CallbackQuery) else target.answer)(
            text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )
        last_message_dict.setdefault(user_id, []).append(msg.message_id)
        return msg


# =============================================================================
# ПАРСИНГ CALLBACK
# =============================================================================

class CallbackParser:
    """Универсальный парсер callback данных."""
    
    def __init__(self, call: CallbackQuery):
        self.data = call.data
        self._numbers = None
    
    @property
    def numbers(self) -> List[int]:
        """Кэшированный список всех чисел в callback."""
        if self._numbers is None:
            self._numbers = [int(p) for p in self.data.split("_") if p.isdigit()]
        return self._numbers
    
    def get_id(self, prefix: Optional[str] = None, position: Optional[int] = None) -> Optional[int]:
        """
        Получает ID из callback.
        
        - prefix: ищет первое число после префикса
        - position: берет число по индексу из списка всех чисел
        - если ничего не указано: возвращает первое число
        """
        if prefix:
            if not self.data.startswith(prefix):
                return None
            match = re.search(r'\d+', self.data[len(prefix):])
            return int(match.group()) if match else None
        
        if position is not None:
            return self.numbers[position] if position < len(self.numbers) else None
        
        return self.numbers[0] if self.numbers else None
    
    def get_ids(self, count: int) -> List[Optional[int]]:
        """Возвращает первые count ID."""
        return [self.numbers[i] if i < len(self.numbers) else None for i in range(count)]
    
    def matches(self, prefix: str) -> bool:
        """Проверяет начало callback."""
        return self.data.startswith(prefix)
    
    def validate(self, prefix: str, count: int = 1) -> Tuple[Union[int, List[int], None], Optional[str]]:
        """Проверяет callback и возвращает ID или ошибку."""
        if not self.matches(prefix):
            return None, f"❌ Неверный формат: ожидался {prefix}"
        
        if len(self.numbers) < count:
            return None, f"❌ Недостаточно данных. Ожидается {count} ID, получено {len(self.numbers)}"
        
        return self.numbers[0] if count == 1 else self.numbers[:count], None


def parse_callback(
    call: CallbackQuery,
    expected_prefix: Optional[str] = None, 
    expected_count: int = 1                 
) -> Tuple[Union[int, List[int], None], Optional[str]]:
    """Быстрый парсинг callback с валидацией."""
    parser = CallbackParser(call)
    
    if expected_prefix:
        return parser.validate(expected_prefix, expected_count)
    
    numbers = parser.numbers
    if len(numbers) < expected_count:
        return None, f"❌ Недостаточно данных. Ожидается {expected_count} ID, получено {len(numbers)}"
    
    return numbers[0] if expected_count == 1 else numbers[:expected_count], None
def safe_id(call: CallbackQuery, prefix: Optional[str] = None) -> Optional[int]:
    """Безопасно получает первый ID (без ошибок)."""
    return CallbackParser(call).get_id(prefix=prefix)


# =============================================================================
# ДЕКОРАТОР ДЛЯ CALLBACK
# =============================================================================

T = TypeVar('T')

def validate_callback(
    prefix: Optional[str] = None,
    count: int = 1,
    alert: bool = True
):
    """
    Декоратор для автоматической валидации callback.
    
    Пример:
        @validate_callback("admin_dish_")
        async def handler(call, state, session, id):
            ...
        
        @validate_callback("dish_in_cart_", count=2)
        async def handler(call, session, ids):
            dish_id, item_id = ids
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(call: CallbackQuery, *args, **kwargs):
            result, error = parse_callback(call, prefix, count)
            
            if error:
                if alert:
                    await call.answer(error, show_alert=True)
                ic(f"Callback error: {error} | data: {call.data}")
                return
            
            if count == 1:
                return await func(call, *args, **kwargs, id=result)
            return await func(call, *args, **kwargs, ids=result)
        
        return wrapper
    return decorator

# tools.py (добавить в конец файла)

# =============================================================================
# УВЕДОМЛЕНИЯ АДМИНИСТРАТОРОВ
# =============================================================================

async def notify_admins(
    bot,
    text: str,
    admin_ids: List[int],
    buttons: Optional[Dict[str, str]] = None,
    sizes: Optional[List[int]] = None,
    parse_mode: str = ParseMode.HTML
) -> None:
    """
    Отправляет уведомление всем администраторам.
    Использует send_clean_message для автоматической очистки старых сообщений.
    
    Args:
        bot: экземпляр бота
        text: текст уведомления
        admin_ids: список ID администраторов
        buttons: кнопки (опционально)
        sizes: размеры кнопок (опционально)
        parse_mode: режим парсинга
    """
    for admin_id in admin_ids:
        try:
            # Создаём фейковый объект Message для send_clean_message
            # (чтобы использовать существующую логику очистки)
            class FakeMessage:
                def __init__(self, user_id, bot):
                    self.from_user = type('obj', (object,), {'id': user_id})
                    self.bot = bot
                
                async def answer(self, *args, **kwargs):
                    return await bot.send_message(chat_id=self.from_user.id, *args, **kwargs)
                
                async def answer_photo(self, *args, **kwargs):
                    return await bot.send_photo(chat_id=self.from_user.id, *args, **kwargs)
            
            fake_message = FakeMessage(admin_id, bot)
            
            await send_clean_message(
                target=fake_message,
                text=text,
                buttons=buttons,
                sizes=sizes,
                parse_mode=parse_mode
            )
            
        except Exception as e:
            ic(f"Error notifying admin {admin_id}: {e}")

# tools.py (добавить)

