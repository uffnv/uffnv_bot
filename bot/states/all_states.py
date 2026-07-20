from aiogram.fsm.state import State, StatesGroup


class FitnessProfileStates(StatesGroup):
    """Мастер настройки физического профиля."""
    enter_sex        = State()
    enter_age        = State()
    enter_height     = State()
    enter_weight_p   = State()  # вес при настройке профиля
    choose_activity  = State()
    choose_plan      = State()
    confirm_profile  = State()


class AccountWizard(StatesGroup):
    add_name = State()
    add_balance = State()
    add_interest_bearing = State()
    add_interest_rate = State()
    add_interest_period = State()
    ask_more_accounts = State()
    select_main_account = State()


class FinanceStates(StatesGroup):
    # Добавление транзакции
    choose_type = State()
    choose_category = State()
    enter_amount = State()
    enter_note = State()
    confirm = State()
    # Категории
    add_category_name = State()
    # Бюджет
    add_budget_cat = State()
    add_budget_amount = State()
    add_budget_period = State()


class FitnessStates(StatesGroup):
    # Добавление продукта в базу
    product_name = State()
    product_calories = State()
    product_protein = State()
    product_fat = State()
    product_carbs = State()
    # Лог питания
    log_search_product = State()
    log_select_product = State()
    log_enter_grams = State()
    # Ручной ввод
    log_manual_name = State()
    log_manual_calories = State()
    log_manual_protein = State()
    log_manual_fat = State()
    log_manual_carbs = State()
    log_manual_grams = State()
    # Вес
    enter_weight = State()
    # Цели
    goal_weight = State()
    goal_calories = State()


class TaskStates(StatesGroup):
    enter_title = State()
    enter_description = State()
    choose_priority = State()
    enter_due_date = State()
    choose_recurring = State()
    choose_recurrence_type = State()
    enter_remind_time = State()
    # Дайджест
    digest_time = State()
    # Часовой пояс
    enter_timezone = State()
