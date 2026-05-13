"""
Хендлери для власника:
  - /access — управління доступами
  - /set_role — призначити роль
  - /unset_role — забрати роль
  - /list_roles — список ролей
"""
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ConversationHandler, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from sheets import SheetsManager
from calc import LOCATIONS

db = SheetsManager()

ROLES_UA = {
    "location_admin": "Адмін закладу",
    "superadmin": "Головний адмін",
    "worker": "Видалити роль (залишити як працівника)",
}

(SR_USER, SR_ROLE, SR_LOCATION, SR_CONFIRM) = range(60, 64)
(UR_USER, UR_CONFIRM) = range(70, 72)


async def access_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_owner(tid):
        await update.message.reply_text("⛔ Тільки власник може керувати доступами.")
        return
    await update.message.reply_text(
        "🔐 *Управління доступами*\n\n"
        "/set_role — призначити роль\n"
        "/unset_role — забрати роль\n"
        "/list_roles — список всіх ролей",
        parse_mode="Markdown"
    )


async def list_roles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_owner(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return
    roles = db.get_all_roles()
    if not roles:
        await update.message.reply_text("📭 Ролей не призначено.")
        return
    role_names = {
        "owner": "👑 Власник",
        "superadmin": "🔶 Головний адмін",
        "location_admin": "🔷 Адмін закладу",
    }
    lines = ["👥 *Призначені ролі:*\n"]
    for r in roles:
        role_label = role_names.get(r["role"], r["role"])
        loc = f" — {r['location']}" if r.get("location") else ""
        # Знайти ім'я
        w = db.get_worker(r["telegram_id"])
        name = w["name"] if w else f"ID:{r['telegram_id']}"
        lines.append(f"{role_label}: {name}{loc}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /set_role ─────────────────────────────────────────────────────────────────

async def set_role_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_owner(tid):
        await update.message.reply_text("⛔ Тільки власник може призначати ролі.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Введіть ім'я або Telegram ID користувача:",
        reply_markup=ReplyKeyboardRemove()
    )
    return SR_USER


async def set_role_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # Спочатку пошук за ID
    try:
        search_id = int(text)
        w = db.get_worker(search_id)
        if w:
            context.user_data["sr_worker"] = w
            return await _ask_role(update, context)
    except ValueError:
        pass
    # Пошук за ім'ям
    results = db.search_workers(text)
    if not results:
        await update.message.reply_text("❌ Не знайдено. Спробуйте ще раз:")
        return SR_USER
    if len(results) == 1:
        context.user_data["sr_worker"] = results[0]
        return await _ask_role(update, context)
    context.user_data["sr_results"] = results
    lines = ["Знайдено кілька:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['name']}")
    lines.append("\nВведіть номер:")
    await update.message.reply_text("\n".join(lines))
    return SR_USER + 10  # Проміжний стан вибору


async def set_role_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(update.message.text.strip()) - 1
        context.user_data["sr_worker"] = context.user_data["sr_results"][idx]
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Введіть коректний номер:")
        return SR_USER + 10
    return await _ask_role(update, context)


async def _ask_role(update, context):
    w = context.user_data["sr_worker"]
    current = db.get_role(int(w["telegram_id"]))
    curr_label = current["role"] if current else "немає"
    await update.message.reply_text(
        f"👤 {w['name']}\nПоточна роль: {curr_label}\n\nОберіть нову роль:",
        reply_markup=ReplyKeyboardMarkup(
            [["Адмін закладу"], ["Головний адмін"], ["❌ Скасувати"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return SR_ROLE


async def set_role_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    if "Адмін закладу" in text:
        context.user_data["sr_role"] = "location_admin"
        await update.message.reply_text(
            "Оберіть заклад для цього адміна:",
            reply_markup=ReplyKeyboardMarkup(
                [[loc] for loc in LOCATIONS] + [["❌ Скасувати"]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
        return SR_LOCATION
    elif "Головний адмін" in text:
        context.user_data["sr_role"] = "superadmin"
        context.user_data["sr_location"] = ""
        return await _ask_role_confirm(update, context)
    else:
        await update.message.reply_text("Оберіть роль зі списку:")
        return SR_ROLE


async def set_role_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    if text not in LOCATIONS:
        await update.message.reply_text("Оберіть заклад зі списку:")
        return SR_LOCATION
    context.user_data["sr_location"] = text
    return await _ask_role_confirm(update, context)


async def _ask_role_confirm(update, context):
    w = context.user_data["sr_worker"]
    role = context.user_data["sr_role"]
    loc = context.user_data.get("sr_location", "")
    role_label = "Адмін закладу" if role == "location_admin" else "Головний адмін"
    loc_label = f" — {loc}" if loc else ""
    await update.message.reply_text(
        f"Призначити роль?\n\n"
        f"👤 {w['name']}\n"
        f"🎯 {role_label}{loc_label}",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Так, призначити"], ["❌ Скасувати"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return SR_CONFIRM


async def set_role_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Так" in update.message.text:
        w = context.user_data["sr_worker"]
        role = context.user_data["sr_role"]
        loc = context.user_data.get("sr_location", "")
        db.set_role(int(w["telegram_id"]), role, loc)
        role_label = "Адмін закладу" if role == "location_admin" else "Головний адмін"
        loc_label = f" — {loc}" if loc else ""
        await update.message.reply_text(
            f"✅ Готово!\n{w['name']} — {role_label}{loc_label}",
            reply_markup=ReplyKeyboardRemove()
        )
        try:
            role_msg = {
                "location_admin": f"🔷 Вам призначено роль Адміна закладу «{loc}».",
                "superadmin": "🔶 Вам призначено роль Головного адміна.",
            }.get(role, "")
            if role_msg:
                await context.bot.send_message(
                    chat_id=int(w["telegram_id"]),
                    text=role_msg + "\nНапишіть /start щоб побачити нові команди."
                )
        except Exception:
            pass
    else:
        await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── /unset_role ───────────────────────────────────────────────────────────────

async def unset_role_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_owner(tid):
        await update.message.reply_text("⛔ Тільки власник може забирати ролі.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Введіть ім'я або ID користувача для зняття ролі:",
        reply_markup=ReplyKeyboardRemove()
    )
    return UR_USER


async def unset_role_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        uid = int(text)
        w = db.get_worker(uid)
    except ValueError:
        results = db.search_workers(text)
        w = results[0] if len(results) == 1 else None
        if not w:
            await update.message.reply_text("❌ Не знайдено або знайдено кілька. Уточніть:")
            return UR_USER

    role = db.get_role(int(w["telegram_id"]))
    if not role:
        await update.message.reply_text(f"ℹ️ У {w['name']} немає ролі.")
        return ConversationHandler.END

    context.user_data["ur_worker"] = w
    context.user_data["ur_role"] = role
    await update.message.reply_text(
        f"Зняти роль?\n\n"
        f"👤 {w['name']}\n"
        f"Роль: {role['role']}" + (f" — {role['location']}" if role.get("location") else ""),
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Так, зняти роль"], ["❌ Скасувати"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return UR_CONFIRM


async def unset_role_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Так" in update.message.text:
        w = context.user_data["ur_worker"]
        db.remove_role(int(w["telegram_id"]))
        await update.message.reply_text(
            f"✅ Роль {w['name']} знято.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── ConversationHandlers ──────────────────────────────────────────────────────

def set_role_conv():
    return ConversationHandler(
        entry_points=[CommandHandler("set_role", set_role_start)],
        states={
            SR_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_role_user)],
            SR_USER + 10: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_role_select)],
            SR_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_role_role)],
            SR_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_role_location)],
            SR_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_role_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


def unset_role_conv():
    return ConversationHandler(
        entry_points=[CommandHandler("unset_role", unset_role_start)],
        states={
            UR_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, unset_role_user)],
            UR_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, unset_role_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
