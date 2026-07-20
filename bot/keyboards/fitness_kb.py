from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import FoodProduct, FoodLog


def fitness_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🍽 Добавить приём пищи", callback_data="fitness:addmeal"))
    builder.row(InlineKeyboardButton(text="📊 Итог за сегодня", callback_data="fitness:today"))
    builder.row(
        InlineKeyboardButton(text="⚖️ Записать вес", callback_data="fitness:addweight"),
        InlineKeyboardButton(text="📈 График веса", callback_data="fitness:weightlog"),
    )
    builder.row(InlineKeyboardButton(text="📋 Мои продукты", callback_data="fitness:products"))
    builder.row(
        InlineKeyboardButton(text="🎯 Мои цели", callback_data="fitness:goals"),
        InlineKeyboardButton(text="🏋️ Мой план", callback_data="fitness:myplan"),
    )
    builder.row(InlineKeyboardButton(text="🔄 Сбросить день", callback_data="fitness:cleartoday"))
    builder.row(InlineKeyboardButton(text="🔥 Трекер привычек", callback_data="fitness:habits"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def meal_source_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Из базы продуктов", callback_data="fitness:meal:fromdb"))
    builder.row(InlineKeyboardButton(text="✏️ Ручной ввод", callback_data="fitness:meal:manual"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


def products_list_kb(products: list[FoodProduct], prefix: str = "fitness:selproduct") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products[:15]:
        builder.row(InlineKeyboardButton(
            text=f"{p.name} ({p.calories} кк/100г)",
            callback_data=f"{prefix}:{p.id}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


def manage_products_kb(products: list[FoodProduct]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for p in products[:12]:
        builder.row(InlineKeyboardButton(
            text=f"🗑 {p.name}",
            callback_data=f"fitness:delprod:{p.id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Добавить продукт", callback_data="fitness:addproduct"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


def food_log_kb(logs: list[FoodLog]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for log in logs:
        builder.row(InlineKeyboardButton(
            text=f"🗑 {log.product_name} ({log.calories} кк)",
            callback_data=f"fitness:dellog:{log.id}"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


def goals_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⚖️ Целевой вес", callback_data="fitness:goal:weight"))
    builder.row(InlineKeyboardButton(text="🔥 Дневная калорийность", callback_data="fitness:goal:calories"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


# ─── Клавиатуры физического профиля ──────────────────────────────────────────

def sex_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👨 Мужской", callback_data="profile:sex:male"),
        InlineKeyboardButton(text="👩 Женский", callback_data="profile:sex:female"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="fitness:menu"))
    return builder.as_markup()


def activity_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🪑 Сидячий (офис, мало движения)", callback_data="profile:act:sedentary"))
    builder.row(InlineKeyboardButton(text="🚶 Лёгкая (1-3 тренировки в неделю)", callback_data="profile:act:light"))
    builder.row(InlineKeyboardButton(text="🏃 Средняя (3-5 тренировок в неделю)", callback_data="profile:act:moderate"))
    builder.row(InlineKeyboardButton(text="💪 Высокая (6-7 тренировок в неделю)", callback_data="profile:act:active"))
    builder.row(InlineKeyboardButton(text="🔥 Очень высокая (2x в день / физраб.)", callback_data="profile:act:very_active"))
    return builder.as_markup()


def plan_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔥 Активное похудение (-20% калорий)", callback_data="profile:plan:cut_hard"))
    builder.row(InlineKeyboardButton(text="🌿 Мягкое похудение (-10% калорий)", callback_data="profile:plan:cut_soft"))
    builder.row(InlineKeyboardButton(text="⚖️ Поддержание веса (норма)", callback_data="profile:plan:maintain"))
    builder.row(InlineKeyboardButton(text="💪 Набор массы (+15% калорий)", callback_data="profile:plan:bulk"))
    return builder.as_markup()


def plan_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Сохранить и применить", callback_data="profile:confirm"),
        InlineKeyboardButton(text="🔄 Заново", callback_data="fitness:setup_profile"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


def my_plan_kb(has_profile: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_profile:
        builder.row(InlineKeyboardButton(text="🔄 Изменить план", callback_data="profile:change_plan"))
        builder.row(InlineKeyboardButton(text="📝 Обновить профиль", callback_data="fitness:setup_profile"))
    else:
        builder.row(InlineKeyboardButton(text="🚀 Настроить профиль", callback_data="fitness:setup_profile"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


# ─── Habits ───────────────────────────────────────────────────────────────────

def habits_menu_kb(habits) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for h in habits:
        builder.row(InlineKeyboardButton(text=f"{h.name} (🔥 {h.streak})", callback_data=f"habit:info:{h.id}"))
    builder.row(InlineKeyboardButton(text="➕ Новая привычка", callback_data="habit:add"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:menu"))
    return builder.as_markup()


def habit_info_kb(habit_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗑 Удалить привычку", callback_data=f"habit:del:{habit_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="fitness:habits"))
    return builder.as_markup()

