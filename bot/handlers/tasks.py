"""Хендлеры блока Задачи и напоминания."""
import re
from datetime import date, datetime

import pytz
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, BufferedInputFile

from bot.database.base import AsyncSessionLocal
from bot.database import crud
from bot.database.models import TaskPriority, RecurrenceType, Task
from bot.keyboards.tasks_kb import (
    tasks_menu_kb, priority_kb, recurring_kb, recurrence_type_kb,
    tasks_list_kb, done_tasks_list_kb, task_actions_kb, skip_kb, reminder_skip_kb,
    PRIORITY_EMOJI, PRIORITY_LABEL
)
from bot.states.all_states import TaskStates
from bot.utils.charts import generate_tasks_card

router = Router()

RECURRENCE_LABEL = {
    RecurrenceType.daily: "Ежедневно",
    RecurrenceType.weekly: "Еженедельно",
    RecurrenceType.monthly: "Ежемесячно",
}


def local_to_utc_time(time_str: str, tz_str: str) -> datetime.time:
    """Конвертирует локальное время 'HH:MM' в UTC time."""
    local_tz = pytz.timezone(tz_str)
    t = datetime.strptime(time_str, "%H:%M").time()
    dt = datetime.combine(date.today(), t)
    local_dt = local_tz.localize(dt)
    utc_dt = local_dt.astimezone(pytz.UTC)
    return utc_dt.time()


def utc_to_local_time(utc_time: datetime.time, tz_str: str) -> str:
    """Конвертирует UTC time в строку 'HH:MM' локального времени."""
    if not utc_time:
        return ""
    local_tz = pytz.timezone(tz_str)
    dt = datetime.combine(date.today(), utc_time)
    utc_dt = pytz.UTC.localize(dt)
    local_dt = utc_dt.astimezone(local_tz)
    return local_dt.strftime("%H:%M")


async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def _send_tasks_menu(callback: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
        
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )
        
        tasks_active = await crud.get_tasks(session, user.id, show_done=False)
        tasks_all_today = await crud.get_tasks(session, user.id, show_done=None)
        
        # Задачи на сегодня (due_date == today или None, не выполненные)
        today = crud.user_today(user)
        active_today = [t for t in tasks_active if t.due_date is None or t.due_date == today]
        done_today = [t for t in tasks_all_today if t.is_done and t.updated_at.date() == today]
        
        total_today = len(active_today) + len(done_today)
        done_count = len(done_today)
        
        # Для карточки передаём (title, priority, is_done)
        display_tasks = []
        for t in active_today:
            display_tasks.append((t.title, t.priority.value, False))
        for t in done_today:
            display_tasks.append((t.title, t.priority.value, True))
            
    img = generate_tasks_card(
        tasks_today=display_tasks,
        done_count=done_count,
        total_count=total_today
    )
    photo = BufferedInputFile(img.read(), filename="tasks.png")
    
    caption = (
        "✅ <b>Задачи и планирование</b>\n\n"
        "Следи за делами, настраивай напоминания."
    )

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=photo, caption=caption,
        parse_mode="HTML", reply_markup=tasks_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:tasks")
async def cb_tasks_menu(callback: CallbackQuery, state: FSMContext):
    await _send_tasks_menu(callback, state)


@router.callback_query(F.data == "tasks:menu")
async def cb_back_tasks(callback: CallbackQuery, state: FSMContext):
    await _send_tasks_menu(callback, state)


# ─── Создание задачи ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "tasks:new")
async def cb_new_task(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TaskStates.enter_title)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "📝 <b>Новая задача</b>\n\nКак она называется? <i>(коротко)</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(TaskStates.enter_title)
async def process_title(message: Message, state: FSMContext):
    await _safe_delete(message)
    title = message.text.strip()
    if not title:
        return
    await state.update_data(title=title)
    await state.set_state(TaskStates.enter_description)
    await message.answer(
        "📄 Добавь описание или нажми «Пропустить»:",
        reply_markup=skip_kb("desc")
    )


@router.callback_query(TaskStates.enter_description, F.data == "tasks:skip:desc")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await state.set_state(TaskStates.choose_priority)
    await callback.message.edit_text(
        "Выберите приоритет задачи:",
        reply_markup=priority_kb()
    )
    await callback.answer()


@router.message(TaskStates.enter_description)
async def process_description(message: Message, state: FSMContext):
    await _safe_delete(message)
    await state.update_data(description=message.text.strip())
    await state.set_state(TaskStates.choose_priority)
    await message.answer(
        "Оцени важность задачи:",
        reply_markup=priority_kb()
    )


@router.callback_query(TaskStates.choose_priority, F.data.startswith("tasks:prio:"))
async def cb_priority(callback: CallbackQuery, state: FSMContext):
    prio_str = callback.data.split(":")[2]
    await state.update_data(priority=prio_str)
    await state.set_state(TaskStates.enter_due_date)
    await callback.message.edit_text(
        "📅 До какого числа нужно сделать?\n"
        "<i>Введи дату в формате ДД.ММ.ГГГГ, или нажми «Пропустить»</i>",
        parse_mode="HTML",
        reply_markup=skip_kb("date")
    )
    await callback.answer()


@router.callback_query(TaskStates.enter_due_date, F.data == "tasks:skip:date")
async def skip_due_date(callback: CallbackQuery, state: FSMContext):
    await state.update_data(due_date=None)
    await state.set_state(TaskStates.choose_recurring)
    await callback.message.edit_text(
        "Это регулярная задача? (повторяется)",
        reply_markup=recurring_kb()
    )
    await callback.answer()


@router.message(TaskStates.enter_due_date)
async def process_due_date(message: Message, state: FSMContext):
    await _safe_delete(message)
    text = message.text.strip()
    try:
        d = datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Непонятный формат 🤔 Напиши как в примере: <code>31.12.2025</code>", parse_mode="HTML")
        return
    await state.update_data(due_date=d.isoformat())
    await state.set_state(TaskStates.choose_recurring)
    await message.answer(
        "Это регулярная задача? (повторяется)",
        reply_markup=recurring_kb()
    )


@router.callback_query(TaskStates.choose_recurring, F.data.startswith("tasks:rec:"))
async def cb_recurring(callback: CallbackQuery, state: FSMContext):
    ans = callback.data.split(":")[2]
    if ans == "yes":
        await state.update_data(is_recurring=True)
        await state.set_state(TaskStates.choose_recurrence_type)
        await callback.message.edit_text(
            "Как часто она повторяется?",
            reply_markup=recurrence_type_kb()
        )
    else:
        await state.update_data(is_recurring=False, recurrence=None)
        await state.set_state(TaskStates.enter_remind_time)
        await callback.message.edit_text(
            "⏰ Настроить напоминание?\n"
            "<i>Введи время в формате ЧЧ:ММ (например <code>09:30</code>), или пропусти.</i>",
            parse_mode="HTML",
            reply_markup=reminder_skip_kb()
        )
    await callback.answer()


@router.callback_query(TaskStates.choose_recurrence_type, F.data.startswith("tasks:rectype:"))
async def cb_recurrence_type(callback: CallbackQuery, state: FSMContext):
    rtype = callback.data.split(":")[2]
    await state.update_data(recurrence=rtype)
    await state.set_state(TaskStates.enter_remind_time)
    await callback.message.edit_text(
        "⏰ Настроить напоминание?\n"
        "<i>Введи время в формате ЧЧ:ММ (например <code>09:30</code>), или пропусти.</i>",
        parse_mode="HTML",
        reply_markup=reminder_skip_kb()
    )
    await callback.answer()


@router.callback_query(TaskStates.enter_remind_time, F.data == "tasks:skip:reminder")
async def skip_reminder(callback: CallbackQuery, state: FSMContext):
    await state.update_data(remind_at=None)
    await _save_task(callback.message, callback.from_user, state)
    await callback.answer()


@router.message(TaskStates.enter_remind_time)
async def process_reminder(message: Message, state: FSMContext):
    await _safe_delete(message)
    text = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", text):
        await message.answer("Ой, формат должен быть ЧЧ:ММ, например <code>08:15</code>", parse_mode="HTML")
        return
        
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await message.answer("Такого времени не бывает 🤔 Проверь формат (ЧЧ:ММ).", parse_mode="HTML")
        return

    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, message.from_user.id,
            message.from_user.username, message.from_user.first_name
        )
        tz_str = user.timezone

    utc_time = local_to_utc_time(text, tz_str)
    await state.update_data(remind_at=utc_time.isoformat())
    await _save_task(message, message.from_user, state)


async def _save_task(message: Message, from_user, state: FSMContext):
    data = await state.get_data()
    due_date = date.fromisoformat(data["due_date"]) if data.get("due_date") else None
    remind_at = datetime.time.fromisoformat(data["remind_at"]) if data.get("remind_at") else None
    recurrence = RecurrenceType(data["recurrence"]) if data.get("recurrence") else None

    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, from_user.id, from_user.username, from_user.first_name
        )
        await crud.add_task(
            session,
            user_id=user.id,
            title=data["title"],
            description=data.get("description"),
            priority=TaskPriority(data["priority"]),
            due_date=due_date,
            is_recurring=data["is_recurring"],
            recurrence=recurrence,
            remind_at=remind_at
        )

    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
        
    await message.answer(f"Задача «{data['title']}» успешно создана! 🎉")
    class DummyCallback:
        def __init__(self, msg, usr):
            self.message = msg
            self.from_user = usr
        async def answer(self): pass
    await _send_tasks_menu(DummyCallback(message, from_user), None)


# ─── Списки задач ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "tasks:list")
async def cb_tasks_list(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        tasks = await crud.get_tasks(session, callback.from_user.id, show_done=False)

    try:
        await callback.message.delete()
    except Exception:
        pass
        
    if not tasks:
        await callback.message.answer(
            "📋 Активных задач нет! Всё выполнено 🎉",
            reply_markup=tasks_menu_kb()
        )
    else:
        await callback.message.answer(
            f"📋 <b>Активные задачи ({len(tasks)})</b>\n\n"
            f"✅ — отметить как выполненную\n"
            f"📋 — посмотреть детали",
            parse_mode="HTML",
            reply_markup=tasks_list_kb(tasks)
        )
    await callback.answer()


@router.callback_query(F.data == "tasks:done")
async def cb_done_tasks(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        tasks = await crud.get_tasks(session, callback.from_user.id, show_done=True)

    done = [t for t in tasks if t.is_done]
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    if not done:
        await callback.message.answer(
            "📭 Выполненных задач пока нет.",
            reply_markup=tasks_menu_kb()
        )
    else:
        await callback.message.answer(
            f"✅ <b>Выполненные задачи ({len(done)})</b>:",
            parse_mode="HTML",
            reply_markup=done_tasks_list_kb(done)
        )
    await callback.answer()


# ─── Быстрое выполнение ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tasks:quick_done:"))
async def cb_quick_done(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        marked = await crud.mark_task_done(session, task_id, callback.from_user.id)
        if marked:
            await callback.answer("✅ Отлично! Задача выполнена.")
        else:
            await callback.answer("Ошибка: задача не найдена.", show_alert=True)
            
    # Обновляем список
    await cb_tasks_list(callback)


# ─── Детальный просмотр и действия ────────────────────────────────────────────

@router.callback_query(F.data.startswith("tasks:view:"))
async def cb_view_task(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[2])

    async with AsyncSessionLocal() as session:
        task = await session.get(Task, task_id)
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )

    if not task or task.user_id != callback.from_user.id:
        await callback.answer("❌ Задача не найдена", show_alert=True)
        return

    emoji = PRIORITY_EMOJI.get(task.priority, "⚪")
    due_str = task.due_date.strftime("%d.%m.%Y") if task.due_date else "без срока"
    rec_str = f"\n🔁 Повторение: {RECURRENCE_LABEL.get(task.recurrence, '')}" if task.is_recurring else ""
    desc_str = f"\n📄 {task.description}" if task.description else ""
    
    remind_str = ""
    if task.remind_at:
        local_t = utc_to_local_time(task.remind_at, user.timezone)
        remind_str = f"\n⏰ Напоминание: в {local_t}"

    status = "✅ Выполнена" if task.is_done else "В процессе"

    text = (
        f"{emoji} <b>{task.title}</b>\n\n"
        f"Статус: {status}\n"
        f"📅 Срок: {due_str}{remind_str}{rec_str}{desc_str}"
    )

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=task_actions_kb(task)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:done:"))
async def cb_done_task(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        await crud.mark_task_done(session, task_id, callback.from_user.id)
    await callback.answer("✅ Отлично! Задача выполнена.")
    await cb_tasks_list(callback)


@router.callback_query(F.data.startswith("tasks:del:"))
async def cb_del_task(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        await crud.delete_task(session, task_id, callback.from_user.id)
    await callback.answer("Задача удалена 🗑")
    await cb_tasks_list(callback)


@router.callback_query(F.data == "tasks:clear_done")
async def cb_clear_done_tasks(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        count = await crud.delete_completed_tasks(session, callback.from_user.id)
    await callback.answer(f"✅ Очищено задач: {count}", show_alert=True)
    await cb_done_tasks(callback)
