"""Хендлеры блока Финансы."""
from datetime import date, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.base import AsyncSessionLocal
from bot.database import crud
from bot.database.models import TransactionType, BudgetPeriod, FinanceCategory
from bot.states.all_states import FinanceStates, AccountWizard
from bot.utils.charts import generate_finance_card
from bot.database.models import Account, InterestPeriod
from bot.keyboards.finance_kb import (
    finance_menu_kb, category_select_kb, categories_manage_kb, 
    confirm_delete_cat_kb, budget_period_kb, history_kb, budgets_list_kb,
    yes_no_kb, interest_period_kb, account_select_kb, accounts_manage_kb
)

router = Router()


async def _safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def _send_finance_menu(callback: CallbackQuery, state: FSMContext = None):
    """Отправляет меню финансов с картинкой-карточкой."""
    if state:
        await state.clear()

    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )
        
        # Получаем статистику за текущий месяц
        today = crud.user_today(user)
        start_date = today.replace(day=1)
        
        balance = await crud.get_balance(session, user.id, start_date, today)
        inc = balance["income"]
        exp = balance["expense"]
        
        # Топ категорий
        txs = await crud.get_transactions(session, user.id, start_date, today)
        cat_map = {}
        for t in txs:
            if t.type == TransactionType.expense and t.category:
                cat_map[t.category.name] = cat_map.get(t.category.name, 0) + float(t.amount)
                
        sorted_cats = sorted(cat_map.items(), key=lambda x: x[1], reverse=True)
        top_cats = sorted_cats[:3]

    img = generate_finance_card(
        income=float(inc),
        expense=float(exp),
        period_label="Этот месяц",
        top_cats=top_cats
    )
    photo = BufferedInputFile(img.read(), filename="finance.png")

    accounts = await crud.get_accounts(session, user.id)
    if not accounts:
        # Require setup first
        await callback.message.edit_caption(
            caption="У тебя пока нет ни одного финансового счета (банка). Давай добавим первый счет!",
            reply_markup=None
        )
        await state.set_state(AccountWizard.add_name)
        msg = await callback.message.answer("Введи название счета (например, Сбербанк, Наличные):")
        await state.update_data(last_msg_id=msg.message_id)
        return

    acc_text = "\n".join([f"🏦 {a.name}: {a.balance:,.0f} ₽" for a in accounts])
    caption = (
        "💰 <b>Финансы</b>\n\n"
        f"<b>Твои счета:</b>\n{acc_text}\n\n"
        "Контролируй расходы, следи за доходами и укладывайся в бюджет."
    )

    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.message.answer_photo(
        photo=photo, caption=caption,
        parse_mode="HTML", reply_markup=finance_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:finance")
async def cb_finance_menu(callback: CallbackQuery, state: FSMContext, clear_user_message: callable):
    await clear_user_message()
    await _send_finance_menu(callback, state)


@router.callback_query(F.data == "finance:menu")
async def cb_back_finance(callback: CallbackQuery, state: FSMContext, clear_user_message: callable):
    await clear_user_message()
    await _send_finance_menu(callback, state)


# ─── Быстрый расход (quick action) ───────────────────────────────────────────

@router.callback_query(F.data.startswith("finance:quick_exp:"))
async def cb_quick_expense(callback: CallbackQuery, state: FSMContext):
    amount = float(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        user = await crud.get_user(session, callback.from_user.id)
        if not user or not user.main_account_id:
            accounts = await crud.get_accounts(session, callback.from_user.id)
            acc_id = accounts[0].id if accounts else None
        else:
            acc_id = user.main_account_id

    if not acc_id:
        await callback.answer("Сначала добавь счет!", show_alert=True)
        return

    await state.update_data(tx_type=TransactionType.expense.value, amount=amount, account_id=acc_id)
    
    async with AsyncSessionLocal() as session:
        cats = await crud.get_categories(session, callback.from_user.id, TransactionType.expense)
        if not cats:
            await callback.answer("Сначала добавь категорию расходов!", show_alert=True)
            return
        
        await callback.message.edit_caption(
            caption=f"Расход {amount:,.0f} ₽\n\nВыбери категорию:",
            reply_markup=category_select_kb(cats)
        )
    await state.set_state(FinanceStates.choose_category)
    await callback.answer()


# ─── Ручное добавление транзакции ───────────────────────────────────────────

@router.callback_query(F.data.startswith("finance:add:"))
async def cb_add_tx(callback: CallbackQuery, state: FSMContext):
    tx_type = callback.data.split(":")[2]
    await state.update_data(tx_type=tx_type)
    
    async with AsyncSessionLocal() as session:
        accounts = await crud.get_accounts(session, callback.from_user.id)
        if not accounts:
            await callback.answer("Сначала добавь счет!", show_alert=True)
            return
            
        if len(accounts) == 1:
            await state.update_data(account_id=accounts[0].id)
            await _proceed_to_category(callback.message, state, tx_type)
        else:
            await callback.message.edit_caption(
                caption="Выбери счет:",
                reply_markup=account_select_kb(accounts)
            )
    await callback.answer()

@router.callback_query(F.data.startswith("finance:selacc:"))
async def cb_select_account(callback: CallbackQuery, state: FSMContext):
    acc_id = int(callback.data.split(":")[2])
    await state.update_data(account_id=acc_id)
    data = await state.get_data()
    await _proceed_to_category(callback.message, state, data["tx_type"])
    await callback.answer()

async def _proceed_to_category(message: Message, state: FSMContext, tx_type: str):
    async with AsyncSessionLocal() as session:
        cats = await crud.get_categories(session, message.chat.id, TransactionType(tx_type))
        if not cats:
            t_name = "расходов" if tx_type == "expense" else "доходов"
            await message.edit_caption(
                caption=f"У тебя нет категорий {t_name}. Перейди в 'Категории' и добавь.",
                reply_markup=finance_menu_kb()
            )
            return
        
        await message.edit_caption(
            caption="Выбери категорию:",
            reply_markup=category_select_kb(cats)
        )
    await state.set_state(FinanceStates.choose_category)


@router.callback_query(FinanceStates.choose_category, F.data.startswith("finance:selcat:"))
async def cb_choose_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split(":")[2])
    await state.update_data(category_id=category_id)
    
    data = await state.get_data()
    amount = data.get("amount")
    
    if amount is not None:
        # Быстрое добавление (сумма уже есть)
        await _save_transaction(callback.message, callback.from_user, data, state)
        await callback.answer()
    else:
        # Ручной ввод суммы
        await state.set_state(FinanceStates.enter_amount)
        await callback.message.edit_caption(
            caption="💵 А теперь отправь сумму:\n<i>(просто число, например 1500)</i>",
            parse_mode="HTML"
        )
        await callback.answer()


@router.message(FinanceStates.enter_amount)
async def process_amount(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Хм, это не похоже на число 🤔 Попробуй ещё раз, например: <code>1500</code>", parse_mode="HTML")
        return

    data = await state.get_data()
    data["amount"] = amount
    await _save_transaction(message, message.from_user, data, state)


async def _save_transaction(message: Message, from_user, data: dict, state: FSMContext):
    tx_type = TransactionType(data["tx_type"])
    amount = data["amount"]
    cat_id = data.get("category_id")
    acc_id = data.get("account_id")
    note = None

    async with AsyncSessionLocal() as session:
        # Save to db
        await crud.add_transaction(
            session, user_id=from_user.id, account_id=acc_id,
            amount=amount, type_=tx_type,
            category_id=cat_id, note=note, tx_date=date.today()
        )
    
    await state.clear()
    await message.answer(f"✅ Успешно сохранено:\n{amount:,.0f} ₽")
    
    class DummyCallback:
        def __init__(self, msg, usr):
            self.message = msg
            self.from_user = usr
        async def answer(self): pass
    await _send_finance_menu(DummyCallback(message, from_user), None)


# ─── Детальный баланс ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "finance:balance")
async def cb_balance(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, callback.from_user.id,
            callback.from_user.username, callback.from_user.first_name
        )
        today = crud.user_today(user)
        
        # За неделю
        w_start = today - timedelta(days=today.weekday())
        w_bal = await crud.get_balance(session, user.id, w_start, today)
        w_inc = w_bal["income"]
        w_exp = w_bal["expense"]
        
        # За месяц
        m_start = today.replace(day=1)
        m_bal = await crud.get_balance(session, user.id, m_start, today)
        m_inc = m_bal["income"]
        m_exp = m_bal["expense"]

    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(
        f"📊 <b>Детальный баланс</b>\n\n"
        f"<b>Текущая неделя:</b>\n"
        f"💚 Доход: +{w_inc:,.0f} ₽\n"
        f"📉 Расход: -{w_exp:,.0f} ₽\n"
        f"Остаток: <b>{(w_inc - w_exp):,.0f} ₽</b>\n\n"
        f"<b>Текущий месяц:</b>\n"
        f"💚 Доход: +{m_inc:,.0f} ₽\n"
        f"📉 Расход: -{m_exp:,.0f} ₽\n"
        f"Остаток: <b>{(m_inc - m_exp):,.0f} ₽</b>",
        parse_mode="HTML",
        reply_markup=history_kb(txs=[], has_more=False)
    )
    await callback.answer()


# ─── История ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "finance:history")
async def cb_history_first_page(callback: CallbackQuery):
    await _show_history_page(callback, 0)

@router.callback_query(F.data.startswith("finance:hist_page:"))
async def cb_history_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[2])
    await _show_history_page(callback, page)

async def _show_history_page(callback: CallbackQuery, page: int):
    LIMIT = 10
    async with AsyncSessionLocal() as session:
        txs = await crud.get_transactions_history(session, callback.from_user.id, limit=LIMIT + 1, offset=page * LIMIT)
    
    has_more = len(txs) > LIMIT
    display_txs = txs[:LIMIT]

    if not display_txs and page == 0:
        text = "📭 История пуста."
    else:
        lines = [f"📋 <b>История операций</b> (Стр. {page + 1})\n"]
        for t in display_txs:
            sign = "+" if t.type == TransactionType.income else "-"
            cat = t.category.name if t.category else "—"
            icon = t.category.icon if t.category else "💵"
            d_str = t.date.strftime("%d.%m")
            lines.append(f"• {d_str} | {icon} {cat}: <b>{sign}{t.amount:,.0f}₽</b>")
        text = "\n".join(lines)

    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(
        text, parse_mode="HTML",
        reply_markup=history_kb(txs=display_txs, has_more=has_more, page=page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("finance:deltx:"))
async def cb_delete_transaction(callback: CallbackQuery):
    tx_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        success = await crud.delete_transaction(session, tx_id, callback.from_user.id)
    if success:
        await callback.answer("✅ Транзакция удалена!")
        await cb_history_first_page(callback)
    else:
        await callback.answer("❌ Ошибка удаления.", show_alert=True)


@router.callback_query(F.data == "finance:clear_all")
async def cb_clear_all_history(callback: CallbackQuery):
    await callback.message.edit_text(
        "🧨 <b>Внимание!</b> Ты собираешься удалить ВСЕ транзакции. Баланс счетов будет пересчитан.\n\nПродолжить?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💣 ДА, УДАЛИТЬ ВСЁ", callback_data="finance:confirm_clear_all")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="finance:history")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "finance:confirm_clear_all")
async def cb_confirm_clear_all_history(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        # Удаляем транзакции от начала времен до текущего момента
        from_d = date(2000, 1, 1)
        to_d = date(2100, 1, 1)
        count = await crud.delete_transactions_period(session, callback.from_user.id, from_d, to_d)
    await callback.answer(f"✅ Удалено транзакций: {count}", show_alert=True)
    await cb_history_first_page(callback)



# ─── Категории ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "finance:categories")
async def cb_categories(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        cats = await crud.get_categories(session, callback.from_user.id)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(
        "🗂 <b>Управление категориями</b>\nНажми, чтобы удалить.",
        parse_mode="HTML",
        reply_markup=categories_manage_kb(cats)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("finance:delcat:"))
async def cb_delcat(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "Удалить категорию? Все её операции станут «Без категории».",
        reply_markup=confirm_delete_cat_kb(cat_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("finance:confirmdelcat:"))
async def cb_confirm_delcat(callback: CallbackQuery):
    cat_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        await crud.delete_category(session, cat_id, callback.from_user.id)
    await callback.answer("Удалено 🗑")
    await cb_categories(callback)


# Создание категории
@router.callback_query(F.data == "finance:newcat")
async def cb_newcat(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FinanceStates.add_category_name)
    await callback.message.edit_text(
        "📝 Отправь название и эмодзи новой категории расхода.\n<i>Например: 🚗 Автомобиль</i>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(FinanceStates.add_category_name)
async def process_new_category(message: Message, state: FSMContext):
    await _safe_delete(message)
    text = message.text.strip()
    icon = text[0] if text and len(text) > 1 and not text[0].isalnum() else "🔹"
    name = text[1:].strip() if icon != "🔹" else text
    
    async with AsyncSessionLocal() as session:
        user = await crud.get_or_create_user(
            session, message.from_user.id,
            message.from_user.username, message.from_user.first_name
        )
        await crud.add_category(session, user.id, name, TransactionType.expense, icon)
        
    await state.clear()
    await message.answer(f"Категория {icon} {name} добавлена! 🎉")
    
    class DummyCallback:
        def __init__(self, msg, usr):
            self.message = msg
            self.from_user = usr
        async def answer(self): pass
    await cb_categories(DummyCallback(message, message.from_user))


# ─── Бюджеты ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "finance:budgets")
async def cb_budgets(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        budgets = await crud.get_budgets(session, callback.from_user.id)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    if not budgets:
        await callback.message.answer(
            "🎯 <b>Бюджеты</b>\n\nТут пусто. Установи лимит на категорию, и я предупрежу, если ты его превысишь!",
            parse_mode="HTML",
            reply_markup=budgets_list_kb(budgets)
        )
    else:
        await callback.message.answer(
            "🎯 <b>Твои бюджеты</b>\nНажми, чтобы удалить.",
            parse_mode="HTML",
            reply_markup=budgets_list_kb(budgets)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("finance:delbudget:"))
async def cb_delbudget(callback: CallbackQuery):
    b_id = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        await crud.delete_budget(session, b_id, callback.from_user.id)
    await callback.answer("Бюджет удалён 🗑")
    await cb_budgets(callback)


@router.callback_query(F.data == "finance:addbudget")
async def cb_addbudget(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        cats = await crud.get_categories(session, callback.from_user.id, TransactionType.expense)
    
    await state.set_state(FinanceStates.add_budget_cat)
    await callback.message.edit_text(
        "На какую категорию установим лимит?",
        reply_markup=category_select_kb(cats)
    )
    await callback.answer()


@router.callback_query(FinanceStates.add_budget_cat, F.data.startswith("finance:selcat:"))
async def cb_budget_cat(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split(":")[2])
    await state.update_data(budget_cat_id=cat_id)
    await state.set_state(FinanceStates.add_budget_amount)
    
    await callback.message.edit_text("💵 Введи сумму лимита (например: <code>10000</code>):", parse_mode="HTML")
    await callback.answer()


@router.message(FinanceStates.add_budget_amount)
async def process_budget_amount(message: Message, state: FSMContext):
    await _safe_delete(message)
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0: raise ValueError
    except ValueError:
        await message.answer("Непохоже на число. Попробуй ещё:")
        return

    await state.update_data(budget_amount=amount)
    await state.set_state(FinanceStates.add_budget_period)
    await message.answer("📅 На какой период?", reply_markup=budget_period_kb())


@router.callback_query(FinanceStates.add_budget_period, F.data.startswith("finance:budget_period:"))
async def cb_budget_period(callback: CallbackQuery, state: FSMContext):
    p_str = callback.data.split(":")[2]
    period = BudgetPeriod(p_str)
    
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        await crud.add_budget(
            session, callback.from_user.id,
            data["budget_cat_id"], data["budget_amount"], period
        )
        
    await state.clear()
    await callback.answer("✅ Бюджет сохранён!", show_alert=True)
    await cb_budgets(callback)


# ─── Account Wizard ──────────────────────────────────────────────────────────

@router.message(AccountWizard.add_name)
async def acc_wiz_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AccountWizard.add_balance)
    await message.answer("Отлично. Какой сейчас начальный баланс на этом счете? (Введи число)")

@router.message(AccountWizard.add_balance)
async def acc_wiz_balance(message: Message, state: FSMContext):
    try:
        balance = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Пожалуйста, введи число (например 5000).")
        return
    await state.update_data(balance=balance)
    await state.set_state(AccountWizard.add_interest_bearing)
    await message.answer("На этот счет начисляется процент (как по вкладу/копилке)?", reply_markup=yes_no_kb())

@router.callback_query(AccountWizard.add_interest_bearing)
async def acc_wiz_bearing(callback: CallbackQuery, state: FSMContext):
    is_bearing = (callback.data == "yes")
    await state.update_data(is_interest_bearing=is_bearing)
    if is_bearing:
        await state.set_state(AccountWizard.add_interest_rate)
        await callback.message.edit_text("Какой процент начисляется? (Введи число, например 5 или 5.5)")
    else:
        await _save_account_from_wizard(callback.message.chat.id, state)
        await state.set_state(AccountWizard.ask_more_accounts)
        await callback.message.edit_text("Счет сохранен! Добавим еще один?", reply_markup=yes_no_kb())
    await callback.answer()

@router.message(AccountWizard.add_interest_rate)
async def acc_wiz_rate(message: Message, state: FSMContext):
    try:
        rate = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введи число (например 5.5).")
        return
    await state.update_data(interest_rate=rate)
    await state.set_state(AccountWizard.add_interest_period)
    await message.answer("Как часто происходит начисление?", reply_markup=interest_period_kb())

@router.callback_query(AccountWizard.add_interest_period, F.data.startswith("period:"))
async def acc_wiz_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split(":")[1]
    await state.update_data(interest_period=period)
    await _save_account_from_wizard(callback.message.chat.id, state)
    await state.set_state(AccountWizard.ask_more_accounts)
    await callback.message.edit_text("Счет с процентами сохранен! Добавим еще один счет?", reply_markup=yes_no_kb())
    await callback.answer()

async def _save_account_from_wizard(user_id: int, state: FSMContext):
    data = await state.get_data()
    async with AsyncSessionLocal() as session:
        await crud.add_account(
            session, user_id=user_id,
            name=data["name"],
            balance=data["balance"],
            is_interest_bearing=data.get("is_interest_bearing", False),
            interest_rate=data.get("interest_rate"),
            interest_period=data.get("interest_period")
        )

@router.callback_query(AccountWizard.ask_more_accounts)
async def acc_wiz_more(callback: CallbackQuery, state: FSMContext):
    if callback.data == "yes":
        await state.set_state(AccountWizard.add_name)
        await callback.message.edit_text("Введи название нового счета:")
    else:
        async with AsyncSessionLocal() as session:
            accounts = await crud.get_accounts(session, callback.from_user.id)
            if len(accounts) == 1:
                await crud.set_main_account(session, callback.from_user.id, accounts[0].id)
                await state.clear()
                await callback.message.edit_text("✅ Основной счет установлен автоматически.")
            else:
                await state.set_state(AccountWizard.select_main_account)
                await callback.message.edit_text("Какой из этих счетов сделать основным (для быстрых трат)?", reply_markup=account_select_kb(accounts, "finance:wiz:main"))
    await callback.answer()

@router.callback_query(AccountWizard.select_main_account, F.data.startswith("finance:wiz:main:"))
async def acc_wiz_main(callback: CallbackQuery, state: FSMContext):
    acc_id = int(callback.data.split(":")[3])
    async with AsyncSessionLocal() as session:
        await crud.set_main_account(session, callback.from_user.id, acc_id)
    await state.clear()
    await callback.message.edit_text("✅ Настройка счетов завершена!")
    # Show menu
    class DummyCallback:
        def __init__(self, msg, usr):
            self.message = msg
            self.from_user = usr
        async def answer(self, **kwargs):
            pass
    from bot.handlers.finance import _send_finance_menu
    await _send_finance_menu(DummyCallback(callback.message, callback.from_user))

