from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from bot.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Создаёт все таблицы при запуске и проверяет недостающие колонки."""
    async with engine.begin() as conn:
        from bot.database import models  # noqa — зарегистрировать модели
        await conn.run_sync(Base.metadata.create_all)
        
        # Ручная миграция для добавления новых колонок, если их нет
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN evening_report_enabled BOOLEAN DEFAULT FALSE;"))
        except Exception:
            pass  # Колонка уже есть
            
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN evening_report_time VARCHAR(5);"))
        except Exception:
            pass  # Колонка уже есть
