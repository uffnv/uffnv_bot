from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Финансы", callback_data="menu:finance"))
    builder.row(InlineKeyboardButton(text="🥗 Питание и физа", callback_data="menu:fitness"))
    builder.row(InlineKeyboardButton(text="✅ Задачи", callback_data="menu:tasks"))
    builder.row(
        InlineKeyboardButton(text="📥 Импорт", callback_data="excel:import"),
        InlineKeyboardButton(text="📤 Экспорт", callback_data="excel:export")
    )
    builder.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"))
    return builder.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def settings_kb(user) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🕐 Часовой пояс", callback_data="settings:timezone"))
    
    report_status = "✅ Вкл" if getattr(user, 'evening_report_enabled', False) else "❌ Выкл"
    builder.row(InlineKeyboardButton(text=f"🌙 Вечерний отчет: {report_status}", callback_data="settings:toggle_report"))
    if getattr(user, 'evening_report_enabled', False):
        builder.row(InlineKeyboardButton(text=f"⏰ Время отчета: {getattr(user, 'evening_report_time', 'Не задано') or 'Не задано'}", callback_data="settings:time_report"))
        
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()
