"""
Хендлери для працівника v2:
  - Заповнити день (можна двічі — різні заклади)
  - Мої записи
  - Редагувати запис (лише поточний місяць)
  - Додати пропущений день
  - Видалити день (лише поточний місяць)
"""
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ConversationHandler, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from calc import calculate, format_result, LOCATIONS
from sheets import SheetsManager

db = SheetsManager()

(LOC, RATE, HOURS, REVENUE) = range(4)
(EDIT_DATE, EDIT_PICK, EDIT_FIELD, EDIT_VALUE) = range(10, 14)
(ADD_DATE, ADD_LOC, ADD_RATE, ADD_HOURS, ADD_REVENUE) = range(20, 25)
(DEL_DATE, DEL_PICK, DEL_CONFIRM) = range(30, 33)

MAIN_KB = ReplyKeyboardMarkup([
    ["📝 Заповнити день", "📊 Мої записи"],
    ["➕ Додати день", "🗑 Видалити день"],
    ["✏️ Змінити запис"]
], resize_keyboard=True)

LOC_KB = ReplyKeyboardMarkup(
    [[loc] for loc in LOCATIONS], resize_keyboard=True, one_time_keyboard=True
)

RATE_KB = ReplyKeyboardMarkup([
    ["Ставка 1 — 110 грн/год + бонус"],
    ["Ставка 1.5 — 110 грн/год + більший бонус"]
], resize_keyboard=True, one_time_keyboard=True)


def _today():
    return datetime.now().strftime("%d.%m.%Y")


def _this_month_year():
    n = datetime.now()
    return n.month, n.year


def _validate_date_current_month(text: str):
    now = datetime.now()
    parts = text.strip().split(".")
    if len(parts) == 2:
        text = f"{parts[0].zfill(2)}.{parts[1].zfill(2)}.{now.year}"
    try:
        d = datetime.strptime(text, "%d.%m.%Y")
        if d.month == now.month and d.year == now.year:
            return d.strftime("%d.%m.%Y")
    except ValueError:
        pass
    return None


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    worker = db.get_worker(tid)
    role = db.get_role(tid)

    if worker:
        await update.message.reply_text(
            f"👋 Привіт, {worker['name']}!", reply_markup=MAIN_KB
        )
    elif role and role["role"] in ("owner", "superadmin", "location_admin"):
        loc = role.get("location", "")
        role_name = {"owner": "Власник", "superadmin": "Головний адмін",
                     "location_admin": f"Адмін — {loc}"}.get(role["role"], "")
        await update.message.reply_text(
            f"👋 Привіт! Ваша роль: {role_name}\n\n"
            f"Команди:\n"
            f"/workers — список працівників\n"
            f"/add_worker — додати працівника\n"
            f"/day — перегляд дня\n"
            f"/stats — статистика закладу\n"
            + ("/report — зведений звіт\n/access — доступи\n"
               if role["role"] in ("owner", "superadmin") else "")
        )
    else:
        await update.message.reply_text(
            "⛔ Вас немає в системі.\nЗверніться до адміністратора."
        )


# ── Заповнити день ────────────────────────────────────────────────────────────

async def fill_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.get_worker(tid):
        await update.message.reply_text("⛔ Вас немає в системі.")
        return ConversationHandler.END
    context.user_data["date"] = _today()
    await update.message.reply_text(
        f"📅 {_today()}\n\nОберіть заклад:", reply_markup=LOC_KB
    )
    return LOC


async def fill_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text not in LOCATIONS:
        await update.message.reply_text("Оберіть заклад зі списку:", reply_markup=LOC_KB)
        return LOC
    context.user_data["location"] = update.message.text
    await update.message.reply_text("Оберіть ставку:", reply_markup=RATE_KB)
    return RATE


async def fill_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "1.5" in text:
        context.user_data["rate"] = 1.5
    elif "Ставка 1" in text:
        context.user_data["rate"] = 1.0
    else:
        await update.message.reply_text("Оберіть ставку:", reply_markup=RATE_KB)
        return RATE
    await update.message.reply_text(
        "⏱ Скільки годин відпрацювали?\n_(наприклад: 8 або 7.5)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    return HOURS


async def fill_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        h = float(update.message.text.replace(",", "."))
        if not (0 < h <= 24):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введіть коректну кількість годин (наприклад: 8 або 7.5)")
        return HOURS
    context.user_data["hours"] = h
    await update.message.reply_text("💰 Введіть виторг закладу за сьогодні (грн):")
    return REVENUE


async def fill_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rev = float(update.message.text.replace(",", ".").replace(" ", ""))
        if rev < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введіть суму виторгу (наприклад: 47500)")
        return REVENUE

    tid = update.effective_user.id
    worker = db.get_worker(tid)
    ud = context.user_data
    calc = calculate(ud["hours"], ud["rate"], rev)

    db.save_entry(
        telegram_id=tid, name=worker["name"],
        date=ud["date"], location=ud["location"],
        hours=ud["hours"], rate=ud["rate"], revenue=rev,
        hourly_rate=calc["hourly_rate"], base_pay=calc["base_pay"],
        rate_bonus=calc["rate_bonus"],
    )

    await update.message.reply_text(
        format_result(calc, ud["date"], ud["location"], ud["hours"], ud["rate"], rev),
        reply_markup=MAIN_KB
    )
    return ConversationHandler.END


# ── Мої записи ────────────────────────────────────────────────────────────────

async def my_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    worker = db.get_worker(tid)
    if not worker:
        await update.message.reply_text("⛔ Вас немає в системі.")
        return
    m, y = _this_month_year()
    entries = db.get_worker_entries(tid, m, y)
    if not entries:
        await update.message.reply_text("📭 За цей місяць записів ще немає.", reply_markup=MAIN_KB)
        return

    total = sum(float(r["total"]) for r in entries)
    hours = sum(float(r["hours"]) for r in entries)
    now = datetime.now()

    lines = [f"📊 *{worker['name']}* — {now.strftime('%B %Y')}\n"]
    for r in entries:
        univ = "🔧" if float(r.get("universal", 0)) > 0 else ""
        bon = "⭐" if float(r.get("bonus", 0)) > 0 else ""
        lines.append(
            f"  {r['date']} | {r['location']} | {r['hours']}г | "
            f"{float(r['total']):,.0f}₴ {univ}{bon}"
        )
    lines.append(f"\n⏱ Годин: {hours:.1f}")
    lines.append(f"💵 Разом: *{total:,.0f} грн*")

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_KB
    )


# ── Редагувати запис (лише поточний місяць) ───────────────────────────────────

EDIT_FIELDS_KB = ReplyKeyboardMarkup([
    ["Змінити заклад", "Змінити ставку"],
    ["Змінити години", "Змінити виторг"],
    ["❌ Скасувати"]
], resize_keyboard=True, one_time_keyboard=True)


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.get_worker(tid):
        await update.message.reply_text("⛔ Вас немає в системі.")
        return ConversationHandler.END
    now = datetime.now()
    await update.message.reply_text(
        f"Введіть дату запису для зміни:\n_(лише {now.strftime('%B %Y')}, наприклад: 05.05)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    return EDIT_DATE


async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = _validate_date_current_month(update.message.text)
    if not date:
        now = datetime.now()
        await update.message.reply_text(
            f"❌ Дата має бути в межах {now.strftime('%B %Y')}"
        )
        return EDIT_DATE
    tid = update.effective_user.id
    entries = db.get_entries_by_date(tid, date)
    if not entries:
        await update.message.reply_text(f"❌ Записів за {date} не знайдено.", reply_markup=MAIN_KB)
        return ConversationHandler.END
    if len(entries) == 1:
        context.user_data["edit_entry"] = entries[0]
        context.user_data["edit_date"] = date
        return await _ask_edit_field(update, context)
    # Кілька записів за цей день
    context.user_data["edit_date"] = date
    context.user_data["edit_entries"] = entries
    lines = [f"За {date} знайдено {len(entries)} записи:\n"]
    for i, e in enumerate(entries, 1):
        lines.append(f"{i}. {e['location']} | {e['hours']}г | {float(e['total']):,.0f}₴")
    lines.append("\nВведіть номер запису:")
    await update.message.reply_text("\n".join(lines))
    return EDIT_PICK


async def edit_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(update.message.text.strip()) - 1
        entry = context.user_data["edit_entries"][idx]
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Введіть коректний номер:")
        return EDIT_PICK
    context.user_data["edit_entry"] = entry
    return await _ask_edit_field(update, context)


async def _ask_edit_field(update, context):
    entry = context.user_data["edit_entry"]
    await update.message.reply_text(
        f"📅 {entry['date']} — {entry['location']}\n"
        f"⏱ {entry['hours']} год | Ставка {entry['rate']} | Виторг {float(entry['revenue']):,.0f}\n\n"
        f"Що змінити?",
        reply_markup=EDIT_FIELDS_KB
    )
    return EDIT_FIELD


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Скасувати":
        await update.message.reply_text("Скасовано.", reply_markup=MAIN_KB)
        return ConversationHandler.END
    field_map = {
        "Змінити заклад": "location",
        "Змінити ставку": "rate",
        "Змінити години": "hours",
        "Змінити виторг": "revenue",
    }
    if text not in field_map:
        await update.message.reply_text("Оберіть поле:", reply_markup=EDIT_FIELDS_KB)
        return EDIT_FIELD
    context.user_data["edit_field"] = field_map[text]
    prompts = {
        "location": ("Оберіть новий заклад:", LOC_KB),
        "rate": ("Оберіть нову ставку:", RATE_KB),
        "hours": ("Введіть нову кількість годин:", ReplyKeyboardRemove()),
        "revenue": ("Введіть новий виторг (грн):", ReplyKeyboardRemove()),
    }
    msg, kb = prompts[field_map[text]]
    await update.message.reply_text(msg, reply_markup=kb)
    return EDIT_VALUE


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data["edit_field"]
    text = update.message.text
    entry = context.user_data["edit_entry"]

    if field == "location":
        if text not in LOCATIONS:
            await update.message.reply_text("Оберіть зі списку:", reply_markup=LOC_KB)
            return EDIT_VALUE
        value = text
    elif field == "rate":
        value = 1.5 if "1.5" in text else 1.0
    elif field in ("hours", "revenue"):
        try:
            value = float(text.replace(",", ".").replace(" ", ""))
            if value <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Введіть коректне число:")
            return EDIT_VALUE
    else:
        value = text

    row_id = entry.get("row_id")
    db.update_entry_by_row(row_id, field, value)
    updated = db.get_entry_by_row(row_id)
    await update.message.reply_text(
        f"✅ Оновлено!\n\n"
        f"📅 {updated['date']} — {updated['location']}\n"
        f"⏱ {updated['hours']} год | Ставка {updated['rate']}\n"
        f"💵 {float(updated['total']):,.0f} грн",
        reply_markup=MAIN_KB
    )
    return ConversationHandler.END


# ── Додати пропущений день ────────────────────────────────────────────────────

async def add_day_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.get_worker(tid):
        await update.message.reply_text("⛔ Вас немає в системі.")
        return ConversationHandler.END
    now = datetime.now()
    await update.message.reply_text(
        f"Введіть дату яку хочете додати:\n_(лише {now.strftime('%B %Y')}, наприклад: 10.05)_",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    return ADD_DATE


async def add_day_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = _validate_date_current_month(update.message.text)
    if not date:
        now = datetime.now()
        await update.message.reply_text(f"❌ Дата має бути в межах {now.strftime('%B %Y')}")
        return ADD_DATE
    context.user_data["date"] = date
    await update.message.reply_text(f"📅 {date}\n\nОберіть заклад:", reply_markup=LOC_KB)
    return ADD_LOC


async def add_day_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text not in LOCATIONS:
        await update.message.reply_text("Оберіть зі списку:", reply_markup=LOC_KB)
        return ADD_LOC
    context.user_data["location"] = update.message.text
    await update.message.reply_text("Оберіть ставку:", reply_markup=RATE_KB)
    return ADD_RATE


async def add_day_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "1.5" in text:
        context.user_data["rate"] = 1.5
    elif "Ставка 1" in text:
        context.user_data["rate"] = 1.0
    else:
        await update.message.reply_text("Оберіть ставку:", reply_markup=RATE_KB)
        return ADD_RATE
    await update.message.reply_text("⏱ Скільки годин?", reply_markup=ReplyKeyboardRemove())
    return ADD_HOURS


async def add_day_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        h = float(update.message.text.replace(",", "."))
        if not (0 < h <= 24):
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введіть коректну кількість годин:")
        return ADD_HOURS
    context.user_data["hours"] = h
    await update.message.reply_text("💰 Виторг закладу (грн):")
    return ADD_REVENUE


async def add_day_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rev = float(update.message.text.replace(",", ".").replace(" ", ""))
        if rev < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введіть суму виторгу:")
        return ADD_REVENUE
    tid = update.effective_user.id
    worker = db.get_worker(tid)
    ud = context.user_data
    calc = calculate(ud["hours"], ud["rate"], rev)
    db.save_entry(
        telegram_id=tid, name=worker["name"],
        date=ud["date"], location=ud["location"],
        hours=ud["hours"], rate=ud["rate"], revenue=rev,
        hourly_rate=calc["hourly_rate"], base_pay=calc["base_pay"],
        rate_bonus=calc["rate_bonus"],
    )
    await update.message.reply_text(
        format_result(calc, ud["date"], ud["location"], ud["hours"], ud["rate"], rev),
        reply_markup=MAIN_KB
    )
    return ConversationHandler.END


# ── Видалити день (лише поточний місяць) ─────────────────────────────────────

async def del_day_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.get_worker(tid):
        await update.message.reply_text("⛔ Вас немає в системі.")
        return ConversationHandler.END
    m, y = _this_month_year()
    entries = db.get_worker_entries(tid, m, y)
    if not entries:
        await update.message.reply_text("📭 Немає записів для видалення.", reply_markup=MAIN_KB)
        return ConversationHandler.END
    now = datetime.now()
    lines = [f"Ваші записи за {now.strftime('%B %Y')}:\n"]
    for r in entries:
        lines.append(f"  {r['date']} | {r['location']} | {r['hours']}г | {float(r['total']):,.0f}₴")
    lines.append("\nВведіть дату для видалення (наприклад: 02.05):")
    await update.message.reply_text("\n".join(lines), reply_markup=ReplyKeyboardRemove())
    return DEL_DATE


async def del_day_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = _validate_date_current_month(update.message.text)
    if not date:
        now = datetime.now()
        await update.message.reply_text(f"❌ Дата має бути в межах {now.strftime('%B %Y')}")
        return DEL_DATE
    tid = update.effective_user.id
    entries = db.get_entries_by_date(tid, date)
    if not entries:
        await update.message.reply_text(f"❌ Записів за {date} не знайдено.", reply_markup=MAIN_KB)
        return ConversationHandler.END
    context.user_data["del_date"] = date
    context.user_data["del_entries"] = entries
    if len(entries) == 1:
        context.user_data["del_entry"] = entries[0]
        return await _ask_del_confirm(update, context)
    lines = [f"За {date} знайдено {len(entries)} записи:\n"]
    for i, e in enumerate(entries, 1):
        lines.append(f"{i}. {e['location']} | {e['hours']}г | {float(e['total']):,.0f}₴")
    lines.append("\nВведіть номер для видалення:")
    await update.message.reply_text("\n".join(lines))
    return DEL_PICK


async def del_day_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(update.message.text.strip()) - 1
        entry = context.user_data["del_entries"][idx]
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Введіть коректний номер:")
        return DEL_PICK
    context.user_data["del_entry"] = entry
    return await _ask_del_confirm(update, context)


async def _ask_del_confirm(update, context):
    entry = context.user_data["del_entry"]
    await update.message.reply_text(
        f"Видалити запис?\n\n"
        f"📅 {entry['date']} — {entry['location']}\n"
        f"⏱ {entry['hours']} год | 💵 {float(entry['total']):,.0f} грн",
        reply_markup=ReplyKeyboardMarkup(
            [["🗑 Так, видалити"], ["❌ Скасувати"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return DEL_CONFIRM


async def del_day_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Так" in update.message.text:
        entry = context.user_data["del_entry"]
        db.delete_entry_by_row(entry["row_id"])
        await update.message.reply_text(
            f"✅ Запис за {entry['date']} — {entry['location']} видалено.",
            reply_markup=MAIN_KB
        )
    else:
        await update.message.reply_text("Скасовано.", reply_markup=MAIN_KB)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано.", reply_markup=MAIN_KB)
    return ConversationHandler.END


# ── ConversationHandlers ──────────────────────────────────────────────────────

def fill_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 Заповнити день$"), fill_start)],
        states={
            LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_loc)],
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_rate)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_hours)],
            REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, fill_revenue)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


def edit_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✏️ Змінити запис$"), edit_start)],
        states={
            EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_date)],
            EDIT_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_pick)],
            EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field)],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


def add_day_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Додати день$"), add_day_start)],
        states={
            ADD_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_date)],
            ADD_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_loc)],
            ADD_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_rate)],
            ADD_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_hours)],
            ADD_REVENUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_day_revenue)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


def del_day_conv():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑 Видалити день$"), del_day_start)],
        states={
            DEL_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_day_date)],
            DEL_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_day_pick)],
            DEL_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_day_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
