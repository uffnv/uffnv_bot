"""Шедулер: утренний дайджест и напоминания о задачах."""
import logging
from datetime import datetime

import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.database.base import AsyncSessionLocal
from bot.database import crud

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def send_morning_digest(bot: Bot):
    """Рассылает утренний дайджест тем, у кого настало время дайджеста."""
    now_utc = datetime.now(pytz.utc)
    current_time = now_utc.strftime("%H:%M")

    async with AsyncSessionLocal() as session:
        users = await crud.get_all_users(session)

    for user in users:
        if user.digest_time != current_time:
            continue

        try:
            async with AsyncSessionLocal() as session:
                user_tz = pytz.timezone(user.timezone)
                user_now = datetime.now(user_tz)
                today = user_now.date()
                tasks = await crud.get_tasks_for_date(session, user.id, today)

            if not tasks:
                text = (
                    f"☀️ <b>Доброе утро!</b>\n\n"
                    f"📋 На сегодня задач нет. Отличный день для новых целей! 💪"
                )
            else:
                from bot.keyboards.tasks_kb import PRIORITY_EMOJI, PRIORITY_LABEL
                lines = [f"☀️ <b>Доброе утро! Твои задачи на {today.strftime('%d.%m.%Y')}:</b>\n"]
                for task in tasks:
                    emoji = PRIORITY_EMOJI.get(task.priority, "⚪")
                    rec = " 🔁" if task.is_recurring else ""
                    lines.append(f"{emoji} {task.title}{rec}")

                lines.append(f"\nВсего задач: <b>{len(tasks)}</b>")
                text = "\n".join(lines)

            await bot.send_message(user.id, text, parse_mode="HTML", disable_notification=False)
        except Exception as e:
            logger.error(f"Ошибка отправки дайджеста пользователю {user.id}: {e}")


async def send_task_reminders(bot: Bot):
    """Проверяет задачи с напоминаниями и отправляет сообщение."""
    now_utc = datetime.now(pytz.utc)
    current_time = now_utc.strftime("%H:%M")

    async with AsyncSessionLocal() as session:
        tasks = await crud.get_tasks_with_reminders(session)

    for task in tasks:
        if task.remind_at != current_time:
            continue
        try:
            from bot.keyboards.tasks_kb import PRIORITY_EMOJI
            emoji = PRIORITY_EMOJI.get(task.priority, "⚪")
            await bot.send_message(
                task.user_id,
                f"🔔 <b>Напоминание о задаче!</b>\n\n"
                f"{emoji} <b>{task.title}</b>\n"
                + (f"📄 {task.description}" if task.description else ""),
                parse_mode="HTML",
                disable_notification=False
            )
        except Exception as e:
            logger.error(f"Ошибка напоминания для задачи {task.id}: {e}")


def setup_scheduler(bot: Bot):
    """Настраивает и запускает шедулер."""
    # Проверяем каждую минуту
    scheduler.add_job(
        send_morning_digest,
        "cron",
        minute="*",
        kwargs={"bot": bot},
        id="morning_digest",
        replace_existing=True
    )
    scheduler.add_job(
        send_task_reminders,
        "cron",
        minute="*",
        kwargs={"bot": bot},
        id="task_reminders",
        replace_existing=True
    )
    scheduler.add_job(
        accrue_interest,
        "cron",
        hour=0, minute=0,
        kwargs={"bot": bot},
        id="accrue_interest",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Шедулер запущен")


async def accrue_interest(bot: Bot):
    from bot.database.models import Account, InterestPeriod, Transaction, TransactionType
    from sqlalchemy import select
    from datetime import date
    async with AsyncSessionLocal() as session:
        accounts = (await session.execute(select(Account).where(Account.is_interest_bearing == True))).scalars().all()
        for acc in accounts:
            today = date.today()
            if acc.last_interest_date == today:
                continue
            should_accrue = False
            if acc.interest_period == InterestPeriod.daily:
                should_accrue = True
            elif acc.interest_period == InterestPeriod.weekly and today.weekday() == 0:
                should_accrue = True
            elif acc.interest_period == InterestPeriod.monthly and today.day == 1:
                should_accrue = True
            
            if should_accrue and acc.interest_rate:
                interest_amount = float(acc.balance) * (float(acc.interest_rate) / 100.0)
                if interest_amount > 0:
                    tx = Transaction(
                        user_id=acc.user_id, account_id=acc.id, amount=interest_amount, type=TransactionType.income,
                        note="Начисление процентов", date=today
                    )
                    acc.balance += interest_amount
                    acc.last_interest_date = today
                    session.add(tx)
                    try:
                        await bot.send_message(acc.user_id, f"💰 Начислены проценты по счету {acc.name}: {interest_amount:,.0f} ₽", disable_notification=False)
                    except Exception:
                        pass
        await session.commit()

