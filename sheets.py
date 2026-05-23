"""
Робота з Google Sheets
Аркуші:
  Працівники  — telegram_id | name
  Ролі        — telegram_id | role | location
  Записи      — telegram_id | name | date | location | hours | rate |
                revenue | hourly_rate | base_pay | rate_bonus |
                universal | bonus | total
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SH_WORKERS = "Працівники"
SH_ROLES   = "Ролі"
SH_ENTRIES = "Записи"


class SheetsManager:
    def __init__(self):
        creds_json = os.getenv("GOOGLE_CREDS_JSON")
        if creds_json:
            creds = Credentials.from_service_account_info(
                json.loads(creds_json), scopes=SCOPES
            )
        else:
            creds = Credentials.from_service_account_file(
                os.getenv("GOOGLE_CREDS_FILE", "credentials.json"), scopes=SCOPES
            )
        self.gc = gspread.authorize(creds)
        self.ss = self.gc.open_by_key(os.getenv("SPREADSHEET_ID"))
        self._init_sheets()

    def _init_sheets(self):
        existing = {s.title for s in self.ss.worksheets()}
        if SH_WORKERS not in existing:
            ws = self.ss.add_worksheet(SH_WORKERS, 500, 2)
            ws.append_row(["telegram_id", "name"])
        if SH_ROLES not in existing:
            ws = self.ss.add_worksheet(SH_ROLES, 200, 3)
            ws.append_row(["telegram_id", "role", "location"])
        if SH_ENTRIES not in existing:
            ws = self.ss.add_worksheet(SH_ENTRIES, 10000, 13)
            ws.append_row([
                "telegram_id", "name", "date", "location",
                "hours", "rate", "revenue", "hourly_rate",
                "base_pay", "rate_bonus", "universal", "bonus", "total"
            ])

    def _ws(self, name):
        return self.ss.worksheet(name)

    def _parse_date(self, d):
        return datetime.strptime(str(d).strip().lstrip("'"), "%d.%m.%Y")

    def _rows_to_dicts(self, ws):
        headers = ws.row_values(1)
        all_rows = ws.get_all_values()
        result = []
        for i, row in enumerate(all_rows[1:], start=2):
            if not any(row):
                continue
            d = {headers[j]: row[j] if j < len(row) else "" for j in range(len(headers))}
            d["row_id"] = i
            result.append(d)
        return result

    # ── Workers ───────────────────────────────────────────────────────────────

    def get_worker(self, telegram_id):
        for r in self._rows_to_dicts(self._ws(SH_WORKERS)):
            if str(r["telegram_id"]) == str(telegram_id):
                return r
        return None

    def get_all_workers(self):
        return self._rows_to_dicts(self._ws(SH_WORKERS))

    def add_worker(self, telegram_id, name):
        self._ws(SH_WORKERS).append_row([str(telegram_id), name])

    def remove_worker(self, telegram_id):
        ws = self._ws(SH_WORKERS)
        for r in self._rows_to_dicts(ws):
            if str(r["telegram_id"]) == str(telegram_id):
                ws.delete_rows(r["row_id"])
                return True
        return False

    def search_workers(self, query):
        q = query.lower()
        return [r for r in self.get_all_workers() if q in r["name"].lower()]

    # ── Roles ─────────────────────────────────────────────────────────────────

    def get_role(self, telegram_id):
        """Повертає перший запис ролі для користувача."""
        for r in self._rows_to_dicts(self._ws(SH_ROLES)):
            if str(r["telegram_id"]) == str(telegram_id):
                return r
        return None

    def get_all_roles_for(self, telegram_id):
        """Повертає ВСІ рядки ролей для одного користувача."""
        return [
            r for r in self._rows_to_dicts(self._ws(SH_ROLES))
            if str(r["telegram_id"]) == str(telegram_id)
        ]

    def get_all_roles(self):
        return self._rows_to_dicts(self._ws(SH_ROLES))

    def set_role(self, telegram_id, role, location=""):
        """
        Призначає роль.
        Для location_admin: якщо такий заклад вже є — нічого не робить,
        інакше додає новий рядок (один адмін може мати кілька закладів).
        Для owner/superadmin: оновлює перший рядок або створює новий.
        """
        ws = self._ws(SH_ROLES)
        existing = self.get_all_roles_for(telegram_id)

        if role == "location_admin":
            for r in existing:
                if (r.get("role") == "location_admin"
                        and r.get("location", "").strip() == location.strip()):
                    return  # такий заклад вже є
            ws.append_row([str(telegram_id), role, location])
        else:
            if existing:
                first = existing[0]
                ws.update(
                    f"A{first['row_id']}:C{first['row_id']}",
                    [[str(telegram_id), role, location]]
                )
                for r in existing[1:]:
                    try:
                        ws.delete_rows(r["row_id"])
                    except Exception:
                        pass
            else:
                ws.append_row([str(telegram_id), role, location])

    def remove_role(self, telegram_id, location=None):
        """
        Видаляє роль.
        Якщо location вказано — видаляє лише той рядок із закладом.
        Якщо location=None — видаляє ВСІ рядки ролей користувача.
        """
        ws = self._ws(SH_ROLES)
        rows = self.get_all_roles_for(telegram_id)
        if not rows:
            return False
        deleted = False
        for r in sorted(rows, key=lambda x: x["row_id"], reverse=True):
            if location is None or r.get("location", "").strip() == location.strip():
                try:
                    ws.delete_rows(r["row_id"])
                    deleted = True
                except Exception:
                    pass
        return deleted

    # ── Role checks ───────────────────────────────────────────────────────────

    def is_owner(self, tid):
        rows = self.get_all_roles_for(tid)
        return any(r.get("role") == "owner" for r in rows)

    def is_superadmin_or_above(self, tid):
        rows = self.get_all_roles_for(tid)
        return any(r.get("role") in ("owner", "superadmin") for r in rows)

    def is_admin_or_above(self, tid):
        rows = self.get_all_roles_for(tid)
        return any(r.get("role") in ("owner", "superadmin", "location_admin") for r in rows)

    def can_manage_workers(self, tid):
        return self.is_admin_or_above(tid)

    def get_admin_locations(self, tid):
        """
        Повертає список закладів для location_admin.
        owner/superadmin → [] (порожній = всі заклади).
        """
        role = self.get_role(tid)
        if role is None:
            return []
        if role["role"] in ("owner", "superadmin"):
            return []
        if role["role"] == "location_admin":
            rows = self.get_all_roles_for(tid)
            return [
                r.get("location", "").strip() for r in rows
                if r.get("role") == "location_admin"
                and r.get("location", "").strip()
            ]
        return []

    # ── Entries ───────────────────────────────────────────────────────────────

    def save_entry(self, telegram_id, name, date, location,
                   hours, rate, revenue, hourly_rate,
                   base_pay, rate_bonus, universal=0, bonus=0):
        total = base_pay + rate_bonus + universal + bonus
        self._ws(SH_ENTRIES).append_row([
            str(telegram_id), name, date, location,
            hours, rate, revenue, hourly_rate,
            round(base_pay, 2), round(rate_bonus, 2),
            round(universal, 2), round(bonus, 2), round(total, 2)
        ])

    def get_worker_entries(self, telegram_id, month, year):
        result = []
        for r in self._rows_to_dicts(self._ws(SH_ENTRIES)):
            if str(r["telegram_id"]) != str(telegram_id):
                continue
            try:
                d = self._parse_date(r["date"])
                if d.month == month and d.year == year:
                    result.append(r)
            except ValueError:
                continue
        return sorted(result, key=lambda x: (self._parse_date(x["date"]), x["row_id"]))

    def get_all_worker_entries(self, telegram_id):
        result = []
        for r in self._rows_to_dicts(self._ws(SH_ENTRIES)):
            if str(r["telegram_id"]) == str(telegram_id):
                result.append(r)
        return sorted(result, key=lambda x: (self._parse_date(x["date"]), x["row_id"]))

    def get_entries_by_date(self, telegram_id, date):
        return [
            r for r in self._rows_to_dicts(self._ws(SH_ENTRIES))
            if str(r["telegram_id"]) == str(telegram_id) and r.get("date") == date
        ]

    def get_entry_by_row(self, row_id):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)
        row = ws.row_values(row_id)
        if not row:
            return None
        d = {headers[j]: row[j] if j < len(row) else "" for j in range(len(headers))}
        d["row_id"] = row_id
        return d

    def delete_entry_by_row(self, row_id):
        self._ws(SH_ENTRIES).delete_rows(row_id)

    def update_entry_field(self, row_id, field, value):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)
        if field not in headers:
            return False
        col = headers.index(field) + 1
        ws.update_cell(row_id, col, value)
        return True

    def set_universal_bonus(self, telegram_id, date, universal, bonus, row_id=None):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)

        def _update_row(i):
            row = ws.row_values(i)
            try:
                base = float(row[headers.index("base_pay")] or 0)
                rb   = float(row[headers.index("rate_bonus")] or 0)
            except (ValueError, IndexError):
                base, rb = 0, 0
            new_total = round(base + rb + universal + bonus, 2)
            ws.update_cell(i, headers.index("universal") + 1, round(universal, 2))
            ws.update_cell(i, headers.index("bonus") + 1, round(bonus, 2))
            ws.update_cell(i, headers.index("total") + 1, new_total)

        if row_id:
            _update_row(row_id)
            return True

        for r in self._rows_to_dicts(ws):
            if str(r["telegram_id"]) == str(telegram_id) and r.get("date") == date:
                _update_row(r["row_id"])
                return True
        return False

    # ── Reports ───────────────────────────────────────────────────────────────

    def get_day_entries(self, location, date):
        return [
            r for r in self._rows_to_dicts(self._ws(SH_ENTRIES))
            if r.get("location") == location and r.get("date") == date
        ]

    def get_location_entries(self, location, month, year):
        result = []
        for r in self._rows_to_dicts(self._ws(SH_ENTRIES)):
            if r.get("location") != location:
                continue
            try:
                d = self._parse_date(r["date"])
                if d.month == month and d.year == year:
                    result.append(r)
            except ValueError:
                continue
        return sorted(result, key=lambda x: (self._parse_date(x["date"]), x["row_id"]))

    def get_all_entries(self, month, year):
        result = []
        for r in self._rows_to_dicts(self._ws(SH_ENTRIES)):
            try:
                d = self._parse_date(r["date"])
                if d.month == month and d.year == year:
                    result.append(r)
            except ValueError:
                continue
        return result

    def summarize_workers(self, entries):
        s = {}
        for r in entries:
            tid = str(r["telegram_id"])
            if tid not in s:
                s[tid] = {
                    "name": r["name"], "days": 0, "hours": 0.0,
                    "base_pay": 0.0, "rate_bonus": 0.0,
                    "universal": 0.0, "bonus": 0.0, "total": 0.0,
                    "locations": set()
                }
            s[tid]["days"] += 1
            for f in ("hours", "base_pay", "rate_bonus", "universal", "bonus", "total"):
                s[tid][f] += float(r.get(f, 0) or 0)
            s[tid]["locations"].add(r.get("location", ""))
        for v in s.values():
            v["locations"] = sorted(v["locations"])
        return s

    def summarize_locations(self, entries):
        s = {}
        for r in entries:
            loc = r.get("location", "?")
            if loc not in s:
                s[loc] = {
                    "days": 0, "hours": 0.0,
                    "base_pay": 0.0, "rate_bonus": 0.0,
                    "universal": 0.0, "bonus": 0.0, "total": 0.0
                }
            s[loc]["days"] += 1
            for f in ("hours", "base_pay", "rate_bonus", "universal", "bonus", "total"):
                s[loc][f] += float(r.get(f, 0) or 0)
        return s
