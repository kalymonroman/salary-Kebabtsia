"""
Хендлери для адміна закладу, головного адміна:
  - /day — перегляд дня з таблицею унів/премій
  - /stats — статистика закладу
  - /report — зведений звіт по мережі (тільки superadmin+)
  - /workers — список та управління працівниками
  - /add_worker, /remove_worker
"""
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from sheets import SheetsManager
from calc import LOCATIONS, UNIVERSAL_BONUS, DAILY_BONUS

db = SheetsManager()

# Стани
(AW_NAME, AW_ID, AW_CONFIRM) = range(40, 43)
(RW_SEARCH, RW_SELECT, RW_CONFIRM) = range(50, 53)

MONTHS_UA = [
    "", "січень", "лютий", "березень", "квітень", "травень", "червень",
    "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"
]


def _now():
    return datetime.now()


def _fmt(val):
    return f"{float(val):,.0f}".replace(",", " ")


def _check_admin(tid):
    return db.is_admin_or_above(tid)


def _get_location_for(tid):
    """Повертає заклад для перегляду: для location_admin — свій, для вищих — None (всі)."""
    r = db.get_role(tid)
    if r and r["role"] == "location_admin":
        return r.get("location", "")
    return None


# ── /day — перегляд дня ───────────────────────────────────────────────────────

async def day_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not _check_admin(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return

    args = context.args
    today = _now().strftime("%d.%m.%Y")
    date = args[0] if args else today
    # Нормалізація дати
    parts = date.split(".")
    if len(parts) == 2:
        date = f"{parts[0].zfill(2)}.{parts[1].zfill(2)}.{_now().year}"

    loc_filter = _get_location_for(tid)

    if loc_filter:
        entries = db.get_day_entries(loc_filter, date)
        loc_label = loc_filter
    else:
        # Для superadmin/owner — якщо передали заклад другим аргументом
        if len(args) >= 2:
            loc_filter = " ".join(args[1:])
            entries = db.get_day_entries(loc_filter, date)
            loc_label = loc_filter
        else:
            # Показати список закладів
            kb = ReplyKeyboardMarkup(
                [[f"/day {date} {loc}"] for loc in LOCATIONS],
                resize_keyboard=True, one_time_keyboard=True
            )
            await update.message.reply_text(
                f"📅 {date}\nОберіть заклад:", reply_markup=kb
            )
            return

    if not entries:
        await update.message.reply_text(
            f"📅 {date} — {loc_label}\n📭 Записів немає."
        )
        return

    lines = [f"📅 *{date}* — {loc_label}\nПрацівників: {len(entries)}\n"]
    buttons = []

    for r in entries:
        name = r["name"]
        tid_w = str(r["telegram_id"])
        univ = float(r.get("universal", 0)) > 0
        bonus = float(r.get("bonus", 0)) > 0
        u_icon = "✅" if univ else "⬜"
        b_icon = "✅" if bonus else "⬜"
        lines.append(
            f"👤 {name}\n"
            f"  ⏱ {r['hours']}г | {_fmt(r['base_pay'])} грн\n"
            f"  🔧 Унів {u_icon}  |  ⭐ Премія {b_icon}"
        )
        buttons.append([
            InlineKeyboardButton(
                f"{'🔧✅' if univ else '🔧⬜'} {name[:12]}",
                callback_data=f"univ:{tid_w}:{date}:{int(not univ)}"
            ),
            InlineKeyboardButton(
                f"{'⭐✅' if bonus else '⭐⬜'}",
                callback_data=f"bonus:{tid_w}:{date}:{int(not bonus)}"
            ),
        ])

    lines.append(f"\nНатисніть кнопку щоб перемкнути унів/премію:")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid_admin = query.from_user.id
    if not _check_admin(tid_admin):
        await query.answer("⛔ Немає доступу", show_alert=True)
        return

    action, tid_w, date, val = query.data.split(":")
    val = int(val)

    entry = db.get_entry_by_date(int(tid_w), date)
    if not entry:
        await query.answer("Запис не знайдено", show_alert=True)
        return

    current_univ = float(entry.get("universal", 0))
    current_bonus = float(entry.get("bonus", 0))

    if action == "univ":
        new_univ = UNIVERSAL_BONUS if val else 0
        db.set_universal_bonus(int(tid_w), date, new_univ, current_bonus)
        icon = "✅" if val else "⬜"
        await query.answer(f"🔧 Універсал {'нараховано' if val else 'знято'}")
    else:
        new_bonus = DAILY_BONUS if val else 0
        db.set_universal_bonus(int(tid_w), date, current_univ, new_bonus)
        icon = "✅" if val else "⬜"
        await query.answer(f"⭐ Премія {'нарахована' if val else 'знята'}")

    # Оновлюємо кнопки
    keyboard = query.message.reply_markup.inline_keyboard
    new_keyboard = []
    for row in keyboard:
        new_row = []
        for btn in row:
            data = btn.callback_data
            if data == query.data:
                # Перемикаємо
                if action == "univ":
                    name_part = btn.text.split(" ", 1)[1] if " " in btn.text else ""
                    new_text = f"{'🔧✅' if val else '🔧⬜'} {name_part}"
                else:
                    new_text = f"{'⭐✅' if val else '⭐⬜'}"
                new_row.append(InlineKeyboardButton(new_text, callback_data=f"{action}:{tid_w}:{date}:{int(not val)}"))
            else:
                new_row.append(btn)
        new_keyboard.append(new_row)
    await query.edit_message_reply_markup(InlineKeyboardMarkup(new_keyboard))


# ── /stats — статистика закладу ───────────────────────────────────────────────

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not _check_admin(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return

    now = _now()
    args = context.args
    loc_filter = _get_location_for(tid)

    if not loc_filter:
        # superadmin/owner — треба вказати заклад
        if args:
            loc_filter = " ".join(args)
        else:
            kb = [[f"/stats {loc}"] for loc in LOCATIONS]
            await update.message.reply_text(
                "Оберіть заклад:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
            )
            return

    entries = db.get_location_entries(loc_filter, now.month, now.year)
    if not entries:
        await update.message.reply_text(f"📭 Даних по '{loc_filter}' немає.")
        return

    summary = db.summarize_workers(entries)
    total_base = sum(s["base_pay"] for s in summary.values())
    total_rate_b = sum(s["rate_bonus"] for s in summary.values())
    total_univ = sum(s["universal"] for s in summary.values())
    total_bonus = sum(s["bonus"] for s in summary.values())
    grand = sum(s["total"] for s in summary.values())

    lines = [
        f"📊 *{loc_filter}* — {MONTHS_UA[now.month]} {now.year}\n",
        f"1. Погодинна оплата: {_fmt(total_base)} грн",
        f"2. Бонус ставки 1.5: {_fmt(total_rate_b)} грн",
        f"3. Надбавка унів.: {_fmt(total_univ)} грн",
        f"4. Премії: {_fmt(total_bonus)} грн",
        f"─────────────────",
        f"💵 Разом: *{_fmt(grand)} грн*\n",
        f"Прац.: {len(summary)} | Год.: {sum(s['hours'] for s in summary.values()):.1f}\n",
        "По працівниках:"
    ]
    for s in sorted(summary.values(), key=lambda x: x["name"]):
        lines.append(
            f"  👤 {s['name']}: {s['days']}дн | {s['hours']}г | *{_fmt(s['total'])} грн*"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /report — зведений звіт по мережі ────────────────────────────────────────

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.is_superadmin_or_above(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return

    now = _now()
    entries = db.get_all_entries(now.month, now.year)
    if not entries:
        await update.message.reply_text("📭 Даних за цей місяць немає.")
        return

    by_loc = db.summarize_locations(entries)
    grand = {"base_pay": 0, "rate_bonus": 0, "universal": 0, "bonus": 0, "total": 0}

    lines = [f"📊 *Мережа* — {MONTHS_UA[now.month]} {now.year}\n"]
    for loc in LOCATIONS:
        if loc not in by_loc:
            continue
        s = by_loc[loc]
        for k in grand:
            grand[k] += s[k]
        lines.append(
            f"📍 *{loc}*\n"
            f"  Прац.: {s['worker_count']} | Год.: {s['hours']:.1f}\n"
            f"  База: {_fmt(s['base_pay'])} | Бонус 1.5: {_fmt(s['rate_bonus'])}\n"
            f"  Унів.: +{_fmt(s['universal'])} | Премії: +{_fmt(s['bonus'])}\n"
            f"  💵 {_fmt(s['total'])} грн"
        )

    lines += [
        f"\n─────────────────",
        f"1. Погодинна: {_fmt(grand['base_pay'])} грн",
        f"2. Бонус 1.5: {_fmt(grand['rate_bonus'])} грн",
        f"3. Унів.: +{_fmt(grand['universal'])} грн",
        f"4. Премії: +{_fmt(grand['bonus'])} грн",
        f"💵 *Разом: {_fmt(grand['total'])} грн*",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def worker_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фільтр по конкретному працівнику для superadmin/owner."""
    tid = update.effective_user.id
    if not db.is_superadmin_or_above(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "Використання: /worker_report Ім'я\nНаприклад: /worker_report Олена"
        )
        return
    query = " ".join(args)
    workers = db.search_workers(query)
    if not workers:
        await update.message.reply_text(f"Не знайдено працівника '{query}'")
        return

    now = _now()
    lines = []
    for w in workers:
        tid_w = int(w["telegram_id"])
        entries = db.get_worker_entries(tid_w, now.month, now.year)
        if not entries:
            continue
        by_loc = {}
        for e in entries:
            loc = e.get("location", "?")
            if loc not in by_loc:
                by_loc[loc] = []
            by_loc[loc].append(e)

        total = sum(float(e["total"]) for e in entries)
        hours = sum(float(e["hours"]) for e in entries)
        base = sum(float(e["base_pay"]) for e in entries)
        rate_b = sum(float(e.get("rate_bonus", 0)) for e in entries)
        univ = sum(float(e.get("universal", 0)) for e in entries)
        bonus = sum(float(e.get("bonus", 0)) for e in entries)

        lines.append(f"👤 *{w['name']}* — {MONTHS_UA[now.month]} {now.year}")
        lines.append(f"Днів: {len(entries)} | Год.: {hours:.1f}")
        lines.append(f"1. Погодинна: {_fmt(base)} грн")
        lines.append(f"2. Бонус 1.5: {_fmt(rate_b)} грн")
        lines.append(f"3. Унів.: +{_fmt(univ)} грн")
        lines.append(f"4. Премії: +{_fmt(bonus)} грн")
        lines.append(f"💵 *Разом: {_fmt(total)} грн*\n")
        lines.append("По локаціях:")
        for loc, es in by_loc.items():
            loc_total = sum(float(e["total"]) for e in es)
            lines.append(f"  📍 {loc}: {len(es)}дн | {_fmt(loc_total)} грн")
        lines.append("\nДеталі по днях:")
        for e in entries:
            lines.append(
                f"  {e['date']} | {e['location']} | {e['hours']}г | {_fmt(e['total'])}₴"
            )

    if not lines:
        await update.message.reply_text(f"📭 Даних за {MONTHS_UA[now.month]} немає.")
        return
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /workers — список ─────────────────────────────────────────────────────────

async def list_workers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.can_manage_workers(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return
    workers = db.get_all_workers()
    if not workers:
        await update.message.reply_text("📭 Список порожній.")
        return
    lines = ["👥 *Список працівників:*\n"]
    for i, w in enumerate(workers, 1):
        lines.append(f"{i}. {w['name']} (ID: {w['telegram_id']})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /add_worker ───────────────────────────────────────────────────────────────

async def add_worker_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id
    if not db.can_manage_workers(tid):
        await update.message.reply_text("⛔ Немає доступу.")
        return ConversationHandler.END
    await update.message.reply_text(
        "Введіть ім'я нового працівника:", reply_markup=ReplyKeyboardRemove()
    )
    return AW_NAME


async def add_worker_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["aw_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Введіть Telegram ID працівника.\n\n"
        "_Попросіть його написати @userinfobot — він покаже ID_",
        parse_mode="Markdown"
    )
    return AW_ID


async def add_worker_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ ID має бути числом. Спробуйте ще раз:")
        return AW_ID
    if db.get_worker(new_id):
        await update.message.reply_text("⚠️ Такий ID вже є в системі.")
        return ConversationHandler.END
    context.user_data["aw_id"] = new_id
    await update.message.reply_text(
        f"Додати працівника?\n\n"
        f"👤 {context.user_data['aw_name']}\n"
        f"🆔 {new_id}",
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Так, додати"], ["❌ Скасувати"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return AW_CONFIRM


async def add_worker_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Так" in update.message.text:
        name = context.user_data["aw_name"]
        new_id = context.user_data["aw_id"]
        db.add_worker(new_id, name)
        await update.message.reply_text(
            f"✅ {name} доданий до системи.\n"
            f"Він може написати боту /start щоб розпочати.",
            reply_markup=ReplyKeyboardRemove()
        )
        # Спробуємо надіслати сповіщення
        try:
            await context.bot.send_message(
                chat_id=new_id,
                text=f"👋 Вас додано до системи обліку зарплати!\n\nНатисніть /start щоб розпочати."
            )
        except Exception:
            pass
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
        "Введіть ім'я або частину імені працівника:",
        reply_markup=ReplyKeyboardRemove()
    )
    return RW_SEARCH


async def remove_worker_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = db.search_workers(update.message.text.strip())
    if not results:
        await update.message.reply_text("❌ Нікого не знайдено. Спробуйте ще раз:")
        return RW_SEARCH
    if len(results) == 1:
        context.user_data["rw_worker"] = results[0]
        return await _ask_remove_confirm(update, context)
    context.user_data["rw_results"] = results
    lines = ["Знайдено кілька:\n"]
    for i, w in enumerate(results, 1):
        lines.append(f"{i}. {w['name']}")
    lines.append("\nВведіть номер:")
    await update.message.reply_text("\n".join(lines))
    return RW_SELECT


async def remove_worker_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(update.message.text.strip()) - 1
        worker = context.user_data["rw_results"][idx]
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Введіть коректний номер:")
        return RW_SELECT
    context.user_data["rw_worker"] = worker
    return await _ask_remove_confirm(update, context)


async def _ask_remove_confirm(update, context):
    w = context.user_data["rw_worker"]
    await update.message.reply_text(
        f"Видалити доступ?\n\n"
        f"👤 {w['name']}\n\n"
        f"⚠️ Всі записи залишаться в таблиці.",
        reply_markup=ReplyKeyboardMarkup(
            [["🗑 Так, видалити доступ"], ["❌ Скасувати"]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return RW_CONFIRM


async def remove_worker_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Так" in update.message.text:
        w = context.user_data["rw_worker"]
        db.remove_worker(int(w["telegram_id"]))
        await update.message.reply_text(
            f"✅ Доступ {w['name']} видалено. Дані збережено в таблиці.",
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
            AW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_worker_name)],
            AW_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_worker_id)],
            AW_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_worker_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


def remove_worker_conv():
    return ConversationHandler(
        entry_points=[CommandHandler("remove_worker", remove_worker_start)],
        states={
            RW_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_worker_search)],
            RW_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_worker_select)],
            RW_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_worker_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
