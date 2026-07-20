"""Хендлеры блока Питание, физподготовка и планы."""
from datetime import date

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, BufferedInputFile

from bot.database.base import AsyncSessionLocal
from bot.database import crud
from bot.database.models import FoodProduct, ActivityLevel, FitnessPlanType
from bot.keyboards.fitness_kb import (
    fitness_menu_kb, meal_source_kb, products_list_kb,
    manage_products_kb, food_log_kb, goals_kb,
    sex_kb, activity_kb, plan_kb, plan_confirm_kb, my_plan_kb,
)
from bot.states.all_states import FitnessStates, FitnessProfileStates
from bot.utils.charts import generate_fitness_card
from bot.utils.fitness_calc import (
    FitnessProfile, ActivityLevel as CalcActivity,
    FitnessPlan, PLAN_LABEL, ACTIVITY_LABEL,
)

router = Router()

ACTIVITY_MAP = {
    "sedentary":   CalcActivity.sedentary,
    "light":       CalcActivity.light,
    "moderate":    CalcActivity.moderate,
    "active":      CalcActivity.active,
    "very_active": CalcActivity.very_active,
}

PLAN_MAP = {
    "cut_hard": FitnessPlan.cut_hard,
    "cut_soft": FitnessPlan.cut_soft,
    "maintain": FitnessPlan.maintain,
    "bulk":     FitnessPlan.bulk,
}


async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def _send_fitness_menu(callback: CallbackQuery, state: FSMContext = None):
    """Отправляет меню питания с картинкой-карточкой."""
    if state:
        await state.clear()

    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )
        today = crud.user_today(user)
        logs = await crud.get_food_log(session, user.id, today)
        summary = crud.calc_food_summary(logs)
        goal = await crud.get_fitness_goal(session, user.id)
        weight_logs = await crud.get_weight_log(session, user.id, days=7)
        phys = await crud.get_physical_profile(session, user.id)

    current_weight = float(weight_logs[-1].weight) if weight_logs else None
    target_weight = float(goal.target_weight) if goal and goal.target_weight else None
    goal_cal = goal.daily_calories if goal else None

    # Если есть физ. профиль — автоматически устанавливаем калории из плана
    if phys and not goal_cal:
        calc = FitnessProfile(
            weight=float(phys.weight), height=phys.height,
            age=phys.age, sex=phys.sex,
            activity=ACTIVITY_MAP[phys.activity.value],
            plan=PLAN_MAP[phys.plan.value],
        )
        goal_cal = calc.target_calories

    img = generate_fitness_card(
        calories=summary["calories"],
        protein=summary["protein"],
        fat=summary["fat"],
        carbs=summary["carbs"],
        goal_calories=goal_cal,
        current_weight=current_weight,
        target_weight=target_weight,
    )
    photo = BufferedInputFile(img.read(), filename="fitness.png")

    plan_str = ""
    if phys:
        plan_str = f"\n🏋️ Твой план: <b>{PLAN_LABEL[PLAN_MAP[phys.plan.value]]}</b>"

    caption = (
        f"🥗 <b>Питание и физподготовка</b>{plan_str}\n\n"
        "Следи за КБЖУ, весом и прогрессом — всё под рукой."
    )

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer_photo(
        photo=photo, caption=caption,
        parse_mode="HTML", reply_markup=fitness_menu_kb()
    )
    await callback.answer()


# ─── Меню ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:fitness")
async def cb_fitness_menu(callback: CallbackQuery, state: FSMContext):
    await _send_fitness_menu(callback, state)


@router.callback_query(F.data == "fitness:menu")
async def cb_back_fitness(callback: CallbackQuery, state: FSMContext):
    await _send_fitness_menu(callback, state)


@router.callback_query(F.data == "fitness:cleartoday")
async def cb_clear_today(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )
        today = crud.user_today(user)
        count = await crud.delete_food_logs_for_date(session, callback.from_user.id, today)
    await callback.answer(f"✅ Данные за сегодня сброшены (удалено {count} записей).", show_alert=True)
    await _send_fitness_menu(callback, None)


# ─── Мой план ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fitness:myplan")
async def cb_my_plan(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        phys = await crud.get_physical_profile(session, callback.from_user.id)

    if not phys:
        text = (
            "🏋️ <b>Мой план питания</b>\n\n"
            "Профиль ещё не настроен.\n\n"
            "Заполни данные о себе — рост, вес, возраст, уровень активности — "
            "и я рассчитаю оптимальную норму КБЖУ по формуле Миффлина-Сан Жеора 🧮"
        )
    else:
        calc = FitnessProfile(
            weight=float(phys.weight), height=phys.height,
            age=phys.age, sex=phys.sex,
            activity=ACTIVITY_MAP[phys.activity.value],
            plan=PLAN_MAP[phys.plan.value],
        )
        text = calc.summary()

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=my_plan_kb(has_profile=phys is not None)
    )
    await callback.answer()


@router.callback_query(F.data == "profile:change_plan")
async def cb_change_plan(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FitnessProfileStates.choose_plan)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "🎯 <b>Выбери новый план</b>\n\n"
        "Каждый план задаёт разный дефицит или профицит калорий:",
        parse_mode="HTML",
        reply_markup=plan_kb()
    )
    await callback.answer()


# ─── Мастер настройки профиля ─────────────────────────────────────────────────

@router.callback_query(F.data == "fitness:setup_profile")
async def cb_setup_profile(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FitnessProfileStates.enter_sex)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "🏋️ <b>Настройка физического профиля</b>\n\n"
        "Шаг 1 из 6 — Выбери пол:",
        parse_mode="HTML",
        reply_markup=sex_kb()
    )
    await callback.answer()


@router.callback_query(FitnessProfileStates.enter_sex, F.data.startswith("profile:sex:"))
async def cb_sex(callback: CallbackQuery, state: FSMContext):
    sex = callback.data.split(":")[2]
    await state.update_data(prof_sex=sex)
    await state.set_state(FitnessProfileStates.enter_age)
    await callback.message.edit_text(
        "🏋️ <b>Настройка профиля</b>\n\n"
        "Шаг 2 из 6 — Сколько тебе лет?\n"
        "<i>Введи число, например: <code>25</code></i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FitnessProfileStates.enter_age)
async def process_age(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        age = int(message.text.strip())
        if not (10 <= age <= 120):
            raise ValueError
    except ValueError:
        await message.answer("Хм, это не похоже на возраст 🤔 Введи число от 10 до 120:")
        return
    await state.update_data(prof_age=age)
    await state.set_state(FitnessProfileStates.enter_height)
    await message.answer(
        "🏋️ <b>Настройка профиля</b>\n\n"
        "Шаг 3 из 6 — Рост в сантиметрах:\n"
        "<i>Например: <code>175</code></i>",
        parse_mode="HTML"
    )


@router.message(FitnessProfileStates.enter_height)
async def process_height(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        height = int(message.text.strip())
        if not (100 <= height <= 250):
            raise ValueError
    except ValueError:
        await message.answer("Что-то не то 🤔 Введи рост в сантиметрах (от 100 до 250):")
        return
    await state.update_data(prof_height=height)
    await state.set_state(FitnessProfileStates.enter_weight_p)
    await message.answer(
        "🏋️ <b>Настройка профиля</b>\n\n"
        "Шаг 4 из 6 — Текущий вес в кг:\n"
        "<i>Например: <code>72.5</code></i>",
        parse_mode="HTML"
    )


@router.message(FitnessProfileStates.enter_weight_p)
async def process_weight_profile(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        weight = float(message.text.replace(",", ".").strip())
        if not (20 <= weight <= 500):
            raise ValueError
    except ValueError:
        await message.answer("Проверь число — вес должен быть от 20 до 500 кг:")
        return
    await state.update_data(prof_weight=weight)
    await state.set_state(FitnessProfileStates.choose_activity)
    await message.answer(
        "🏋️ <b>Настройка профиля</b>\n\n"
        "Шаг 5 из 6 — Уровень физической активности:\n\n"
        "<i>Выбери то, что ближе всего к твоему образу жизни</i>",
        parse_mode="HTML",
        reply_markup=activity_kb()
    )


@router.callback_query(FitnessProfileStates.choose_activity, F.data.startswith("profile:act:"))
async def cb_activity(callback: CallbackQuery, state: FSMContext):
    act_str = callback.data.split(":")[2]
    await state.update_data(prof_activity=act_str)
    await state.set_state(FitnessProfileStates.choose_plan)
    await callback.message.edit_text(
        "🏋️ <b>Настройка профиля</b>\n\n"
        "Шаг 6 из 6 — Выбери цель:\n\n"
        "🔥 <b>Активное похудение</b> — дефицит 20%, быстрый результат\n"
        "🌿 <b>Мягкое похудение</b> — дефицит 10%, без стресса для организма\n"
        "⚖️ <b>Поддержание</b> — точная норма, без изменений веса\n"
        "💪 <b>Набор массы</b> — профицит 15%, рост мышечной массы",
        parse_mode="HTML",
        reply_markup=plan_kb()
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("profile:plan:"),
    FitnessProfileStates.choose_plan
)
async def cb_plan_choice(callback: CallbackQuery, state: FSMContext):
    plan_str = callback.data.split(":")[2]
    await state.update_data(prof_plan=plan_str)
    data = await state.get_data()

    # Предварительный расчёт
    calc = FitnessProfile(
        weight=data["prof_weight"],
        height=data["prof_height"],
        age=data["prof_age"],
        sex=data["prof_sex"],
        activity=ACTIVITY_MAP[data["prof_activity"]],
        plan=PLAN_MAP[plan_str],
    )

    await state.set_state(FitnessProfileStates.confirm_profile)
    await callback.message.edit_text(
        f"👀 <b>Проверь данные перед сохранением</b>\n\n"
        f"{calc.summary()}\n\n"
        f"Всё верно?",
        parse_mode="HTML",
        reply_markup=plan_confirm_kb()
    )
    await callback.answer()


@router.callback_query(FitnessProfileStates.confirm_profile, F.data == "profile:confirm")
async def cb_confirm_profile(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        profile = await crud.set_physical_profile(
            session,
            user_id=callback.from_user.id,
            sex=data["prof_sex"],
            age=data["prof_age"],
            height=data["prof_height"],
            weight=data["prof_weight"],
            activity=ActivityLevel(data["prof_activity"]),
            plan=FitnessPlanType(data["prof_plan"]),
        )
        # Автоматически обновляем цель калорий из плана
        calc = FitnessProfile(
            weight=data["prof_weight"], height=data["prof_height"],
            age=data["prof_age"], sex=data["prof_sex"],
            activity=ACTIVITY_MAP[data["prof_activity"]],
            plan=PLAN_MAP[data["prof_plan"]],
        )
        await crud.set_fitness_goal(
            session,
            user_id=callback.from_user.id,
            target_weight=None,
            daily_calories=calc.target_calories,
        )

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Профиль сохранён!</b>\n\n"
        f"Дневная норма <b>{calc.target_calories} ккал</b> установлена автоматически.\n"
        f"Теперь в разделе «Итог за сегодня» будет видно прогресс по твоему плану 🎯",
        parse_mode="HTML",
        reply_markup=my_plan_kb(has_profile=True)
    )
    await callback.answer()


# Быстрая смена плана без пересчёта всего профиля
@router.callback_query(F.data.startswith("profile:plan:"))
async def cb_quick_plan(callback: CallbackQuery, state: FSMContext):
    plan_str = callback.data.split(":")[2]
    async with AsyncSessionLocal() as session:
        await crud.update_physical_plan(session, callback.from_user.id, FitnessPlanType(plan_str))
        phys = await crud.get_physical_profile(session, callback.from_user.id)
        if phys:
            calc = FitnessProfile(
                weight=float(phys.weight), height=phys.height,
                age=phys.age, sex=phys.sex,
                activity=ACTIVITY_MAP[phys.activity.value],
                plan=PLAN_MAP[plan_str],
            )
            await crud.set_fitness_goal(
                session, callback.from_user.id,
                target_weight=None, daily_calories=calc.target_calories
            )

    plan_label = PLAN_LABEL.get(PLAN_MAP[plan_str], plan_str)
    await callback.answer(f"✅ План изменён: {plan_label}", show_alert=False)
    await _send_fitness_menu(callback, None)


# ─── Добавить приём пищи ──────────────────────────────────────────────────────

@router.callback_query(F.data == "fitness:addmeal")
async def cb_addmeal(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "🍽 <b>Добавить приём пищи</b>\n\nКак хочешь добавить?",
        parse_mode="HTML",
        reply_markup=meal_source_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "fitness:meal:fromdb")
async def cb_meal_from_db(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        products = await crud.get_food_products(session, callback.from_user.id)

    if not products:
        await callback.answer(
            "База пустая — сначала добавь продукты в «Мои продукты» 📋",
            show_alert=True
        )
        return

    await state.set_state(FitnessStates.log_select_product)
    await callback.message.edit_text(
        "📋 <b>Выбери продукт из базы:</b>",
        parse_mode="HTML",
        reply_markup=products_list_kb(products)
    )
    await callback.answer()


@router.callback_query(FitnessStates.log_select_product, F.data.startswith("fitness:selproduct:"))
async def cb_select_product(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split(":")[2])
    await state.update_data(selected_product_id=product_id)
    await state.set_state(FitnessStates.log_enter_grams)
    await callback.message.edit_text(
        "⚖️ Сколько граммов?\n<i>Введи число, например: <code>150</code></i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FitnessStates.log_enter_grams)
async def process_grams(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        grams = float(message.text.replace(",", ".").strip())
        if grams <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Хм, это не похоже на граммы 🤔 Введи число:")
        return

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, message.from_user.id,
            message.from_user.username, message.from_user.first_name
        )
        product = await session.get(FoodProduct, data["selected_product_id"])
        if not product:
            await message.answer("Продукт не найден — попробуй снова")
            await state.clear()
            return

        factor = grams / 100
        await crud.add_food_log(
            session, user_id=user.id,
            product_name=product.name, grams=grams,
            calories=round(product.calories * factor),
            protein=round(float(product.protein) * factor, 1),
            fat=round(float(product.fat) * factor, 1),
            carbs=round(float(product.carbs) * factor, 1),
            log_date=crud.user_today(user)
        )

    factor = grams / 100
    await state.clear()
    await message.answer(
        f"Записал! 💾\n\n"
        f"<b>{product.name}</b> — {grams:.0f}г\n"
        f"🔥 {round(product.calories * factor)} кк · "
        f"Б {round(float(product.protein)*factor,1)}г · "
        f"Ж {round(float(product.fat)*factor,1)}г · "
        f"У {round(float(product.carbs)*factor,1)}г",
        parse_mode="HTML",
        reply_markup=fitness_menu_kb()
    )


# --- Ручной ввод ---

@router.callback_query(F.data == "fitness:meal:manual")
async def cb_meal_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FitnessStates.log_manual_name)
    await callback.message.edit_text(
        "✏️ Как называется блюдо или продукт?\n"
        "<i>Например: Греческий салат</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FitnessStates.log_manual_name)
async def manual_name(message: Message, state: FSMContext):
    await _safe_delete(message)
    await state.update_data(manual_name=message.text.strip())
    await state.set_state(FitnessStates.log_manual_calories)
    await message.answer("🔥 Сколько калорий? <i>(только число)</i>", parse_mode="HTML")


@router.message(FitnessStates.log_manual_calories)
async def manual_calories(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        cal = int(message.text.strip())
        if cal < 0: raise ValueError
    except ValueError:
        await message.answer("Введи целое число, например: <code>350</code>", parse_mode="HTML")
        return
    await state.update_data(manual_calories=cal)
    await state.set_state(FitnessStates.log_manual_protein)
    await message.answer("🥩 Белки в граммах? <i>(введи 0 если не знаешь)</i>", parse_mode="HTML")


@router.message(FitnessStates.log_manual_protein)
async def manual_protein(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        val = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Нужно число, например: <code>12.5</code>", parse_mode="HTML")
        return
    await state.update_data(manual_protein=val)
    await state.set_state(FitnessStates.log_manual_fat)
    await message.answer("🧈 Жиры в граммах? <i>(введи 0 если не знаешь)</i>", parse_mode="HTML")


@router.message(FitnessStates.log_manual_fat)
async def manual_fat(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        val = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Нужно число:", parse_mode="HTML")
        return
    await state.update_data(manual_fat=val)
    await state.set_state(FitnessStates.log_manual_carbs)
    await message.answer("🍞 Углеводы в граммах? <i>(введи 0 если не знаешь)</i>", parse_mode="HTML")


@router.message(FitnessStates.log_manual_carbs)
async def manual_carbs(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        val = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Нужно число:")
        return
    await state.update_data(manual_carbs=val)
    await state.set_state(FitnessStates.log_manual_grams)
    await message.answer(
        "⚖️ Вес порции в граммах?\n"
        "<i>Введи 100 если считал на 100г</i>",
        parse_mode="HTML"
    )


@router.message(FitnessStates.log_manual_grams)
async def manual_grams(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        grams = float(message.text.replace(",", ".").strip())
        if grams <= 0: raise ValueError
    except ValueError:
        await message.answer("Введи корректный вес в граммах:")
        return

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, message.from_user.id,
            message.from_user.username, message.from_user.first_name
        )
        await crud.add_food_log(
            session, user_id=user.id,
            product_name=data["manual_name"], grams=grams,
            calories=data["manual_calories"],
            protein=data["manual_protein"],
            fat=data["manual_fat"],
            carbs=data["manual_carbs"],
            log_date=crud.user_today(user)
        )

    await state.clear()
    await message.answer(
        f"Записал! 💾\n\n"
        f"<b>{data['manual_name']}</b> — {grams:.0f}г\n"
        f"🔥 {data['manual_calories']} кк · "
        f"Б {data['manual_protein']}г · "
        f"Ж {data['manual_fat']}г · "
        f"У {data['manual_carbs']}г",
        parse_mode="HTML",
        reply_markup=fitness_menu_kb()
    )


# ─── Итог за сегодня ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "fitness:today")
async def cb_today(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )
        today = crud.user_today(user)
        logs = await crud.get_food_log(session, user.id, today)
        summary = crud.calc_food_summary(logs)
        goal = await crud.get_fitness_goal(session, user.id)

    if not logs:
        await callback.answer("Сегодня ещё ничего не ел 🤷 Добавь первый приём!", show_alert=True)
        return

    goal_line = ""
    if goal and goal.daily_calories:
        percent = round(summary["calories"] / goal.daily_calories * 100)
        remaining = goal.daily_calories - summary["calories"]
        bar_filled = min(percent // 10, 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        status = "✅" if remaining >= 0 else "⚠️"
        goal_line = (
            f"\n\n<b>Прогресс по цели:</b>\n"
            f"[{bar}] {percent}%\n"
            f"{status} {'Осталось' if remaining >= 0 else 'Перебор'}: "
            f"<b>{abs(remaining)} ккал</b>"
        )

    lines = [f"📊 <b>Питание за {today.strftime('%d.%m.%Y')}</b>\n"]
    for log in logs:
        lines.append(f"• {log.product_name} ({log.grams:.0f}г) — {log.calories} кк")

    lines.append(
        f"\n<b>Итого:</b> 🔥 {summary['calories']} кк\n"
        f"🥩 {summary['protein']}г  🧈 {summary['fat']}г  🍞 {summary['carbs']}г"
        + goal_line
    )

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=food_log_kb(logs)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fitness:dellog:"))
async def cb_delete_food_log(callback: CallbackQuery):
    log_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        deleted = await crud.delete_food_log(session, log_id, callback.from_user.id)

    if not deleted:
        await callback.answer("Что-то пошло не так 🤷", show_alert=True)
        return
    await callback.answer("Удалено 🗑")

    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )
        logs = await crud.get_food_log(session, user.id, crud.user_today(user))

    if logs:
        await callback.message.edit_reply_markup(reply_markup=food_log_kb(logs))
    else:
        await callback.message.edit_text(
            "Записей за сегодня нет — можно начинать заново 🍽",
            reply_markup=fitness_menu_kb()
        )


# ─── Вес ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fitness:addweight")
async def cb_addweight(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FitnessStates.enter_weight)
    await callback.message.edit_caption(
        caption="⚖️ Сколько сегодня весишь? Введи в кг:\n<i>Например: <code>72.5</code></i>",
        parse_mode="HTML"
    ) if hasattr(callback.message, 'caption') and callback.message.caption else \
    await callback.message.edit_text(
        "⚖️ Сколько сегодня весишь? Введи в кг:\n<i>Например: <code>72.5</code></i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FitnessStates.enter_weight)
async def process_weight(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        weight = float(message.text.replace(",", ".").strip())
        if not (20 <= weight <= 500): raise ValueError
    except ValueError:
        await message.answer("Проверь число — это вес в кг, например: <code>72.5</code>", parse_mode="HTML")
        return

    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, message.from_user.id,
            message.from_user.username, message.from_user.first_name
        )
        await crud.add_weight(session, user.id, weight, crud.user_today(user))

    await state.clear()
    await message.answer(
        f"Записал ⚖️ — сегодня <b>{weight} кг</b>",
        parse_mode="HTML",
        reply_markup=fitness_menu_kb()
    )


@router.callback_query(F.data == "fitness:weightlog")
async def cb_weightlog(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        logs = await crud.get_weight_log(session, callback.from_user.id, days=30)
        goal = await crud.get_fitness_goal(session, callback.from_user.id)

    if not logs:
        await callback.answer("Записей веса пока нет — добавь первый!", show_alert=True)
        return

    target = float(goal.target_weight) if goal and goal.target_weight else None
    lines = [f"📈 <b>Динамика веса за 30 дней</b>\n"]

    for log in logs:
        diff_str = ""
        lines.append(f"• {log.date.strftime('%d.%m')} — <b>{float(log.weight):.1f} кг</b>{diff_str}")

    first = float(logs[0].weight)
    last = float(logs[-1].weight)
    diff = last - first
    trend = f"📉 -{abs(diff):.1f}" if diff < 0 else f"📈 +{diff:.1f}"
    lines.append(f"\n{trend} кг за период")
    if target:
        rem = last - target
        lines.append(
            f"🎯 До цели ({target} кг): "
            f"{'ещё ' + str(round(abs(rem), 1)) + ' кг ↓' if rem > 0 else '✅ Цель достигнута!'}"
        )

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=fitness_menu_kb()
    )
    await callback.answer()


# ─── База продуктов ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "fitness:products")
async def cb_products(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        products = await crud.get_food_products(session, callback.from_user.id)

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        f"📋 <b>Мои продукты</b> ({len(products)} шт.)\n"
        "<i>Нажми на продукт чтобы удалить его</i>",
        parse_mode="HTML",
        reply_markup=manage_products_kb(products)
    )
    await callback.answer()


@router.callback_query(F.data == "fitness:addproduct")
async def cb_addproduct(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FitnessStates.product_name)
    await callback.message.edit_text(
        "➕ <b>Новый продукт</b>\n\nКак называется? <i>(как в магазине)</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FitnessStates.product_name)
async def product_name(message: Message, state: FSMContext):
    await _safe_delete(message)
    await state.update_data(prod_name=message.text.strip())
    await state.set_state(FitnessStates.product_calories)
    await message.answer("🔥 Калорийность на 100г <i>(целое число)</i>:", parse_mode="HTML")


@router.message(FitnessStates.product_calories)
async def product_calories(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        val = int(message.text.strip())
        if val < 0: raise ValueError
    except ValueError:
        await message.answer("Нужно целое число, например: <code>250</code>", parse_mode="HTML")
        return
    await state.update_data(prod_cal=val)
    await state.set_state(FitnessStates.product_protein)
    await message.answer("🥩 Белки на 100г <i>(0 если не знаешь)</i>:", parse_mode="HTML")


@router.message(FitnessStates.product_protein)
async def product_protein(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        val = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Нужно число:")
        return
    await state.update_data(prod_prot=val)
    await state.set_state(FitnessStates.product_fat)
    await message.answer("🧈 Жиры на 100г <i>(0 если не знаешь)</i>:", parse_mode="HTML")


@router.message(FitnessStates.product_fat)
async def product_fat(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        val = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Нужно число:")
        return
    await state.update_data(prod_fat=val)
    await state.set_state(FitnessStates.product_carbs)
    await message.answer("🍞 Углеводы на 100г <i>(0 если не знаешь)</i>:", parse_mode="HTML")


@router.message(FitnessStates.product_carbs)
async def product_carbs(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        val = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Нужно число:")
        return

    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        await crud.add_food_product(
            session, message.from_user.id,
            data["prod_name"], data["prod_cal"],
            data["prod_prot"], data["prod_fat"], val
        )

    await state.clear()
    await message.answer(
        f"Добавил! ✅\n\n"
        f"<b>{data['prod_name']}</b>\n"
        f"🔥 {data['prod_cal']} кк · 🥩 {data['prod_prot']}г · 🧈 {data['prod_fat']}г · 🍞 {val}г",
        parse_mode="HTML",
        reply_markup=fitness_menu_kb()
    )


@router.callback_query(F.data.startswith("fitness:delprod:"))
async def cb_delprod(callback: CallbackQuery):
    prod_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        deleted = await crud.delete_food_product(session, prod_id, callback.from_user.id)
        products = await crud.get_food_products(session, callback.from_user.id)

    if deleted:
        await callback.answer("Удалено 🗑")
        await callback.message.edit_reply_markup(reply_markup=manage_products_kb(products))
    else:
        await callback.answer("Не получилось удалить 🤷", show_alert=True)


# ─── Цели ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "fitness:goals")
async def cb_goals(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        goal = await crud.get_fitness_goal(session, callback.from_user.id)

    if goal:
        text = (
            "🎯 <b>Мои цели</b>\n\n"
            f"⚖️ Целевой вес: <b>{float(goal.target_weight):.1f} кг</b>\n"
            f"🔥 Дневная норма: <b>{goal.daily_calories} ккал</b>\n\n"
            "<i>Нажми, чтобы изменить:</i>"
        ) if (goal.target_weight and goal.daily_calories) else (
            "🎯 <b>Мои цели</b>\n\nЧасть целей ещё не задана — давай настроим:"
        )
    else:
        text = "🎯 <b>Мои цели</b>\n\nЦелей пока нет. Задай их:"

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=goals_kb())
    await callback.answer()


@router.callback_query(F.data == "fitness:goal:weight")
async def cb_goal_weight(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FitnessStates.goal_weight)
    await callback.message.edit_text(
        "⚖️ Какой вес хочешь достичь? <i>(кг, например: <code>65</code>)</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FitnessStates.goal_weight)
async def process_goal_weight(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        weight = float(message.text.replace(",", ".").strip())
        if not (20 <= weight <= 500): raise ValueError
    except ValueError:
        await message.answer("Введи корректный вес, например: <code>65</code>", parse_mode="HTML")
        return

    async with AsyncSessionLocal() as session:
        await crud.set_fitness_goal(session, message.from_user.id, target_weight=weight, daily_calories=None)

    await state.clear()
    await message.answer(
        f"Записал! 🎯 Целевой вес — <b>{weight} кг</b>",
        parse_mode="HTML", reply_markup=fitness_menu_kb()
    )


@router.callback_query(F.data == "fitness:goal:calories")
async def cb_goal_calories(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FitnessStates.goal_calories)
    await callback.message.edit_text(
        "🔥 Дневная норма калорий?\n<i>Например: <code>1800</code> — или настрой автоматически через «Мой план» 🏋️</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(FitnessStates.goal_calories)
async def process_goal_calories(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        cal = int(message.text.strip())
        if not (500 <= cal <= 10000): raise ValueError
    except ValueError:
        await message.answer("Введи разумное число от 500 до 10000 ккал:")
        return

    async with AsyncSessionLocal() as session:
        await crud.set_fitness_goal(session, message.from_user.id, target_weight=None, daily_calories=cal)

    await state.clear()
    await message.answer(
        f"Готово! 🔥 Дневная норма — <b>{cal} ккал</b>",
        parse_mode="HTML", reply_markup=fitness_menu_kb()
    )
