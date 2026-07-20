from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.future import select

from bot.database.base import AsyncSessionLocal
from bot.database.models import Habit
from bot.states.all_states import HabitStates
from bot.keyboards.fitness_kb import habits_menu_kb, habit_info_kb
# from bot.scheduler.jobs import setup_habit_jobs  # We'll implement this later

router = Router()

async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data == "fitness:habits")
async def cb_habits_menu(callback: CallbackQuery, state: FSMContext, clear_user_message: callable):
    await clear_user_message()
    await state.clear()
    
    async with AsyncSessionLocal() as session:
        stmt = select(Habit).where(Habit.user_id == callback.from_user.id)
        result = await session.execute(stmt)
        habits = result.scalars().all()
        
    text = "🔥 <b>Трекер привычек</b>\n\nЗдесь ты можешь добавить привычки, которые хочешь соблюдать каждый день. Бот будет напоминать о них в нужное время."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=habits_menu_kb(habits))
    await callback.answer()


@router.callback_query(F.data == "habit:add")
async def cb_add_habit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(HabitStates.enter_name)
    await callback.message.edit_text(
        "📝 <b>Новая привычка</b>\n\nНапиши название привычки (например, <i>Пить 2л воды</i> или <i>Чтение 20 мин</i>):",
        parse_mode="HTML",
        reply_markup=None
    )
    await callback.answer()


@router.message(HabitStates.enter_name)
async def process_habit_name(message: Message, state: FSMContext, clear_user_message: callable):
    await _safe_delete(message)
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(HabitStates.enter_time)
        
    await message.answer(
        f"Привычка: <b>{name}</b>\n\n⏰ <b>В какое время напоминать?</b>\nНапиши время в формате ЧЧ:ММ (например, 21:00)",
        parse_mode="HTML"
    )


@router.message(HabitStates.enter_time)
async def process_habit_time(message: Message, state: FSMContext, clear_user_message: callable):
    await _safe_delete(message)
    time_str = message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Пожалуйста, введи время в формате ЧЧ:ММ (например, 21:00)")
        return
        
    data = await state.get_data()
    name = data['name']
    
    async with AsyncSessionLocal() as session:
        habit = Habit(
            user_id=message.from_user.id,
            name=name,
            remind_at=time_str
        )
        session.add(habit)
        await session.commit()
        await session.refresh(habit)
        
    await state.clear()
    await clear_user_message()
    
    # Возвращаемся в меню
    async with AsyncSessionLocal() as session:
        stmt = select(Habit).where(Habit.user_id == message.from_user.id)
        result = await session.execute(stmt)
        habits = result.scalars().all()
        
    text = f"✅ Привычка <b>{name}</b> сохранена! Напоминание в {time_str}."
    await message.answer(text, parse_mode="HTML", reply_markup=habits_menu_kb(habits))


@router.callback_query(F.data.startswith("habit:info:"))
async def cb_habit_info(callback: CallbackQuery):
    habit_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        habit = await session.get(Habit, habit_id)
        if not habit:
            await callback.answer("Привычка не найдена")
            return
            
    text = (
        f"🔥 <b>{habit.name}</b>\n\n"
        f"⏰ Напоминание: {habit.remind_at}\n"
        f"Текущий стрик: 🔥 {habit.streak} дней подряд"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=habit_info_kb(habit_id))
    await callback.answer()


@router.callback_query(F.data.startswith("habit:del:"))
async def cb_del_habit(callback: CallbackQuery):
    habit_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        habit = await session.get(Habit, habit_id)
        if habit:
            await session.delete(habit)
            await session.commit()
            
    await callback.answer("Привычка удалена!")
    
    # Возврат в меню
    async with AsyncSessionLocal() as session:
        stmt = select(Habit).where(Habit.user_id == callback.from_user.id)
        result = await session.execute(stmt)
        habits = result.scalars().all()
        
    text = "🔥 <b>Трекер привычек</b>\n\nЗдесь ты можешь добавить привычки, которые хочешь соблюдать каждый день."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=habits_menu_kb(habits))


from bot.database.models import HabitLog
from datetime import date

@router.callback_query(F.data.startswith('habit:done:'))
async def cb_habit_done(callback: CallbackQuery):
    habit_id = int(callback.data.split(':')[2])
    today = date.today()
    
    async with AsyncSessionLocal() as session:
        habit = await session.get(Habit, habit_id)
        if not habit:
            await callback.message.delete()
            return
            
        stmt = select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.date == today)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        
        if existing and existing.is_done:
            await callback.answer('Уже отмечено!')
            await callback.message.delete()
            return
            
        log = HabitLog(habit_id=habit.id, date=today, is_done=True)
        session.add(log)
        habit.streak += 1
        await session.commit()
        
    await callback.answer(f'Супер! Стрик: 🔥 {habit.streak}')
    await callback.message.delete()

@router.callback_query(F.data == 'habit:ignore')
async def cb_habit_ignore(callback: CallbackQuery):
    await callback.message.delete()
