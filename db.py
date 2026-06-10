"""
Database manager — Supabase
Замінює sheets.py. Зберігає той самий інтерфейс.
"""
import os
from datetime import datetime
from supabase import create_client, Client


class DB:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL або SUPABASE_KEY не знайдено")
        self.sb: Client = create_client(url, key)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_date(self, d: str) -> datetime:
        return datetime.strptime(str(d).strip().lstrip("'"), "%d.%m.%Y")

    def _row(self, d: dict) -> dict:
        """Додає row_id як аліас для id."""
        if d and "id" in d:
            d["row_id"] = d["id"]
        return d

    def _rows(self, data: list) -> list:
        return [self._row(d) for d in (data or [])]

    # ── Workers ───────────────────────────────────────────────────────────────

    def get_worker(self, telegram_id):
        r = self.sb.table("workers").select("*").eq("telegram_id", int(telegram_id)).execute()
        return self._row(r.data[0]) if r.data else None

    def get_all_workers(self):
        r = self.sb.table("workers").select("*").order("name").limit(10000).execute()
        return self._rows(r.data)

    def add_worker(self, telegram_id, name):
        self.sb.table("workers").insert({
            "telegram_id": int(telegram_id), "name": name
        }).execute()

    def remove_worker(self, telegram_id):
        self.sb.table("workers").delete().eq("telegram_id", int(telegram_id)).execute()
        return True

    def search_workers(self, query):
        r = self.sb.table("workers").select("*").ilike("name", f"%{query}%").execute()
        return self._rows(r.data)

    # ── Roles ─────────────────────────────────────────────────────────────────

    def get_role(self, telegram_id):
        r = self.sb.table("roles").select("*").eq("telegram_id", int(telegram_id)).limit(1).execute()
        return self._row(r.data[0]) if r.data else None

    def get_all_roles_for(self, telegram_id):
        r = self.sb.table("roles").select("*").eq("telegram_id", int(telegram_id)).execute()
        return self._rows(r.data)

    def get_all_roles(self):
        r = self.sb.table("roles").select("*").limit(10000).execute()
        return self._rows(r.data)

    def set_role(self, telegram_id, role, location=""):
        existing = self.get_all_roles_for(telegram_id)
        if role == "location_admin":
            for r in existing:
                if r.get("role") == "location_admin" and r.get("location", "").strip() == location.strip():
                    return
            self.sb.table("roles").insert({
                "telegram_id": int(telegram_id), "role": role, "location": location
            }).execute()
        else:
            if existing:
                self.sb.table("roles").delete().eq("telegram_id", int(telegram_id)).execute()
            self.sb.table("roles").insert({
                "telegram_id": int(telegram_id), "role": role, "location": location
            }).execute()

    def remove_role(self, telegram_id, location=None):
        if location is None:
            self.sb.table("roles").delete().eq("telegram_id", int(telegram_id)).execute()
        else:
            rows = self.get_all_roles_for(telegram_id)
            for r in rows:
                if r.get("location", "").strip() == location.strip():
                    self.sb.table("roles").delete().eq("id", r["id"]).execute()
        return True

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
        role = self.get_role(tid)
        if role is None:
            return []
        if role["role"] in ("owner", "superadmin"):
            return []
        if role["role"] == "location_admin":
            rows = self.get_all_roles_for(tid)
            return [
                r.get("location", "").strip() for r in rows
                if r.get("role") == "location_admin" and r.get("location", "").strip()
            ]
        return []

    # ── Entries ───────────────────────────────────────────────────────────────

    def save_entry(self, telegram_id, name, date, location,
                   hours, rate, revenue, hourly_rate,
                   base_pay, rate_bonus, universal=0, bonus=0):
        total = round(base_pay + rate_bonus + universal + bonus, 2)
        self.sb.table("entries").insert({
            "telegram_id": int(telegram_id),
            "name":        name,
            "date":        date,
            "location":    location,
            "hours":       float(hours),
            "rate":        float(rate),
            "revenue":     float(revenue),
            "hourly_rate": float(hourly_rate),
            "base_pay":    round(float(base_pay), 2),
            "rate_bonus":  round(float(rate_bonus), 2),
            "universal":   round(float(universal), 2),
            "bonus":       round(float(bonus), 2),
            "total":       total,
        }).execute()

    def _month_pattern(self, month: int, year: int) -> str:
        return f"__.{month:02d}.{year}"

    def get_worker_entries(self, telegram_id, month, year):
        r = (self.sb.table("entries")
             .select("*")
             .eq("telegram_id", int(telegram_id))
             .like("date", self._month_pattern(month, year))
             .execute())
        data = self._rows(r.data)
        return sorted(data, key=lambda x: (self._parse_date(x["date"]), x["id"]))

    def get_all_worker_entries(self, telegram_id):
        r = self.sb.table("entries").select("*").eq("telegram_id", int(telegram_id)).limit(10000).execute()
        data = self._rows(r.data)
        return sorted(data, key=lambda x: (self._parse_date(x["date"]), x["id"]))

    def get_entries_by_date(self, telegram_id, date):
        r = (self.sb.table("entries")
             .select("*")
             .eq("telegram_id", int(telegram_id))
             .eq("date", date)
             .execute())
        return self._rows(r.data)

    def get_entry_by_row(self, row_id):
        r = self.sb.table("entries").select("*").eq("id", int(row_id)).execute()
        return self._row(r.data[0]) if r.data else None

    def delete_entry_by_row(self, row_id):
        self.sb.table("entries").delete().eq("id", int(row_id)).execute()

    def update_entry_field(self, row_id, field, value):
        self.sb.table("entries").update({field: value}).eq("id", int(row_id)).execute()
        return True

    def update_entry_recalc(self, row_id: int, field: str, value) -> dict:
        from calc import calculate
        self.sb.table("entries").update({field: value}).eq("id", int(row_id)).execute()

        if field in ("hours", "rate", "revenue"):
            entry = self.get_entry_by_row(row_id)
            hours   = float(entry.get("hours")   or 0)
            rate    = float(entry.get("rate")     or 1)
            revenue = float(entry.get("revenue")  or 0)
            univ    = float(entry.get("universal")or 0)
            bonus   = float(entry.get("bonus")    or 0)

            calc        = calculate(hours, rate, revenue)
            base_stored = round(calc["base_pay"] + calc["addon_pay"], 2)
            total_new   = round(base_stored + calc["rate_bonus"] + univ + bonus, 2)

            self.sb.table("entries").update({
                "hourly_rate": calc["hourly_rate"],
                "base_pay":    base_stored,
                "rate_bonus":  round(calc["rate_bonus"], 2),
                "total":       total_new,
            }).eq("id", int(row_id)).execute()

        return self.get_entry_by_row(row_id)

    def set_universal_bonus(self, telegram_id, date, universal, bonus, row_id=None):
        if row_id:
            entry = self.get_entry_by_row(row_id)
            if entry:
                base = float(entry.get("base_pay") or 0)
                rb   = float(entry.get("rate_bonus") or 0)
                new_total = round(base + rb + universal + bonus, 2)
                self.sb.table("entries").update({
                    "universal": round(universal, 2),
                    "bonus":     round(bonus, 2),
                    "total":     new_total,
                }).eq("id", int(row_id)).execute()
            return True

        r = (self.sb.table("entries")
             .select("*")
             .eq("telegram_id", int(telegram_id))
             .eq("date", date)
             .execute())
        for entry in (r.data or []):
            base = float(entry.get("base_pay") or 0)
            rb   = float(entry.get("rate_bonus") or 0)
            new_total = round(base + rb + universal + bonus, 2)
            self.sb.table("entries").update({
                "universal": round(universal, 2),
                "bonus":     round(bonus, 2),
                "total":     new_total,
            }).eq("id", entry["id"]).execute()
        return True

    # ── Reports ───────────────────────────────────────────────────────────────

    def get_day_entries(self, location, date):
        r = (self.sb.table("entries")
             .select("*")
             .eq("location", location)
             .eq("date", date)
             .limit(10000)
             .execute())
        return self._rows(r.data)

    def get_location_entries(self, location, month, year):
        r = (self.sb.table("entries")
             .select("*")
             .eq("location", location)
             .like("date", self._month_pattern(month, year))
             .execute())
        data = self._rows(r.data)
        return sorted(data, key=lambda x: (self._parse_date(x["date"]), x["id"]))

    def get_all_entries(self, month, year):
        r = (self.sb.table("entries")
             .select("*")
             .like("date", self._month_pattern(month, year))
             .execute())
        return self._rows(r.data)

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
                s[tid][f] += float(r.get(f) or 0)
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
                s[loc][f] += float(r.get(f) or 0)
        return s
