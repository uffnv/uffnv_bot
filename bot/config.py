from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан в .env")
