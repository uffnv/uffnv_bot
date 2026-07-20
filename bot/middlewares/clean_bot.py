from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import SendMessage, SendPhoto, TelegramMethod
from aiogram.types import Message

class CleanBotMessagesMiddleware(BaseRequestMiddleware):
    def __init__(self):
        self.last_bot_msg = {}

    async def __call__(self, make_request, bot, method: TelegramMethod):
        if isinstance(method, (SendMessage, SendPhoto)):
            # Execute the request first to get the new message
            result = await make_request(bot, method)
            
            if isinstance(result, Message):
                chat_id = result.chat.id
                msg_id = result.message_id
                
                old_msg_id = self.last_bot_msg.get(chat_id)
                if old_msg_id and old_msg_id != msg_id:
                    try:
                        await bot.delete_message(chat_id, old_msg_id)
                    except Exception:
                        pass
                self.last_bot_msg[chat_id] = msg_id
                
            return result
            
        return await make_request(bot, method)
