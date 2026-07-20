import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

class CleanChatMiddleware(BaseMiddleware):
    """
    Мидлварь для реализации Single-Message Architecture (Clean Chat).
    Отслеживает последнее сообщение пользователя и удаляет предыдущее.
    Предоставляет в хендлеры функцию clear_user_message() для зачистки при выходе в меню.
    """
    def __init__(self):
        self.last_user_msg = {}

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = event.from_user.id
        
        # Если пришло обычное текстовое/медиа сообщение от пользователя
        if isinstance(event, Message):
            old_msg_id = self.last_user_msg.get(user_id)
            if old_msg_id:
                try:
                    await event.bot.delete_message(event.chat.id, old_msg_id)
                except Exception:
                    pass
            
            # Сохраняем текущее
            self.last_user_msg[user_id] = event.message_id
            chat_id = event.chat.id
            
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id
            
        # Функция для хендлеров, чтобы очистить сообщение пользователя
        async def clear_user_message():
            msg_id = self.last_user_msg.get(user_id)
            if msg_id:
                try:
                    await event.bot.delete_message(chat_id, msg_id)
                except Exception:
                    pass
                self.last_user_msg.pop(user_id, None)
                
        data['clear_user_message'] = clear_user_message
        
        return await handler(event, data)
