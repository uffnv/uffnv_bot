"""CRUD-операции для всех модулей."""
from datetime import date, datetime, timedelta
from typing import Optional

import pytz
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    User, Transaction, FinanceCategory, Budget,
    FoodLog, FoodProduct, WeightLog, FitnessGoal,
    Task, TransactionType, BudgetPeriod, TaskPriority, RecurrenceType,
    PhysicalProfile, ActivityLevel, FitnessPlanType, Account, InterestPeriod
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def user_now(user: User) -> datetime:
    """Текущее время в часовом поясе пользователя."""
    tz = pytz.timezone(user.timezone)
    return datetime.now(tz)


def user_today(user: User) -> date:
    return user_now(user).date()


# ─── Users ────────────────────────────────────────────────────────────────────

async def get_or_create_user(session: AsyncSession, telegram_id: int,
                              username: str | None, first_name: str | None) -> User:
    user = await session.get(User, telegram_id)
    if not user:
        user = User(id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def update_user_timezone(session: AsyncSession, user_id: int, timezone: str) -> User | None:
    user = await get_user(session, user_id)
    if user:
        user.timezone = timezone
        await session.commit()
    return user


async def set_main_account(session: AsyncSession, user_id: int, account_id: int | None) -> User | None:
    user = await get_user(session, user_id)
    if user:
        user.main_account_id = account_id
        await session.commit()
    return user


async def update_digest_time(session: AsyncSession, user_id: int, time_str: str) -> None:
    user = await session.get(User, user_id)
    if user:
        user.digest_time = time_str
        await session.commit()


async def get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User))
    return result.scalars().all()


# ─── Finance Categories ───────────────────────────────────────────────────────

DEFAULT_INCOME_CATEGORIES = ["Зарплата", "Подработка", "Подарок", "Другое"]
DEFAULT_EXPENSE_CATEGORIES = ["Продукты", "Транспорт", "Кафе/Ресторан", "ЖКХ", "Развлечения", "Здоровье", "Одежда", "Другое"]


async def ensure_default_categories(session: AsyncSession, user_id: int) -> None:
    """Создаёт дефолтные категории для нового пользователя."""
    result = await session.execute(select(FinanceCategory).where(FinanceCategory.user_id == user_id))
    if result.scalars().first():
        return  # уже есть
    for name in DEFAULT_INCOME_CATEGORIES:
        session.add(FinanceCategory(user_id=user_id, name=name, type=TransactionType.income))
    for name in DEFAULT_EXPENSE_CATEGORIES:
        session.add(FinanceCategory(user_id=user_id, name=name, type=TransactionType.expense))
    await session.commit()


async def get_categories(session: AsyncSession, user_id: int,
                          type_: TransactionType) -> list[FinanceCategory]:
    result = await session.execute(
        select(FinanceCategory).where(
            FinanceCategory.user_id == user_id,
            FinanceCategory.type == type_
        ).order_by(FinanceCategory.name)
    )
    return result.scalars().all()


async def add_category(session: AsyncSession, user_id: int,
                        name: str, type_: TransactionType) -> FinanceCategory:
    cat = FinanceCategory(user_id=user_id, name=name, type=type_)
    session.add(cat)
    await session.commit()
    await session.refresh(cat)
    return cat


async def delete_category(session: AsyncSession, category_id: int, user_id: int) -> bool:
    cat = await session.get(FinanceCategory, category_id)
    if cat and cat.user_id == user_id:
        await session.delete(cat)
        await session.commit()
        return True
    return False


# ─── Accounts ──────────────────────────────────────────────────────────────────

async def get_accounts(session: AsyncSession, user_id: int) -> list[Account]:
    result = await session.execute(
        select(Account).where(Account.user_id == user_id).order_by(Account.id)
    )
    return result.scalars().all()


async def get_account(session: AsyncSession, account_id: int, user_id: int) -> Account | None:
    account = await session.get(Account, account_id)
    if account and account.user_id == user_id:
        return account
    return None


async def add_account(
    session: AsyncSession, user_id: int, name: str, balance: float = 0.0,
    is_interest_bearing: bool = False, interest_rate: float | None = None,
    interest_period: InterestPeriod | None = None
) -> Account:
    acc = Account(
        user_id=user_id, name=name, balance=balance,
        is_interest_bearing=is_interest_bearing,
        interest_rate=interest_rate,
        interest_period=interest_period
    )
    session.add(acc)
    await session.commit()
    await session.refresh(acc)
    return acc


async def delete_account(session: AsyncSession, account_id: int, user_id: int) -> bool:
    acc = await get_account(session, account_id, user_id)
    if acc:
        await session.delete(acc)
        await session.commit()
        return True
    return False


# ─── Transactions ─────────────────────────────────────────────────────────────

async def add_transaction(session: AsyncSession, user_id: int, account_id: int, amount: float,
                           type_: TransactionType, category_id: int | None,
                           note: str | None, tx_date: date) -> Transaction | None:
    acc = await session.get(Account, account_id)
    if not acc or acc.user_id != user_id:
        return None

    tx = Transaction(
        user_id=user_id, account_id=account_id, amount=amount, type=type_,
        category_id=category_id, note=note, date=tx_date
    )
    
    # Update account balance
    if type_ == TransactionType.income:
        acc.balance += amount
    else:
        acc.balance -= amount

    session.add(tx)
    await session.commit()
    await session.refresh(tx)
    return tx


async def get_transactions(session: AsyncSession, user_id: int,
                            from_date: date, to_date: date) -> list[Transaction]:
    result = await session.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.date >= from_date,
            Transaction.date <= to_date
        ).order_by(Transaction.date.desc(), Transaction.created_at.desc())
    )
    return result.scalars().all()


async def get_transactions_history(session: AsyncSession, user_id: int, limit: int = 10, offset: int = 0) -> list[Transaction]:
    result = await session.execute(
        select(Transaction).where(Transaction.user_id == user_id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .limit(limit).offset(offset)
    )
    return result.scalars().all()


async def get_balance(session: AsyncSession, user_id: int,
                       from_date: date, to_date: date) -> dict:
    """Возвращает {income, expense, balance}."""
    txs = await get_transactions(session, user_id, from_date, to_date)
    income = sum(float(t.amount) for t in txs if t.type == TransactionType.income)
    expense = sum(float(t.amount) for t in txs if t.type == TransactionType.expense)
    return {"income": income, "expense": expense, "balance": income - expense}


async def delete_transaction(session: AsyncSession, tx_id: int, user_id: int) -> bool:
    tx = await session.get(Transaction, tx_id)
    if tx and tx.user_id == user_id:
        acc = await session.get(Account, tx.account_id)
        if acc:
            # Revert the balance
            if tx.type == TransactionType.income:
                acc.balance -= tx.amount
            else:
                acc.balance += tx.amount
        
        await session.delete(tx)
        await session.commit()
        return True
    return False


async def delete_transactions_period(session: AsyncSession, user_id: int, from_date: date, to_date: date) -> int:
    txs = await get_transactions(session, user_id, from_date, to_date)
    count = 0
    for tx in txs:
        acc = await session.get(Account, tx.account_id)
        if acc:
            if tx.type == TransactionType.income:
                acc.balance -= tx.amount
            else:
                acc.balance += tx.amount
        await session.delete(tx)
        count += 1
    if count > 0:
        await session.commit()
    return count


# ─── Budget ───────────────────────────────────────────────────────────────────

async def set_budget(session: AsyncSession, user_id: int, category_id: int,
                      limit_amount: float, period: BudgetPeriod) -> Budget:
    result = await session.execute(
        select(Budget).where(Budget.user_id == user_id, Budget.category_id == category_id)
    )
    budget = result.scalars().first()
    if budget:
        budget.limit_amount = limit_amount
        budget.period = period
    else:
        budget = Budget(user_id=user_id, category_id=category_id,
                        limit_amount=limit_amount, period=period)
        session.add(budget)
    await session.commit()
    await session.refresh(budget)
    return budget


async def get_budgets(session: AsyncSession, user_id: int) -> list[Budget]:
    result = await session.execute(select(Budget).where(Budget.user_id == user_id))
    return result.scalars().all()


async def check_budget_exceeded(session: AsyncSession, user_id: int,
                                  category_id: int, today: date) -> Optional[tuple[float, float]]:
    """Если бюджет превышен — возвращает (потрачено, лимит), иначе None."""
    result = await session.execute(
        select(Budget).where(Budget.user_id == user_id, Budget.category_id == category_id)
    )
    budget = result.scalars().first()
    if not budget:
        return None

    if budget.period == BudgetPeriod.week:
        from_date = today - timedelta(days=today.weekday())
    else:
        from_date = today.replace(day=1)

    txs = await get_transactions(session, user_id, from_date, today)
    spent = sum(float(t.amount) for t in txs
                if t.type == TransactionType.expense and t.category_id == category_id)
    limit = float(budget.limit_amount)
    if spent > limit:
        return (spent, limit)
    return None


# ─── Food Products ────────────────────────────────────────────────────────────

async def get_food_products(session: AsyncSession, user_id: int,
                             search: str | None = None) -> list[FoodProduct]:
    q = select(FoodProduct).where(FoodProduct.user_id == user_id)
    if search:
        q = q.where(FoodProduct.name.ilike(f"%{search}%"))
    q = q.order_by(FoodProduct.name)
    result = await session.execute(q)
    return result.scalars().all()


async def add_food_product(session: AsyncSession, user_id: int, name: str,
                            calories: int, protein: float, fat: float, carbs: float) -> FoodProduct:
    p = FoodProduct(user_id=user_id, name=name, calories=calories,
                    protein=protein, fat=fat, carbs=carbs)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def delete_food_product(session: AsyncSession, product_id: int, user_id: int) -> bool:
    p = await session.get(FoodProduct, product_id)
    if p and p.user_id == user_id:
        await session.delete(p)
        await session.commit()
        return True
    return False


# ─── Food Log ─────────────────────────────────────────────────────────────────

async def add_food_log(session: AsyncSession, user_id: int, product_name: str,
                        grams: float, calories: int, protein: float,
                        fat: float, carbs: float, log_date: date) -> FoodLog:
    log = FoodLog(
        user_id=user_id, product_name=product_name, grams=grams,
        calories=calories, protein=protein, fat=fat, carbs=carbs, date=log_date
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def get_food_log(session: AsyncSession, user_id: int, log_date: date) -> list[FoodLog]:
    result = await session.execute(
        select(FoodLog).where(FoodLog.user_id == user_id, FoodLog.date == log_date)
        .order_by(FoodLog.created_at)
    )
    return result.scalars().all()


async def delete_food_log(session: AsyncSession, log_id: int, user_id: int) -> bool:
    log = await session.get(FoodLog, log_id)
    if log and log.user_id == user_id:
        await session.delete(log)
        await session.commit()
        return True
    return False


def calc_food_summary(logs: list[FoodLog]) -> dict:
    return {
        "calories": sum(l.calories for l in logs),
        "protein": round(sum(float(l.protein) for l in logs), 1),
        "fat": round(sum(float(l.fat) for l in logs), 1),
        "carbs": round(sum(float(l.carbs) for l in logs), 1),
    }


# ─── Weight ───────────────────────────────────────────────────────────────────

async def add_weight(session: AsyncSession, user_id: int,
                      weight: float, log_date: date) -> WeightLog:
    # Обновляем запись за этот день если есть
    result = await session.execute(
        select(WeightLog).where(WeightLog.user_id == user_id, WeightLog.date == log_date)
    )
    existing = result.scalars().first()
    if existing:
        existing.weight = weight
        await session.commit()
        return existing
    w = WeightLog(user_id=user_id, weight=weight, date=log_date)
    session.add(w)
    await session.commit()
    await session.refresh(w)
    return w


async def get_weight_log(session: AsyncSession, user_id: int,
                          days: int = 30) -> list[WeightLog]:
    from_date = date.today() - timedelta(days=days)
    result = await session.execute(
        select(WeightLog).where(WeightLog.user_id == user_id,
                                WeightLog.date >= from_date)
        .order_by(WeightLog.date)
    )
    return result.scalars().all()


# ─── Fitness Goal ─────────────────────────────────────────────────────────────

async def get_fitness_goal(session: AsyncSession, user_id: int) -> Optional[FitnessGoal]:
    result = await session.execute(
        select(FitnessGoal).where(FitnessGoal.user_id == user_id)
    )
    return result.scalars().first()


async def set_fitness_goal(session: AsyncSession, user_id: int,
                            target_weight: float | None,
                            daily_calories: int | None) -> FitnessGoal:
    goal = await get_fitness_goal(session, user_id)
    if goal:
        if target_weight is not None:
            goal.target_weight = target_weight
        if daily_calories is not None:
            goal.daily_calories = daily_calories
    else:
        goal = FitnessGoal(user_id=user_id, target_weight=target_weight,
                           daily_calories=daily_calories)
        session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return goal


# ─── Tasks ────────────────────────────────────────────────────────────────────

async def add_task(session: AsyncSession, user_id: int, title: str,
                    description: str | None, priority: TaskPriority,
                    due_date: date | None, is_recurring: bool,
                    recurrence: RecurrenceType | None,
                    remind_at: str | None) -> Task:
    task = Task(
        user_id=user_id, title=title, description=description,
        priority=priority, due_date=due_date, is_recurring=is_recurring,
        recurrence=recurrence, remind_at=remind_at
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_tasks(session: AsyncSession, user_id: int,
                     show_done: bool = False) -> list[Task]:
    q = select(Task).where(Task.user_id == user_id)
    if not show_done:
        q = q.where(Task.is_done == False)
    q = q.order_by(Task.due_date.asc().nullslast(), Task.priority.desc())
    result = await session.execute(q)
    return result.scalars().all()


async def get_tasks_for_date(session: AsyncSession, user_id: int,
                              for_date: date) -> list[Task]:
    """Задачи на конкретный день + повторяющиеся."""
    result = await session.execute(
        select(Task).where(
            Task.user_id == user_id,
            Task.is_done == False,
            (Task.due_date == for_date) | (Task.is_recurring == True)
        ).order_by(Task.priority.desc())
    )
    return result.scalars().all()


async def mark_task_done(session: AsyncSession, task_id: int, user_id: int) -> bool:
    task = await session.get(Task, task_id)
    if task and task.user_id == user_id:
        if task.is_recurring:
            # Для повторяющихся — обновляем дату на следующий период
            if task.recurrence == RecurrenceType.daily:
                task.due_date = date.today() + timedelta(days=1)
            elif task.recurrence == RecurrenceType.weekly:
                task.due_date = date.today() + timedelta(weeks=1)
            elif task.recurrence == RecurrenceType.monthly:
                d = date.today()
                month = d.month + 1 if d.month < 12 else 1
                year = d.year if d.month < 12 else d.year + 1
                task.due_date = d.replace(year=year, month=month)
        else:
            task.is_done = True
        await session.commit()
        return True
    return False


async def delete_task(session: AsyncSession, task_id: int, user_id: int) -> bool:
    task = await session.get(Task, task_id)
    if task and task.user_id == user_id:
        await session.delete(task)
        await session.commit()
        return True
    return False


async def delete_completed_tasks(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(Task).where(Task.user_id == user_id, Task.is_done == True)
    )
    tasks = result.scalars().all()
    count = 0
    for task in tasks:
        await session.delete(task)
        count += 1
    if count > 0:
        await session.commit()
    return count


async def get_productivity_stats(session: AsyncSession, user_id: int,
                                  days: int = 7) -> dict:
    from_date = date.today() - timedelta(days=days)
    result = await session.execute(
        select(Task).where(Task.user_id == user_id,
                           Task.created_at >= datetime.combine(from_date, datetime.min.time()))
    )
    all_tasks = result.scalars().all()
    total = len(all_tasks)
    done = sum(1 for t in all_tasks if t.is_done)
    return {"total": total, "done": done, "percent": round(done / total * 100) if total else 0}


async def get_tasks_with_reminders(session: AsyncSession) -> list[Task]:
    """Все задачи с установленным временем напоминания."""
    result = await session.execute(
        select(Task).where(Task.remind_at.isnot(None), Task.is_done == False)
    )
    return result.scalars().all()


# ─── Physical Profile ─────────────────────────────────────────────────────────────

async def get_physical_profile(session: AsyncSession, user_id: int) -> Optional[PhysicalProfile]:
    result = await session.execute(
        select(PhysicalProfile).where(PhysicalProfile.user_id == user_id)
    )
    return result.scalars().first()


async def set_physical_profile(
    session: AsyncSession,
    user_id: int,
    sex: str,
    age: int,
    height: int,
    weight: float,
    activity: ActivityLevel,
    plan: FitnessPlanType,
) -> PhysicalProfile:
    profile = await get_physical_profile(session, user_id)
    if profile:
        profile.sex = sex
        profile.age = age
        profile.height = height
        profile.weight = weight
        profile.activity = activity
        profile.plan = plan
    else:
        profile = PhysicalProfile(
            user_id=user_id, sex=sex, age=age, height=height,
            weight=weight, activity=activity, plan=plan
        )
        session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def update_physical_plan(
    session: AsyncSession, user_id: int, plan: FitnessPlanType
) -> None:
    profile = await get_physical_profile(session, user_id)
    if profile:
        profile.plan = plan
        await session.commit()

async def delete_food_logs_for_date(session: AsyncSession, user_id: int, log_date: date) -> int:
    result = await session.execute(
        select(FoodLog).where(FoodLog.user_id == user_id, FoodLog.date == log_date)
    )
    logs = result.scalars().all()
    count = 0
    for log in logs:
        await session.delete(log)
        count += 1
    if count > 0:
        await session.commit()
    return count
