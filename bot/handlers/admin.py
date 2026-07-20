from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func

from bot.database.base import AsyncSessionLocal
from bot.database.models import User, Transaction, Account, Task

router = Router()

# Hardcoded admin username (without @)
ADMIN_USERNAME = "uffnv"

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not message.from_user.username or message.from_user.username.lower() != ADMIN_USERNAME.lower():
        await message.answer("У вас нет прав доступа к этой команде.")
        return
        
    async with AsyncSessionLocal() as session:
        # Get stats
        users_count = await session.scalar(select(func.count(User.id)))
        accounts_count = await session.scalar(select(func.count(Account.id)))
        tx_count = await session.scalar(select(func.count(Transaction.id)))
        tasks_count = await session.scalar(select(func.count(Task.id)))
        
        # Calculate total money in system
        total_balance = await session.scalar(select(func.sum(Account.balance))) or 0
        
    text = (
        "👑 <b>Панель Администратора</b>\n\n"
        "📊 <b>Статистика бота:</b>\n"
        f"Пользователей: <b>{users_count}</b>\n"
        f"Заведено счетов: <b>{accounts_count}</b>\n"
        f"Всего денег на счетах: <b>{total_balance:,.0f} ₽</b>\n"
        f"Транзакций в базе: <b>{tx_count}</b>\n"
        f"Задач в базе: <b>{tasks_count}</b>\n"
    )
    
    await message.answer(text, parse_mode="HTML")
