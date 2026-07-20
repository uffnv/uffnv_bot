from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import Task, TaskPriority


PRIORITY_EMOJI = {
    TaskPriority.high: "🔴",
    TaskPriority.medium: "🟡",
    TaskPriority.low: "🟢",
}

PRIORITY_LABEL = {
    TaskPriority.high: "Высокий",
    TaskPriority.medium: "Средний",
    TaskPriority.low: "Низкий",
}


def tasks_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Новая задача", callback_data="tasks:new"))
    builder.row(
        InlineKeyboardButton(text="📋 Активные", callback_data="tasks:list"),
        InlineKeyboardButton(text="✅ Выполненные", callback_data="tasks:done"),
    )
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def tasks_list_kb(tasks: list[Task]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for task in tasks[:15]:
        emoji = PRIORITY_EMOJI.get(task.priority, "⚪")
        # Кнопка быстрой отметки "выполнено" и кнопка "подробнее"
        title = task.title[:30] + ("..." if len(task.title) > 30 else "")
        builder.row(
            InlineKeyboardButton(text=f"✅ {emoji} {title}", callback_data=f"tasks:quick_done:{task.id}"),
            InlineKeyboardButton(text="📋", callback_data=f"tasks:view:{task.id}")
        )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="tasks:menu"))
    return builder.as_markup()


def done_tasks_list_kb(tasks: list[Task]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for task in tasks[:15]:
        builder.row(InlineKeyboardButton(
            text=f"✓ {task.title[:35]}",
            callback_data=f"tasks:view:{task.id}"
        ))
    if tasks:
        builder.row(InlineKeyboardButton(text="🗑 Очистить завершенные", callback_data="tasks:clear_done"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="tasks:menu"))
    return builder.as_markup()


def task_actions_kb(task: Task) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not task.is_done:
        builder.row(InlineKeyboardButton(text="✅ Выполнено", callback_data=f"tasks:done:{task.id}"))
    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"tasks:del:{task.id}"))
    builder.row(InlineKeyboardButton(text="⬅️ К списку", callback_data="tasks:list"))
    return builder.as_markup()


def priority_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔴 Высокий", callback_data="tasks:prio:high"))
    builder.row(InlineKeyboardButton(text="🟡 Средний", callback_data="tasks:prio:medium"))
    builder.row(InlineKeyboardButton(text="🟢 Низкий", callback_data="tasks:prio:low"))
    return builder.as_markup()


def recurring_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Да", callback_data="tasks:rec:yes"),
                InlineKeyboardButton(text="Нет", callback_data="tasks:rec:no"))
    return builder.as_markup()


def recurrence_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Ежедневно", callback_data="tasks:rectype:daily"))
    builder.row(InlineKeyboardButton(text="📆 Еженедельно", callback_data="tasks:rectype:weekly"))
    builder.row(InlineKeyboardButton(text="🗓 Ежемесячно", callback_data="tasks:rectype:monthly"))
    return builder.as_markup()


def skip_kb(step: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏩ Пропустить", callback_data=f"tasks:skip:{step}"))
    return builder.as_markup()


def reminder_skip_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏩ Не напоминать", callback_data="tasks:skip:reminder"))
    return builder.as_markup()
