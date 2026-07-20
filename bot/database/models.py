from datetime import datetime, date
import enum

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, Time
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from bot.database.base import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class BudgetPeriod(str, enum.Enum):
    week = "week"
    month = "month"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RecurrenceType(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class InterestPeriod(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class ActivityLevel(str, enum.Enum):
    sedentary   = "sedentary"
    light       = "light"
    moderate    = "moderate"
    active      = "active"
    very_active = "very_active"


class FitnessPlanType(str, enum.Enum):
    cut_hard = "cut_hard"
    cut_soft = "cut_soft"
    maintain = "maintain"
    bulk     = "bulk"


# ─── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # telegram_id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(32), default="UTC")
    digest_time: Mapped[str | None] = mapped_column(String(5))  # "HH:MM"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    main_account_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("accounts.id", name="fk_user_main_account"), nullable=True)

    # Relationships
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="user", foreign_keys="Account.user_id")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    finance_categories: Mapped[list["FinanceCategory"]] = relationship("FinanceCategory", back_populates="user")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    food_logs: Mapped[list["FoodLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    food_products: Mapped[list["FoodProduct"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    weight_logs: Mapped[list["WeightLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    fitness_goal: Mapped["FitnessGoal | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    physical_profile: Mapped["PhysicalProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ─── Finance ──────────────────────────────────────────────────────────────────

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    
    is_interest_bearing: Mapped[bool] = mapped_column(Boolean, default=False)
    interest_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)  # в процентах, например 5.0
    interest_period: Mapped[InterestPeriod | None] = mapped_column(Enum(InterestPeriod), nullable=True)
    last_interest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="accounts", foreign_keys=[user_id])
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")


class FinanceCategory(Base):
    __tablename__ = "finance_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    icon: Mapped[str | None] = mapped_column(String(8))  # Emoji
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="finance_categories")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True)
    
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    date: Mapped[date] = mapped_column(Date, default=date.today)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    account: Mapped["Account"] = relationship("Account", back_populates="transactions")
    category: Mapped["FinanceCategory | None"] = relationship("FinanceCategory")


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("finance_categories.id", ondelete="CASCADE"))
    limit_amount: Mapped[float] = mapped_column(Numeric(12, 2))
    period: Mapped[BudgetPeriod] = mapped_column(Enum(BudgetPeriod))

    user: Mapped["User"] = relationship(back_populates="budgets")


# ─── Fitness ──────────────────────────────────────────────────────────────────

class PhysicalProfile(Base):
    """Физический профиль пользователя для расчёта нормы КБЖУ."""
    __tablename__ = "physical_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    sex: Mapped[str] = mapped_column(String(10))          # "male" / "female"
    age: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)          # см
    weight: Mapped[float] = mapped_column(Numeric(5, 2))  # кг
    activity: Mapped[ActivityLevel] = mapped_column(Enum(ActivityLevel))
    plan: Mapped[FitnessPlanType] = mapped_column(Enum(FitnessPlanType))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="physical_profile")


class FoodProduct(Base):
    """Пользовательская база продуктов (на 100 г)."""
    __tablename__ = "food_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    calories: Mapped[int] = mapped_column(Integer)
    protein: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    fat: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    carbs: Mapped[float] = mapped_column(Numeric(6, 2), default=0)

    user: Mapped["User"] = relationship(back_populates="food_products")


class FoodLog(Base):
    """Запись о приёме пищи (за конкретный день)."""
    __tablename__ = "food_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    product_name: Mapped[str] = mapped_column(String(128))
    grams: Mapped[float] = mapped_column(Numeric(7, 2), default=100)
    calories: Mapped[int] = mapped_column(Integer)
    protein: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    fat: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    carbs: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="food_logs")


class WeightLog(Base):
    __tablename__ = "weight_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    weight: Mapped[float] = mapped_column(Numeric(5, 2))
    date: Mapped[date] = mapped_column(Date)

    user: Mapped["User"] = relationship(back_populates="weight_logs")


class FitnessGoal(Base):
    __tablename__ = "fitness_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    target_weight: Mapped[float | None] = mapped_column(Numeric(5, 2))
    daily_calories: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="fitness_goal")


# ─── Tasks ────────────────────────────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.medium)
    due_date: Mapped[date | None] = mapped_column(Date)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence: Mapped[RecurrenceType | None] = mapped_column(Enum(RecurrenceType))
    remind_at: Mapped[str | None] = mapped_column(String(5))  # "HH:MM" в UTC
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="tasks")
