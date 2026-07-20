from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import FinanceCategory, TransactionType, Account


def finance_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Quick expense buttons
    builder.row(
        InlineKeyboardButton(text="➖ 500₽", callback_data="finance:quick_exp:500"),
        InlineKeyboardButton(text="➖ 1000₽", callback_data="finance:quick_exp:1000"),
        InlineKeyboardButton(text="➖ 5000₽", callback_data="finance:quick_exp:5000"),
    )
    # Manual add
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести расход", callback_data="finance:add:expense"),
        InlineKeyboardButton(text="➕ Ввести доход", callback_data="finance:add:income"),
    )
    # Stats & History
    builder.row(
        InlineKeyboardButton(text="📊 Баланс подробно", callback_data="finance:balance"),
        InlineKeyboardButton(text="📋 История", callback_data="finance:history")
    )
    # Management
    builder.row(
        InlineKeyboardButton(text="🗂 Категории", callback_data="finance:categories"),
        InlineKeyboardButton(text="🎯 Бюджеты", callback_data="finance:budgets")
    )
    builder.row(InlineKeyboardButton(text="🏦 Мои счета", callback_data="finance:accounts"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def category_select_kb(categories: list[FinanceCategory], page: int = 0) -> InlineKeyboardMarkup:
    # Оставляем старую логику или упрощаем, сделаю без страниц для простоты (лимит 14 на экран)
    builder = InlineKeyboardBuilder()
    
    # 2 кнопки в ряд
    cats = categories[:14]
    for i in range(0, len(cats), 2):
        row = []
        for cat in cats[i:i+2]:
            row.append(InlineKeyboardButton(
                text=f"{cat.icon} {cat.name}",
                callback_data=f"finance:selcat:{cat.id}"
            ))
        builder.row(*row)
    
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="finance:menu"))
    return builder.as_markup()


def categories_manage_kb(categories: list[FinanceCategory]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories[:14]:
        builder.row(InlineKeyboardButton(
            text=f"🗑 {cat.icon} {cat.name}",
            callback_data=f"finance:delcat:{cat.id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Новая категория", callback_data="finance:newcat"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="finance:menu"))
    return builder.as_markup()


def confirm_delete_cat_kb(cat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"finance:confirmdelcat:{cat_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="finance:categories")
    )
    return builder.as_markup()


def budget_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Неделя", callback_data="finance:budget_period:week"),
        InlineKeyboardButton(text="🗓 Месяц", callback_data="finance:budget_period:month")
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="finance:menu"))
    return builder.as_markup()


def history_kb(has_more: bool, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"finance:hist_page:{page-1}"))
    if has_more:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"finance:hist_page:{page+1}"))
    
    if nav_row:
        builder.row(*nav_row)
    
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="finance:menu"))
    return builder.as_markup()


def budgets_list_kb(budgets: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in budgets:
        builder.row(InlineKeyboardButton(
            text=f"🗑 {b.category.icon} {b.category.name} ({b.limit_amount}₽)",
            callback_data=f"finance:delbudget:{b.id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Добавить бюджет", callback_data="finance:addbudget"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="finance:menu"))
    return builder.as_markup()


def yes_no_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Да", callback_data="yes"),
        InlineKeyboardButton(text="Нет", callback_data="no")
    )
    return builder.as_markup()


def interest_period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Каждый день", callback_data="period:daily"),
        InlineKeyboardButton(text="Каждую неделю", callback_data="period:weekly"),
        InlineKeyboardButton(text="Каждый месяц", callback_data="period:monthly")
    )
    return builder.as_markup()


def account_select_kb(accounts: list[Account], callback_prefix: str = "finance:selacc") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for acc in accounts:
        builder.row(InlineKeyboardButton(
            text=f"{acc.name} ({acc.balance:,.0f} ₽)",
            callback_data=f"{callback_prefix}:{acc.id}"
        ))
    return builder.as_markup()


def accounts_manage_kb(accounts: list[Account]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for acc in accounts:
        builder.row(InlineKeyboardButton(
            text=f"🗑 {acc.name} ({acc.balance:,.0f} ₽)",
            callback_data=f"finance:delacc:{acc.id}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Добавить счет", callback_data="finance:newacc"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="finance:menu"))
    return builder.as_markup()
