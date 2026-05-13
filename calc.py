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

REVENUE_THRESHOLD = 40_000
RATE1_HOURLY = 110
RATE15_HIGH_HOURLY = 130
RATE15_LOW_HOURLY = 110
UNIVERSAL_BONUS = 150
DAILY_BONUS = 200


def get_hourly_rate(rate: float, revenue: float) -> int:
    if rate == 1:
        return RATE1_HOURLY
    return RATE15_HIGH_HOURLY if revenue >= REVENUE_THRESHOLD else RATE15_LOW_HOURLY


def get_rate_bonus(rate: float, revenue: float, hours: float) -> float:
    """Додаткові гроші від ставки 1.5 (різниця 110→130 коли виторг >=40к)"""
    if rate == 1.5 and revenue >= REVENUE_THRESHOLD:
        return hours * (RATE15_HIGH_HOURLY - RATE1_HOURLY)
    return 0.0


def calculate(hours: float, rate: float, revenue: float,
              universal: bool = False, bonus: bool = False) -> dict:
    hourly = get_hourly_rate(rate, revenue)
    base = hours * hourly
    rate_bonus = get_rate_bonus(rate, revenue, hours)
    univ_amount = UNIVERSAL_BONUS if universal else 0
    bonus_amount = DAILY_BONUS if bonus else 0
    total = base + univ_amount + bonus_amount

    return {
        "hourly_rate": hourly,
        "base_pay": round(base, 2),
        "rate_bonus": round(rate_bonus, 2),
        "universal": round(univ_amount, 2),
        "bonus": round(bonus_amount, 2),
        "total": round(total, 2),
    }


def format_result(calc: dict, date: str, location: str,
                  hours: float, rate: float, revenue: float) -> str:
    rate_note = ""
    if rate == 1.5:
        cond = "≥ 40к ✓" if revenue >= REVENUE_THRESHOLD else "< 40к"
        rate_note = f" ({cond})"

    lines = [
        f"✅ Записано!\n",
        f"📍 {location}",
        f"📅 {date}",
        f"⏱ {hours} год | Ставка {rate}",
        f"📐 {calc['hourly_rate']} грн/год{rate_note}\n",
        f"💰 Розрахунок:",
        f"  Базова: {calc['base_pay']:,.0f} грн",
    ]
    if calc["universal"]:
        lines.append(f"  Універсал: +{calc['universal']:,.0f} грн")
    if calc["bonus"]:
        lines.append(f"  Премія: +{calc['bonus']:,.0f} грн")
    lines.append(f"  ─────────────────")
    lines.append(f"  💵 Разом: {calc['total']:,.0f} грн")
    lines.append(f"\n📊 Унів. та премію проставляє адмін")
    return "\n".join(lines)
