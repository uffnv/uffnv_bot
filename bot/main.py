"""Точка входа бота."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN
from bot.database.base import init_db
from bot.handlers import common, finance, fitness, tasks, admin, habits, excel
from bot.scheduler.jobs import setup_scheduler
from bot.middlewares.clean_chat import CleanChatMiddleware
from aiohttp import web
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def keep_alive_handler(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', keep_alive_handler)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Keep-alive web server started on port {port}")

async def main():
    logger.info("Инициализация базы данных...")
    await init_db()
    
    # Запуск web-сервера для Render
    await start_web_server()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, disable_notification=True)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(CleanChatMiddleware())
    dp.callback_query.outer_middleware(CleanChatMiddleware())

    # Регистрация роутеров
    dp.include_router(common.router)
    dp.include_router(finance.router)
    dp.include_router(excel.router)
    dp.include_router(habits.router)
    dp.include_router(tasks.router)
    dp.include_router(fitness.router)
    dp.include_router(admin.router)

    await bot.delete_webhook(drop_pending_updates=True)

    # Запуск шедулера
    setup_scheduler(bot)

    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
