"""Общие хендлеры: /start, главное меню, настройки."""
import pytz
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from bot.database.base import AsyncSessionLocal
from bot.database.crud import (
    get_or_create_user, ensure_default_categories,
    update_user_timezone
)
from bot.keyboards.main_menu import main_menu_kb, settings_kb
from bot.states.all_states import TaskStates
from bot.utils.charts import generate_main_card

router = Router()


async def _safe_delete(message: Message):
    """Тихо удаляет сообщение — игнорирует ошибки."""
    try:
        await message.delete()
    except Exception:
        pass


async def send_main_menu(target: Message | CallbackQuery, first_name: str, state: FSMContext = None):
    """Отправляет главное меню с картинкой."""
    if state:
        await state.clear()

    try:
        img = generate_main_card(first_name)
        photo = BufferedInputFile(img.read(), filename="menu.png")
        caption = (
            f"Привет, <b>{first_name}</b>! 👋\n\n"
            "Я помогу тебе держать под контролем финансы, питание и дела.\n"
            "Что открываем?"
        )

        if isinstance(target, CallbackQuery):
            # Удаляем старое сообщение и шлём новое с картинкой
            try:
                await target.message.delete()
            except Exception:
                pass
            await target.message.answer_photo(photo=photo, caption=caption,
                                              parse_mode="HTML", reply_markup=main_menu_kb())
            await target.answer()
        else:
            await target.answer_photo(photo=photo, caption=caption,
                                      parse_mode="HTML", reply_markup=main_menu_kb())
    except Exception as e:
        if isinstance(target, CallbackQuery):
            await target.message.answer(f"❌ Критическая ошибка генерации меню: {str(e)}")
            await target.answer()
        else:
            await target.answer(f"❌ Критическая ошибка генерации меню: {str(e)}")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, clear_user_message: callable):
    try:
        await state.clear()
        await clear_user_message()
        async with AsyncSessionLocal() as session:
            user = await get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
            )
            await ensure_default_categories(session, user.id)

        name = message.from_user.first_name or message.from_user.username or "друг"
        await send_main_menu(message, name)
    except Exception as e:
        await message.answer(f"❌ Ошибка при запуске: {str(e)}")


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, clear_user_message: callable):
    try:
        await state.clear()
        await clear_user_message()
        name = message.from_user.first_name or "друг"
        await send_main_menu(message, name)
    except Exception as e:
        await message.answer(f"❌ Ошибка меню: {str(e)}")


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext, clear_user_message: callable):
    await state.clear()
    await clear_user_message()
    name = callback.from_user.first_name or "друг"
    await send_main_menu(callback, name, state)


@router.callback_query(F.data == "menu:settings")
async def cb_settings(callback: CallbackQuery, state: FSMContext, clear_user_message: callable):
    await clear_user_message()
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    async with AsyncSessionLocal() as session:
        from bot.database.models import User
        user = await session.get(User, callback.from_user.id)
        
    await callback.message.answer(
        "⚙️ <b>Настройки и профиль</b>\n\n"
        "Здесь можно настроить часовой пояс и вечерние отчеты.",
        parse_mode="HTML",
        reply_markup=settings_kb(user)
    )
    await callback.answer()


@router.callback_query(F.data == "settings:toggle_report")
async def cb_toggle_report(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        from bot.database.models import User
        user = await session.get(User, callback.from_user.id)
        if hasattr(user, 'evening_report_enabled'):
            user.evening_report_enabled = not user.evening_report_enabled
            await session.commit()
            
    await cb_settings(callback, None, lambda: None)


@router.callback_query(F.data == "settings:time_report")
async def cb_time_report(callback: CallbackQuery, state: FSMContext):
    await state.set_state("enter_evening_time")
    await callback.message.edit_text(
        "⏰ <b>Время отчета</b>\n\nВведи время в формате ЧЧ:ММ (например, 21:00)",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.state == "enter_evening_time")
async def process_evening_time(message: Message, state: FSMContext, clear_user_message: callable):
    await _safe_delete(message)
    time_str = message.text.strip()
    from datetime import datetime
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Нужно ЧЧ:ММ (например, 21:00)")
        return
        
    async with AsyncSessionLocal() as session:
        from bot.database.models import User
        user = await session.get(User, message.from_user.id)
        user.evening_report_time = time_str
        await session.commit()
        
    await state.clear()
    await clear_user_message()
    await message.answer("✅ Время сохранено!")
    
    # Рекурсивно возвращаем в настройки
    # Для этого проще вызвать главное меню или обновить сообщение
    from bot.keyboards.main_menu import main_menu_kb
    name = message.from_user.first_name or "друг"
    await send_main_menu(message, name)



@router.callback_query(F.data == "settings:timezone")
async def cb_set_timezone(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TaskStates.enter_timezone)
    await callback.message.edit_text(
        "🕐 <b>Часовой пояс</b>\n\n"
        "Напиши свой часовой пояс в формате IANA, например:\n"
        "• <code>Asia/Krasnoyarsk</code> — UTC+7\n"
        "• <code>Europe/Moscow</code> — UTC+3\n"
        "• <code>Asia/Yekaterinburg</code> — UTC+5\n\n"
        "<a href='https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'>Полный список →</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()


@router.message(TaskStates.enter_timezone)
async def process_timezone(message: Message, state: FSMContext, clear_user_message: callable):
    await _safe_delete(message)
    tz_str = message.text.strip()
    try:
        pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
        await message.answer(
            f"Хм, не знаю такого часового пояса 🤔\n"
            f"Попробуй ещё раз — например, <code>Asia/Krasnoyarsk</code>",
            parse_mode="HTML"
        )
        return

    async with AsyncSessionLocal() as session:
        await update_user_timezone(session, message.from_user.id, tz_str)

    await state.clear()
    await clear_user_message()
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"✅ Готово! Часовой пояс <code>{tz_str}</code> установлен.",
        parse_mode="HTML"
    )
    await send_main_menu(message, name)
