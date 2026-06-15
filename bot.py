import logging
import os
import subprocess
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from handlers.worker import (
    start, fill_conv, edit_conv, add_day_conv, del_day_conv, my_records
)
from handlers.admin import (
    day_view, toggle_callback, stats, report, worker_filter,
    list_workers, add_worker_conv, remove_worker_conv,
    admin_edit_worker_conv, add_record_conv, del_record_conv
)
from handlers.owner import (
    access_menu, list_roles, set_role_conv, unset_role_conv
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def run_webapp():
    port = int(os.environ.get("PORT", 8080))
    subprocess.Popen([
        "gunicorn", "webapp:app",
        "--bind", f"0.0.0.0:{port}",
        "--workers", "1",
        "--timeout", "120",
        "--log-level", "info"
    ])
    logging.info(f"Веб-панель запущено на порті {port}")


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN не знайдено")

    run_webapp()

    application = Application.builder().token(token).build()

    # Група -1 — вищий пріоритет
    application.add_handler(
        MessageHandler(filters.Regex("^📊 Мої записи$"), my_records), group=-1
    )
    application.add_handler(del_day_conv(), group=-1)

    # Група 0
    application.add_handler(CommandHandler("start", start))
    application.add_handler(fill_conv())
    application.add_handler(edit_conv())
    application.add_handler(add_day_conv())
    application.add_handler(add_worker_conv())
    application.add_handler(remove_worker_conv())
    application.add_handler(admin_edit_worker_conv())
    application.add_handler(add_record_conv())
    application.add_handler(del_record_conv())
    application.add_handler(CommandHandler("day", day_view))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("workers", list_workers))
    application.add_handler(CommandHandler("worker_report", worker_filter))
    application.add_handler(CallbackQueryHandler(toggle_callback, pattern=r"^(univ|bonus):"))
    application.add_handler(CommandHandler("access", access_menu))
    application.add_handler(CommandHandler("list_roles", list_roles))
    application.add_handler(set_role_conv())
    application.add_handler(unset_role_conv())

    logging.info("Бот запущено...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
