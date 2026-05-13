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
        creds = Credentials.from_service_account_file(
            os.getenv("GOOGLE_CREDS_FILE", "credentials.json"), scopes=SCOPES
        )
        self.gc = gspread.authorize(creds)
        self.ss = self.gc.open_by_key(os.getenv("SPREADSHEET_ID"))
        self._init_sheets()

    def _init_sheets(self):
        existing = {s.title for s in self.ss.worksheets()}
        if SH_WORKERS not in existing:
            ws = self.ss.add_worksheet(SH_WORKERS, 500, 3)
            ws.append_row(["telegram_id", "name"])
        if SH_ROLES not in existing:
            ws = self.ss.add_worksheet(SH_ROLES, 200, 3)
            ws.append_row(["telegram_id", "role", "location"])
        if SH_ENTRIES not in existing:
            ws = self.ss.add_worksheet(SH_ENTRIES, 10000, 14)
            ws.append_row([
                "telegram_id", "name", "date", "location",
                "hours", "rate", "revenue", "hourly_rate",
                "base_pay", "rate_bonus", "universal", "bonus", "total"
            ])

    def _ws(self, name):
        return self.ss.worksheet(name)

    def _parse_date(self, d):
        return datetime.strptime(d, "%d.%m.%Y")

    # ── Workers ───────────────────────────────────────────────────────────────

    def get_worker(self, telegram_id):
        for r in self._ws(SH_WORKERS).get_all_records():
            if str(r["telegram_id"]) == str(telegram_id):
                return r
        return None

    def get_all_workers(self):
        return self._ws(SH_WORKERS).get_all_records()

    def add_worker(self, telegram_id, name):
        self._ws(SH_WORKERS).append_row([str(telegram_id), name])

    def remove_worker(self, telegram_id):
        ws = self._ws(SH_WORKERS)
        for i, row in enumerate(ws.get_all_values()[1:], start=2):
            if str(row[0]) == str(telegram_id):
                ws.delete_rows(i)
                return True
        return False

    def search_workers(self, query):
        q = query.lower()
        return [r for r in self.get_all_workers() if q in r["name"].lower()]

    # ── Roles ─────────────────────────────────────────────────────────────────

    def get_role(self, telegram_id):
        for r in self._ws(SH_ROLES).get_all_records():
            if str(r["telegram_id"]) == str(telegram_id):
                return r
        return None

    def set_role(self, telegram_id, role, location=""):
        ws = self._ws(SH_ROLES)
        for i, row in enumerate(ws.get_all_values()[1:], start=2):
            if str(row[0]) == str(telegram_id):
                ws.update(f"A{i}:C{i}", [[str(telegram_id), role, location]])
                return
        ws.append_row([str(telegram_id), role, location])

    def remove_role(self, telegram_id):
        ws = self._ws(SH_ROLES)
        for i, row in enumerate(ws.get_all_values()[1:], start=2):
            if str(row[0]) == str(telegram_id):
                ws.delete_rows(i)
                return True
        return False

    def get_all_roles(self):
        return self._ws(SH_ROLES).get_all_records()

    def is_owner(self, tid):
        r = self.get_role(tid)
        return r is not None and r["role"] == "owner"

    def is_superadmin_or_above(self, tid):
        r = self.get_role(tid)
        return r is not None and r["role"] in ("owner", "superadmin")

    def is_admin_or_above(self, tid):
        r = self.get_role(tid)
        return r is not None and r["role"] in ("owner", "superadmin", "location_admin")

    def can_manage_workers(self, tid):
        return self.is_admin_or_above(tid)

    def get_admin_location(self, tid):
        r = self.get_role(tid)
        if r and r["role"] == "location_admin":
            return r.get("location", "")
        return ""

    # ── Entries ───────────────────────────────────────────────────────────────

    def check_entry_exists(self, telegram_id, date):
        for r in self._ws(SH_ENTRIES).get_all_records():
            if str(r["telegram_id"]) == str(telegram_id) and r["date"] == date:
                return True
        return False

    def save_entry(self, telegram_id, name, date, location,
                   hours, rate, revenue, hourly_rate,
                   base_pay, rate_bonus, universal=0, bonus=0):
        total = base_pay + universal + bonus
        self._ws(SH_ENTRIES).append_row([
            str(telegram_id), name, date, location,
            hours, rate, revenue, hourly_rate,
            round(base_pay, 2), round(rate_bonus, 2),
            round(universal, 2), round(bonus, 2), round(total, 2)
        ])

    def get_worker_entries(self, telegram_id, month, year):
        result = []
        for r in self._ws(SH_ENTRIES).get_all_records():
            if str(r["telegram_id"]) != str(telegram_id):
                continue
            try:
                d = self._parse_date(r["date"])
                if d.month == month and d.year == year:
                    result.append(r)
            except ValueError:
                continue
        return sorted(result, key=lambda x: self._parse_date(x["date"]))

    def get_entry_by_date(self, telegram_id, date):
        for r in self._ws(SH_ENTRIES).get_all_records():
            if str(r["telegram_id"]) == str(telegram_id) and r["date"] == date:
                return r
        return None

    def update_entry_field(self, telegram_id, date, field, value):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)
        if field not in headers:
            return False
        col = headers.index(field) + 1
        for i, row in enumerate(ws.get_all_values()[1:], start=2):
            if str(row[0]) == str(telegram_id) and row[2] == date:
                ws.update_cell(i, col, value)
                self._recalc_row(ws, i, headers)
                return True
        return False

    def _recalc_row(self, ws, row_idx, headers):
        row = ws.row_values(row_idx)
        def v(f):
            try:
                return float(row[headers.index(f)])
            except Exception:
                return 0.0
        # Перерахунок hourly_rate та base_pay якщо змінились rate/revenue/hours
        from calc import get_hourly_rate, get_rate_bonus
        rate = v("rate")
        revenue = v("revenue")
        hours = v("hours")
        hourly = get_hourly_rate(rate, revenue)
        base = hours * hourly
        rate_bonus = get_rate_bonus(rate, revenue, hours)
        ws.update_cell(row_idx, headers.index("hourly_rate") + 1, hourly)
        ws.update_cell(row_idx, headers.index("base_pay") + 1, round(base, 2))
        ws.update_cell(row_idx, headers.index("rate_bonus") + 1, round(rate_bonus, 2))
        total = base + v("universal") + v("bonus")
        ws.update_cell(row_idx, headers.index("total") + 1, round(total, 2))

    def delete_entry(self, telegram_id, date):
        ws = self._ws(SH_ENTRIES)
        for i, row in enumerate(ws.get_all_values()[1:], start=2):
            if str(row[0]) == str(telegram_id) and row[2] == date:
                ws.delete_rows(i)
                return True
        return False

    def set_universal_bonus(self, telegram_id, date, universal, bonus):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)
        for i, row in enumerate(ws.get_all_values()[1:], start=2):
            if str(row[0]) == str(telegram_id) and row[2] == date:
                ws.update_cell(i, headers.index("universal") + 1, round(universal, 2))
                ws.update_cell(i, headers.index("bonus") + 1, round(bonus, 2))
                self._recalc_row(ws, i, headers)
                return True
        return False

    # ── Reports ───────────────────────────────────────────────────────────────

    def get_location_entries(self, location, month, year):
        result = []
        for r in self._ws(SH_ENTRIES).get_all_records():
            if r.get("location") != location:
                continue
            try:
                d = self._parse_date(r["date"])
                if d.month == month and d.year == year:
                    result.append(r)
            except ValueError:
                continue
        return sorted(result, key=lambda x: self._parse_date(x["date"]))

    def get_all_entries(self, month, year):
        result = []
        for r in self._ws(SH_ENTRIES).get_all_records():
            try:
                d = self._parse_date(r["date"])
                if d.month == month and d.year == year:
                    result.append(r)
            except ValueError:
                continue
        return result

    def get_day_entries(self, location, date):
        return [r for r in self._ws(SH_ENTRIES).get_all_records()
                if r.get("location") == location and r.get("date") == date]

    def summarize_workers(self, entries):
        s = {}
        for r in entries:
            tid = str(r["telegram_id"])
            if tid not in s:
                s[tid] = {"name": r["name"], "days": 0, "hours": 0.0,
                          "base_pay": 0.0, "rate_bonus": 0.0,
                          "universal": 0.0, "bonus": 0.0, "total": 0.0,
                          "locations": set()}
            s[tid]["days"] += 1
            for f in ("hours", "base_pay", "rate_bonus", "universal", "bonus", "total"):
                s[tid][f] += float(r.get(f, 0))
            s[tid]["locations"].add(r.get("location", ""))
        for v in s.values():
            v["locations"] = sorted(v["locations"])
        return s

    def summarize_locations(self, entries):
        s = {}
        for r in entries:
            loc = r.get("location", "?")
            if loc not in s:
                s[loc] = {"workers": set(), "days": 0, "hours": 0.0,
                          "base_pay": 0.0, "rate_bonus": 0.0,
                          "universal": 0.0, "bonus": 0.0, "total": 0.0}
            s[loc]["workers"].add(str(r["telegram_id"]))
            s[loc]["days"] += 1
            for f in ("hours", "base_pay", "rate_bonus", "universal", "bonus", "total"):
                s[loc][f] += float(r.get(f, 0))
        for v in s.values():
            v["worker_count"] = len(v["workers"])
        return s
