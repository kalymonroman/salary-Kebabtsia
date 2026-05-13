import logging
import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from handlers.worker import (
    start, fill_conv, edit_conv, add_day_conv, del_day_conv, my_records
)
from handlers.admin import (
    day_view, toggle_callback, stats, report, worker_filter,
    list_workers, add_worker_conv, remove_worker_conv
)
from handlers.owner import (
    access_menu, list_roles, set_role_conv, unset_role_conv
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN не знайдено в .env")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(fill_conv())
    app.add_handler(edit_conv())
    app.add_handler(add_day_conv())
    app.add_handler(del_day_conv())
    app.add_handler(MessageHandler(filters.Regex("^📊 Мої записи$"), my_records))
    app.add_handler(add_worker_conv())
    app.add_handler(remove_worker_conv())
    app.add_handler(CommandHandler("day", day_view))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("workers", list_workers))
    app.add_handler(CommandHandler("worker_report", worker_filter))
    app.add_handler(CallbackQueryHandler(toggle_callback, pattern=r"^(univ|bonus):"))
    app.add_handler(CommandHandler("access", access_menu))
    app.add_handler(CommandHandler("list_roles", list_roles))
    app.add_handler(set_role_conv())
    app.add_handler(unset_role_conv())

    logging.info("Бот запущено...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
