"""
Розрахунок заробітної плати та константи
"""

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

# Бонусна система: (мінімальний виторг, бонус ставка 1, бонус ставка 1.5)
BONUS_TIERS = [
    (95000, 40, 60),
    (85000, 35, 55),
    (70000, 30, 50),
    (55000, 25, 45),
    (45000, 20, 40),
    (40000, 15, 35),
    (30000, 10, 10),
    (0,      0,  0),
]


def get_revenue_bonus(rate: float, revenue: float) -> int:
    """Повертає бонус до погодинної ставки залежно від виторгу і ставки."""
    for threshold, bonus1, bonus15 in BONUS_TIERS:
        if revenue >= threshold:
            return bonus15 if rate == 1.5 else bonus1
    return 0


def get_hourly_rate(rate: float, revenue: float) -> int:
    """Повна погодинна ставка = база 110 + бонус виторгу."""
    return BASE_HOURLY + get_revenue_bonus(rate, revenue)


def calculate(hours: float, rate: float, revenue: float,
              universal: bool = False, bonus: bool = False) -> dict:
    rev_bonus = get_revenue_bonus(rate, revenue)
    hourly = BASE_HOURLY + rev_bonus
    base = hours * BASE_HOURLY
    bonus_revenue_amt = hours * rev_bonus
    univ_amount = UNIVERSAL_BONUS if universal else 0
    bonus_amount = DAILY_BONUS if bonus else 0
    total = base + bonus_revenue_amt + univ_amount + bonus_amount

    return {
        "hourly_rate": hourly,
        "rev_bonus": rev_bonus,
        "base_pay": round(base, 2),
        "rate_bonus": round(bonus_revenue_amt, 2),
        "universal": round(univ_amount, 2),
        "bonus": round(bonus_amount, 2),
        "total": round(total, 2),
    }


def format_result(calc: dict, date: str, location: str,
                  hours: float, rate: float, revenue: float) -> str:
    rev_bonus = calc["rev_bonus"]

    lines = [
        f"✅ Записано!\n",
        f"📍 {location}",
        f"📅 {date}",
        f"⏱ {hours} год | Ставка {rate}",
        f"💵 Виторг: {revenue:,.0f} грн",
        f"📐 {calc['hourly_rate']} грн/год"
        + (f" (бонус +{rev_bonus} грн/год)" if rev_bonus > 0 else "") + "\n",
        f"💰 Розрахунок:",
        f"  База (110 × {hours} год): {calc['base_pay']:,.0f} грн",
    ]
    if rev_bonus > 0:
        lines.append(f"  Бонус виторгу (+{rev_bonus} × {hours} год): +{calc['rate_bonus']:,.0f} грн")
    if calc["universal"]:
        lines.append(f"  Універсал: +{calc['universal']:,.0f} грн")
    if calc["bonus"]:
        lines.append(f"  Премія: +{calc['bonus']:,.0f} грн")
    lines.append(f"  ─────────────────")
    lines.append(f"  💵 Разом: {calc['total']:,.0f} грн")
    lines.append(f"\n📊 Унів. та премію проставляє адмін")
    return "\n".join(lines)
