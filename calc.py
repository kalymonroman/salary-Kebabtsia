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
RATE1_BASE = 110
RATE15_BASE = 130

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


def get_hourly_rate(rate: float, revenue: float) -> int:
    base = RATE15_BASE if rate == 1.5 else RATE1_BASE
    return base + get_revenue_bonus(revenue)


def calculate(hours: float, rate: float, revenue: float,
              universal: bool = False, bonus: bool = False) -> dict:
    base_hourly = RATE15_BASE if rate == 1.5 else RATE1_BASE
    rev_bonus = get_revenue_bonus(revenue)
    hourly = base_hourly + rev_bonus

    base_pay = hours * base_hourly
    rate_bonus = hours * rev_bonus
    univ_amount = UNIVERSAL_BONUS if universal else 0
    bonus_amount = DAILY_BONUS if bonus else 0
    total = base_pay + rate_bonus + univ_amount + bonus_amount

    return {
        "hourly_rate": hourly,
        "base_hourly": base_hourly,
        "rev_bonus": rev_bonus,
        "base_pay": round(base_pay, 2),
        "rate_bonus": round(rate_bonus, 2),
        "universal": round(univ_amount, 2),
        "bonus": round(bonus_amount, 2),
        "total": round(total, 2),
    }


def format_result(calc: dict, date: str, location: str,
                  hours: float, rate: float, revenue: float) -> str:
    rev_bonus = calc["rev_bonus"]
    base_h = calc["base_hourly"]

    lines = [
        f"✅ Записано!\n",
        f"📍 {location}",
        f"📅 {date}",
        f"⏱ {hours} год | Ставка {rate}",
        f"💵 Виторг: {revenue:,.0f} грн",
        f"📐 {base_h} + {rev_bonus} = {calc['hourly_rate']} грн/год\n",
        f"💰 Розрахунок:",
        f"  База ({base_h} × {hours} год): {calc['base_pay']:,.0f} грн",
    ]
    if rev_bonus > 0:
        lines.append(f"  Бонус від каси (+{rev_bonus} × {hours} год): +{calc['rate_bonus']:,.0f} грн")
    if calc["universal"]:
        lines.append(f"  Універсал: +{calc['universal']:,.0f} грн")
    if calc["bonus"]:
        lines.append(f"  Премія: +{calc['bonus']:,.0f} грн")
    lines.append(f"  ─────────────────")
    lines.append(f"  💵 Разом: {calc['total']:,.0f} грн")
    lines.append(f"\n📊 Унів. та премію проставляє адмін")
    return "\n".join(lines)
