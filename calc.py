LOCATIONS = [
    "Крива Липа", "Валова", "Spartak", "New Point", "Вокзал",
    "Victoria Gardens", "Княгині Ольги", "УПА", "Сихів", "Шувар",
    "Левандівка", "Рясне", "Forum", "Семицвіт"
]
ROLES = {
    "owner": "Власник",
    "superadmin": "Головний адмін",
    "location_admin": "Адмін закладу",
    "worker": "Працівник",
}
UNIVERSAL_BONUS = 150
DAILY_BONUS = 200

BASE_HOURLY = 110
RATE15_ADDON = 20          # +20 грн/год для ставки 1.5 при виторгу >= 40 000
RATE15_MIN_REVENUE = 40000

BONUS_TIERS = [
    (95000, 40),
    (85000, 35),
    (70000, 30),
    (55000, 25),
    (45000, 20),
    (40000, 15),
    (30000, 10),
    (0,      0),
]

def get_revenue_bonus(revenue: float) -> int:
    for threshold, bonus in BONUS_TIERS:
        if revenue >= threshold:
            return bonus
    return 0

def get_rate15_addon(rate: float, revenue: float) -> int:
    return RATE15_ADDON if rate == 1.5 and revenue >= RATE15_MIN_REVENUE else 0

def calculate(hours: float, rate: float, revenue: float,
              universal: bool = False, bonus: bool = False) -> dict:
    addon15     = get_rate15_addon(rate, revenue)
    rev_bonus   = get_revenue_bonus(revenue)
    hourly      = BASE_HOURLY + addon15 + rev_bonus

    base_pay    = hours * BASE_HOURLY
    addon_pay   = hours * addon15
    rate_bonus  = hours * rev_bonus
    univ_amount  = UNIVERSAL_BONUS if universal else 0
    bonus_amount = DAILY_BONUS if bonus else 0
    total = base_pay + addon_pay + rate_bonus + univ_amount + bonus_amount

    return {
        "hourly_rate": hourly,
        "base_hourly": BASE_HOURLY,
        "addon15":     addon15,
        "rev_bonus":   rev_bonus,
        "base_pay":    round(base_pay, 2),
        "addon_pay":   round(addon_pay, 2),
        "rate_bonus":  round(rate_bonus, 2),
        "universal":   round(univ_amount, 2),
        "bonus":       round(bonus_amount, 2),
        "total":       round(total, 2),
    }

def format_result(calc: dict, date: str, location: str,
                  hours: float, rate: float, revenue: float) -> str:
    base_h  = calc["base_hourly"]
    addon15 = calc["addon15"]
    rev_b   = calc["rev_bonus"]

    parts = [str(base_h)]
    if addon15: parts.append(str(addon15))
    if rev_b:   parts.append(str(rev_b))
    rate_line = " + ".join(parts) + f" = {calc['hourly_rate']} грн/год"

    lines = [
        f"✅ Записано!\n",
        f"📍 {location}",
        f"📅 {date}",
        f"⏱ {hours} год | Ставка {rate}",
        f"💵 Виторг: {revenue:,.0f} грн",
        f"📐 {rate_line}\n",
        f"💰 Розрахунок:",
        f"  База ({base_h} × {hours} год): {calc['base_pay']:,.0f} грн",
    ]
    if addon15:
        lines.append(f"  Надбавка 1.5 (+{addon15} × {hours} год): +{calc['addon_pay']:,.0f} грн")
    if rev_b:
        lines.append(f"  Бонус від каси (+{rev_b} × {hours} год): +{calc['rate_bonus']:,.0f} грн")
    if calc["universal"]:
        lines.append(f"  Університал: +{calc['universal']:,.0f} грн")
    if calc["bonus"]:
        lines.append(f"  Премія: +{calc['bonus']:,.0f} грн")
    lines += [
        f"  ─────────────────",
        f"  💵 Разом: {calc['total']:,.0f} грн",
        f"\n📊 Унів. та премію проставляє адмін"
    ]
    return "\n".join(lines)
