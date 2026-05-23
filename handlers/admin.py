"""
Хендлери для адміна закладу та головного адміна
"""
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ConversationHandler, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from sheets import SheetsManager
from calc import LOCATIONS, UNIVERSAL_BONUS, DAILY_BONUS

db = SheetsManager()

AW_NAME, AW_ID, AW_CONFIRM = range(40, 43)
RW_SEARCH, RW_SELECT, RW_CONFIRM = range(50, 53)

MONTHS_UA = [
    "", "січень", "лютий", "березень", "квітень", "травень", "червень",
    "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"
]


def _now():
    return datetime.now()


def _fmt(val):
    try:
        return f"{float(val):,.0f}".replace(",", " ")
    except (ValueError, TypeError):
        return "0"


def _get_locations_for(tid):
    """
    Повертає список закладів адміна.
    - location_admin з одним закладом  → ["Валова"]
    - location_admin з двома           → ["Валова", "Spartak"]
    - owner/superadmin                 → [] (всі заклади)
    - не адмін                         → None
    """
    if not db.is_admin_or_above(tid):
        return None
    return db.get_admin_locations(tid)


# ── /day ──────────────────────────────────────────────────────────────────────

async def day_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    locations_for_admin = _get_locations_for(tid)

    if locations_for_admin is None:
        await update.message.reply_text("⛔ Немає доступу.")
        return

    args = context.args
    today = _now().strftime("%d.%m.%Y")
    date_arg = None
    loc_arg = None

    if args:
        if "." in args[0]:
            date_arg = args[0]
            if len(args) >= 2:
                loc_arg = " ".join(args[1:])
        else:
            loc_arg = " ".join(args)

    date = date_arg or today
    parts = date.split(".")
    if len(parts) == 2:
        date = f"{parts[0].zfill(2)}.{parts[1].zfill(2)}.{_now().year}"

    # owner/superadmin: locations_for_admin == [] → доступ до всіх
    is_superadmin = (not locations_for_admin) and db.is_admin_or_above(tid)

    if loc_arg:
        # Заклад вказано явно
        target_location = loc_arg
    elif locations_for_admin and len(locations_for_admin) == 1:
        # location_admin з одним закладом — відразу
        target_location = locations_for_admin[0]
    elif locations_for_admin and len(locations_for_admin) > 1:
        # location_admin з кількома закладами — меню вибору
        kb = ReplyKeyboardMarkup(
            [[f"/day {date} {loc}"] for loc in locations_for_admin],
            resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            f"📅 {date}\n🏪 У якому закладі переглянути записи?",
            reply_markup=kb
        )
        return
    elif is_superadmin:
        # superadmin/owner — показує всі локації
        kb = ReplyKeyboardMarkup(
            [[f"/day {date} {loc}"] for loc in LOCATIONS],
            resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            f"📅 {date}\n🏪 Оберіть заклад:",
            reply_markup=kb
        )
        return
    else:
        await update.message.reply_text(
            "Не вдалось визначити заклад.\nСпробуйте: /day 21.05 Валова",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    entries = db.get_day_entries(target_location, date)

    if not entries:
        await update.message.reply_text(
            f"📅 {date} — {target_location}\n📭 Записів немає.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    text = f"📅 {date} — {target_location}\n\n"
    keyboard = []

    for e in entries:
        univ = float(e.get("universal", 0) or 0)
        bonus = float(e.get("bonus", 0) or 0)
        total = float(e.get("total", 0) or 0)
        row_id = e.get("row_id", 0)
        tid_w = e.get("telegram_id", "")

        univ_icon  = "🔧✅" if univ > 0 else "🔧⬜"
        bonus_icon = "⭐✅" if bonus > 0 else "⭐⬜"

        text += f"👤 {e['name']} — {_fmt(total)} грн\n"
        keyboard.append([
            InlineKeyboardButton(
                f"{univ_icon} {e['name']}",
                callback_data=f"univ:{tid_w}:{date}:{0 if univ > 0 else 1}:{row_id}"
            ),
            InlineKeyboardButton(
                bonus_icon,
                callback_data=f"bonus:{tid_w}:{date}:{0 if bonus > 0 else 1}:{row_id}"
            ),
        ])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── toggle callback ───────────────────────────────────────────────────────────

async def toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tid_admin = query.from_user.id
    if not db.is_admin_or_above(tid_admin):
        await query.answer("⛔ Немає доступу", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) < 5:
        await query.answer("Помилка даних", show_alert=True)
        return

    action  = parts[0]
    tid_w   = parts[1]
    date    = parts[2]
    val     = int(parts[3])
    row_id  = int(parts[4])

    entry = db.get_entry_by_row(row_id)
    if not entry:
        await query.answer("Запис не знайдено", show_alert=True)
        return

    current_univ  = float(entry.get("universal", 0) or 0)
    current_bonus = float(entry.get("bonus", 0) or 0)

    if action == "univ":
        new_univ = float(UNIVERSAL_BONUS) if val else 0.0
        db.set_universal_bonus(int(tid_w), date, new_univ, current_bonus, row_id=row_id)
        await query.answer(f"🔧 Університал {'нараховано' if val else 'знято'}")
    else:
        new_bonus = float(DAILY_BONUS) if val else 0.0
        db.set_universal_bonus(int(tid_w), date, current_univ, new_bonus, row_id=row_id)
        await query.answer(f"⭐ Премія {'нарахована' if val else 'знята'}")

    # Оновлюємо кнопки
    keyboard = query.message.reply_markup.inline_keyboard
    new_keyboard = []
    for row in keyboard:
        new_row = []
        for btn in row:
            if btn.callback_data == query.data:
                new_val = int(not val)
                if action == "univ":
                    icon = "🔧✅" if val else "🔧⬜"
                    name_part = btn.text.split(" ", 1)[1] if " " in btn.text else ""
                    new_text = f"{icon} {name_part}"
                else:
                    new_text = "⭐✅" if val else "⭐⬜"
                new_row.append(InlineKeyboardButton(
                    new_text,
                    callback_data=f"{action}:{tid_w}:{date}:{new_val}:{row_id}"
                ))
            else:
                new_row.append(btn)
        new_keyboard.append(new_row)

    try:
        await query.edit_message_reply_markup(InlineKeyboardMarkup(new_keyboard))
    except Exception:
        pass


# ── /stats ────────────────────────────────────────────────────────────────────

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_admin_or_above(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return

    now = _now()
    args = context.args

    # Визначаємо заклад
    locations_for_admin = _get_locations_for(tid)
    is_superadmin = not locations_for_admin and db.is_admin_or_above(tid)

    if args:
        location = " ".join(args)
    elif locations_for_admin and len(locations_for_admin) == 1:
        location = locations_for_admin[0]
    elif locations_for_admin and len(locations_for_admin) > 1:
        locs_str = "\n".join(f"  /stats {loc}" for loc in locations_for_admin)
        await update.message.reply_text(
            f"🏪 У вас кілька закладів. Вкажіть який:\n{locs_str}"
        )
        return
    elif is_superadmin and not args:
        await update.message.reply_text(
            "Вкажіть заклад: /stats Валова\nАбо /report для зведеного звіту по всіх."
        )
        return
    else:
        await update.message.reply_text("Вкажіть заклад: /stats Валова")
        return

    entries = db.get_location_entries(location, now.month, now.year)
    if not entries:
        await update.message.reply_text(
            f"📊 {location} — {MONTHS_UA[now.month]} {now.year}\n📭 Записів немає."
        )
        return

    summary = db.summarize_workers(entries)
    month_label = f"{MONTHS_UA[now.month]} {now.year}"
    lines = [f"📊 {location} — {month_label}\n"]

    total_hours = total_base = total_rb = total_univ = total_bonus = total_all = 0.0

    for tid_w, s in summary.items():
        lines.append(
            f"👤 {s['name']}  ({s['days']} зм / {s['hours']:.1f} год)\n"
            f"   База: {_fmt(s['base_pay'])} грн\n"
            f"   Бонус каси: {_fmt(s['rate_bonus'])} грн\n"
            f"   Університал: {_fmt(s['universal'])} грн\n"
            f"   Премія: {_fmt(s['bonus'])} грн\n"
            f"   ─── Разом: {_fmt(s['total'])} грн\n"
        )
        total_hours += s["hours"]
        total_base  += s["base_pay"]
        total_rb    += s["rate_bonus"]
        total_univ  += s["universal"]
        total_bonus += s["bonus"]
        total_all   += s["total"]

    lines.append(
        f"─────────────────\n"
        f"Всього: {total_hours:.1f} год\n"
        f"База: {_fmt(total_base)} | Каса: {_fmt(total_rb)}\n"
        f"Університал: {_fmt(total_univ)} | Премії: {_fmt(total_bonus)}\n"
        f"💰 Разом: {_fmt(total_all)} грн"
    )
    await update.message.reply_text("\n".join(lines))


# ── /report ───────────────────────────────────────────────────────────────────

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_superadmin_or_above(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return

    now = _now()
    entries = db.get_all_entries(now.month, now.year)
    if not entries:
        await update.message.reply_text(
            f"📋 {MONTHS_UA[now.month]} {now.year}\n📭 Записів немає."
        )
        return

    loc_summary = db.summarize_locations(entries)
    month_label = f"{MONTHS_UA[now.month]} {now.year}"
    lines = [f"📋 Зведений звіт — {month_label}\n"]

    grand_total = 0.0
    for loc in sorted(loc_summary):
        s = loc_summary[loc]
        lines.append(
            f"🏪 {loc}  ({s['days']} зм / {s['hours']:.1f} год)\n"
            f"   База: {_fmt(s['base_pay'])} | Каса: {_fmt(s['rate_bonus'])}\n"
            f"   Університал: {_fmt(s['universal'])} | Премії: {_fmt(s['bonus'])}\n"
            f"   Разом: {_fmt(s['total'])} грн\n"
        )
        grand_total += s["total"]

    lines.append(f"─────────────────\n💰 Загалом по мережі: {_fmt(grand_total)} грн")
    await update.message.reply_text("\n".join(lines))


# ── /worker_report ────────────────────────────────────────────────────────────

async def worker_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_admin_or_above(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return

    if not context.args:
        await update.message.reply_text("Вкажіть ім'я: /worker_report Роман")
        return

    query = " ".join(context.args)
    workers = db.search_workers(query)
    if not workers:
        await update.message.reply_text(f"❌ Не знайдено: {query}")
        return

    worker = workers[0]
    now = _now()
    entries = db.get_worker_entries(worker["telegram_id"], now.month, now.year)

    if not entries:
        await update.message.reply_text(
            f"👤 {worker['name']}\n📭 Записів за {MONTHS_UA[now.month]} немає."
        )
        return

    lines = [f"👤 {worker['name']} — {MONTHS_UA[now.month]} {now.year}\n"]
    total = 0.0
    for e in entries:
        lines.append(
            f"📅 {e['date']}  {e.get('location','')}  {e.get('hours',0)} год\n"
            f"   {_fmt(e.get('base_pay',0))} + {_fmt(e.get('rate_bonus',0))} "
            f"+ {_fmt(e.get('universal',0))} + {_fmt(e.get('bonus',0))} "
            f"= {_fmt(e.get('total',0))} грн"
        )
        total += float(e.get("total", 0) or 0)

    lines.append(f"\n💰 Разом: {_fmt(total)} грн")
    await update.message.reply_text("\n".join(lines))


# ── /workers ──────────────────────────────────────────────────────────────────

async def list_workers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_admin_or_above(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return

    workers = db.get_all_workers()
    if not workers:
        await update.message.reply_text("📭 Список порожній.")
        return

    lines = [f"👥 Працівників: {len(workers)}\n"]
    for w in workers:
        lines.append(f"• {w['name']} (ID: {w['telegram_id']})")
    await update.message.reply_text("\n".join(lines))


# ── /add_worker ───────────────────────────────────────────────────────────────

async def add_worker_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.can_manage_workers(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Введіть ім'я нового працівника:",
        reply_markup=ReplyKeyboardRemove()
    )
    return AW_NAME


async def add_worker_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["aw_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"Ім'я: {context.user_data['aw_name']}\n"
        "Введіть Telegram ID працівника (числовий, дізнатись через @userinfobot):"
    )
    return AW_ID


async def add_worker_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tid_new = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ID має бути числом. Спробуйте ще раз:")
        return AW_ID

    existing = db.get_worker(tid_new)
    if existing:
        await update.message.reply_text(
            f"⚠️ Працівник з ID {tid_new} вже існує: {existing['name']}",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    context.user_data["aw_id"] = tid_new
    kb = ReplyKeyboardMarkup([["✅ Так, додати", "❌ Скасувати"]],
                             resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"Додати працівника?\n👤 {context.user_data['aw_name']} (ID: {tid_new})",
        reply_markup=kb
    )
    return AW_CONFIRM


async def add_worker_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Так" in update.message.text:
        db.add_worker(context.user_data["aw_id"], context.user_data["aw_name"])
        await update.message.reply_text(
            f"✅ {context.user_data['aw_name']} доданий.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── /remove_worker ────────────────────────────────────────────────────────────

async def remove_worker_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.can_manage_workers(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Введіть ім'я або ID працівника для видалення:",
        reply_markup=ReplyKeyboardRemove()
    )
    return RW_SEARCH


async def remove_worker_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        results = [db.get_worker(int(text))]
        results = [r for r in results if r]
    except ValueError:
        results = db.search_workers(text)

    if not results:
        await update.message.reply_text("❌ Не знайдено. Спробуйте ще раз:")
        return RW_SEARCH

    if len(results) == 1:
        context.user_data["rw_worker"] = results[0]
        kb = ReplyKeyboardMarkup([["✅ Так, видалити", "❌ Скасувати"]],
                                 resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            f"Видалити доступ?\n👤 {results[0]['name']} (ID: {results[0]['telegram_id']})",
            reply_markup=kb
        )
        return RW_CONFIRM

    context.user_data["rw_results"] = results
    kb = ReplyKeyboardMarkup(
        [[f"{i}. {r['name']}"] for i, r in enumerate(results, 1)],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("Знайдено кілька — оберіть:", reply_markup=kb)
    return RW_SELECT


async def remove_worker_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    results = context.user_data.get("rw_results", [])
    try:
        idx = int(text.split(".")[0]) - 1
        context.user_data["rw_worker"] = results[idx]
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Оберіть зі списку:")
        return RW_SELECT

    kb = ReplyKeyboardMarkup([["✅ Так, видалити", "❌ Скасувати"]],
                             resize_keyboard=True, one_time_keyboard=True)
    w = context.user_data["rw_worker"]
    await update.message.reply_text(
        f"Видалити доступ?\n👤 {w['name']} (ID: {w['telegram_id']})",
        reply_markup=kb
    )
    return RW_CONFIRM


async def remove_worker_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Так" in update.message.text:
        w = context.user_data["rw_worker"]
        db.remove_worker(w["telegram_id"])
        await update.message.reply_text(
            f"✅ Доступ {w['name']} видалено.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── ConversationHandlers ──────────────────────────────────────────────────────

def add_worker_conv():
    return ConversationHandler(
        entry_points=[CommandHandler("add_worker", add_worker_start)],
        states={
            AW_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_worker_name)],
            AW_ID:      [MessageHandler(filters.TEXT & ~filters.COMMAND, add_worker_id)],
            AW_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_worker_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


def remove_worker_conv():
    return ConversationHandler(
        entry_points=[CommandHandler("remove_worker", remove_worker_start)],
        states={
            RW_SEARCH:  [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_worker_search)],
            RW_SELECT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_worker_select)],
            RW_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_worker_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
