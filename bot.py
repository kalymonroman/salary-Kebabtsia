import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
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

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def run_server():
    HTTPServer(("0.0.0.0", 8080), PingHandler).serve_forever()

threading.Thread(target=run_server, daemon=True).start()


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN не знайдено")

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
    app.add_handler(CommandHandler("worker_r
