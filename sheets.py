"""
Робота з Google Sheets v2
- Підтримка кількох записів за один день
- Ідентифікація запису по row_id
- Редагування адміном без обмеження місяця
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

    def _rows_to_dicts(self, ws):
        """Повертає всі рядки як словники з row_id."""
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
        for r in self._rows_to_dicts(self._ws(SH_ROLES)):
            if str(r["telegram_id"]) == str(telegram_id):
                return r
        return None

    def set_role(self, telegram_id, role, location=""):
        ws = self._ws(SH_ROLES)
        for r in self._rows_to_dicts(ws):
            if str(r["telegram_id"]) == str(telegram_id):
                ws.update(f"A{r['row_id']}:C{r['row_id']}", [[str(telegram_id), role, location]])
                return
        ws.append_row([str(telegram_id), role, location])

    def remove_role(self, telegram_id):
        ws = self._ws(SH_ROLES)
        for r in self._rows_to_dicts(ws):
            if str(r["telegram_id"]) == str(telegram_id):
                ws.delete_rows(r["row_id"])
                return True
        return False

    def get_all_roles(self):
        return self._rows_to_dicts(self._ws(SH_ROLES))

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

    def get_entries_by_date(self, telegram_id, date):
        """Всі записи працівника за конкретну дату."""
        return [r for r in self._rows_to_dicts(self._ws(SH_ENTRIES))
                if str(r["telegram_id"]) == str(telegram_id) and r["date"] == date]

    def get_entry_by_row(self, row_id):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)
        row = ws.row_values(row_id)
        d = {headers[j]: row[j] if j < len(row) else "" for j in range(len(headers))}
        d["row_id"] = row_id
        return d

    def update_entry_by_row(self, row_id, field, value):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)
        if field not in headers:
            return False
        col = headers.index(field) + 1
        ws.update_cell(row_id, col, value)
        self._recalc_row(ws, row_id, headers)
        return True

    def _recalc_row(self, ws, row_idx, headers):
        from calc import get_hourly_rate, get_revenue_bonus
        row = ws.row_values(row_idx)
        def v(f):
            try:
                return float(row[headers.index(f)])
            except Exception:
                return 0.0
        rate = v("rate")
        revenue = v("revenue")
        hours = v("hours")
        hourly = get_hourly_rate(rate, revenue)
        rev_bonus = get_revenue_bonus(rate, revenue)
        base = hours * 110
        rate_bonus = hours * rev_bonus
        ws.update_cell(row_idx, headers.index("hourly_rate") + 1, hourly)
        ws.update_cell(row_idx, headers.index("base_pay") + 1, round(base, 2))
        ws.update_cell(row_idx, headers.index("rate_bonus") + 1, round(rate_bonus, 2))
        total = base + rate_bonus + v("universal") + v("bonus")
        ws.update_cell(row_idx, headers.index("total") + 1, round(total, 2))

    def delete_entry_by_row(self, row_id):
        self._ws(SH_ENTRIES).delete_rows(row_id)

    def set_universal_bonus(self, telegram_id, date, universal, bonus, row_id=None):
        ws = self._ws(SH_ENTRIES)
        headers = ws.row_values(1)
        if row_id:
            rows_to_update = [row_id]
        else:
            rows_to_update = [r["row_id"] for r in self._rows_to_dicts(ws)
                              if str(r["telegram_id"]) == str(telegram_id) and r["date"] == date]
        for rid in rows_to_update:
            ws.update_cell(rid, headers.index("universal") + 1, round(universal, 2))
            ws.update_cell(rid, headers.index("bonus") + 1, round(bonus, 2))
            self._recalc_row(ws, rid, headers)
        return bool(rows_to_update)

    # ── Admin: редагування будь-якого запису ──────────────────────────────────

    def get_worker_all_entries(self, telegram_id):
        """Всі записи працівника без обмеження місяця (для адміна)."""
        result = []
        for r in self._rows_to_dicts(self._ws(SH_ENTRIES)):
            if str(r["telegram_id"]) == str(telegram_id):
                result.append(r)
        return sorted(result, key=lambda x: (self._parse_date(x["date"]), x["row_id"]))

    # ── Reports ───────────────────────────────────────────────────────────────

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

    def get_day_entries(self, location, date):
        return [r for r in self._rows_to_dicts(self._ws(SH_ENTRIES))
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
