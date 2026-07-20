from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Финансы", callback_data="menu:finance"))
    builder.row(InlineKeyboardButton(text="🥗 Питание и физа", callback_data="menu:fitness"))
    builder.row(InlineKeyboardButton(text="✅ Задачи", callback_data="menu:tasks"))
    builder.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"))
    return builder.as_markup()


def back_to_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()


def settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🕐 Часовой пояс", callback_data="settings:timezone"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()
