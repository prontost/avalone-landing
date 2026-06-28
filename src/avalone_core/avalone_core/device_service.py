"""Device fingerprinting and screen-time tracking for Avalone.

Shared by the portal, Avalone Finance and Avalone Work. Screen time is updated by a periodic
heartbeat from the shared shell JS.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Any

from avalone_core.database import Repository, Service


class DeviceRepository(Repository):
    """SQL access for devices and per-device daily screen time."""

    def upsert(
        self,
        user_id: int,
        fingerprint: str,
        device_id: str | None,
        user_agent: str,
        screen: str,
        platform: str,
        ip: str,
        now: str,
    ) -> int:
        """Return the device row id, creating the row if necessary."""
        with self._db.connection() as con:
            # Prefer matching an existing row for this user + fingerprint.
            row = con.execute(
                "SELECT id FROM avalone_devices WHERE user_id = ? AND fingerprint = ?",
                (user_id, fingerprint),
            ).fetchone()
            if row:
                db_id = row["id"]
                con.execute(
                    """UPDATE avalone_devices
                       SET last_seen_at = ?, last_ip = ?, user_agent = ?, screen = ?, platform = ?
                       WHERE id = ?""",
                    (now, ip, user_agent, screen, platform, db_id),
                )
                if device_id:
                    con.execute(
                        "UPDATE avalone_devices SET device_id = ? WHERE id = ? AND device_id IS NULL",
                        (device_id, db_id),
                    )
                return db_id

            if device_id:
                row = con.execute(
                    "SELECT id FROM avalone_devices WHERE device_id = ?", (device_id,)
                ).fetchone()
                if row:
                    db_id = row["id"]
                    con.execute(
                        """UPDATE avalone_devices
                           SET user_id = ?, fingerprint = ?, last_seen_at = ?, last_ip = ?,
                               user_agent = ?, screen = ?, platform = ?
                           WHERE id = ?""",
                        (user_id, fingerprint, now, ip, user_agent, screen, platform, db_id),
                    )
                    return db_id

            cur = con.execute(
                """INSERT INTO avalone_devices
                   (user_id, fingerprint, device_id, user_agent, screen, platform, last_ip,
                    created_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, fingerprint, device_id, user_agent, screen, platform, ip, now, now),
            )
            return cur.lastrowid or 0

    def get_by_device_id(self, device_id: str) -> dict[str, Any] | None:
        with self._db.connection() as con:
            row = con.execute(
                "SELECT * FROM avalone_devices WHERE device_id = ?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def add_screen_time(
        self, db_device_id: int, user_id: int, date: str, seconds: int, now: str
    ) -> None:
        with self._db.connection() as con:
            con.execute(
                """INSERT INTO avalone_screen_time (user_id, device_id, date, seconds, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, device_id, date)
                   DO UPDATE SET seconds = seconds + excluded.seconds, updated_at = excluded.updated_at""",
                (user_id, db_device_id, date, max(0, seconds), now),
            )

    def daily_screen_time(self, user_id: int, date: str) -> int:
        with self._db.connection() as con:
            row = con.execute(
                "SELECT COALESCE(SUM(seconds), 0) FROM avalone_screen_time WHERE user_id = ? AND date = ?",
                (user_id, date),
            ).fetchone()
        return row[0] if row else 0

    def total_screen_time(self, user_id: int) -> int:
        with self._db.connection() as con:
            row = con.execute(
                "SELECT COALESCE(SUM(seconds), 0) FROM avalone_screen_time WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row[0] if row else 0

    def user_devices(self, user_id: int) -> list[dict[str, Any]]:
        with self._db.connection() as con:
            rows = con.execute(
                """SELECT id, fingerprint, device_id, user_agent, screen, platform,
                          last_ip, created_at, last_seen_at
                   FROM avalone_devices
                   WHERE user_id = ?
                   ORDER BY last_seen_at DESC""",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]


class DeviceService(Service):
    """Business logic for device fingerprinting and screen-time aggregation."""

    _MAX_HEARTBEAT_SECONDS = 60

    def __init__(self, repo: DeviceRepository | None = None) -> None:
        self._repo = repo or DeviceRepository()

    @staticmethod
    def compute_fingerprint(user_agent: str, screen: str, platform: str) -> str:
        payload = f"{user_agent}|{screen}|{platform}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def heartbeat(
        self,
        user_id: int,
        device_id: str | None,
        user_agent: str,
        screen: str,
        platform: str,
        ip: str,
        seconds: int = 5,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat(timespec="seconds")
        date = now.date().isoformat()
        capped = min(max(0, seconds), self._MAX_HEARTBEAT_SECONDS)
        fingerprint = self.compute_fingerprint(user_agent, screen, platform)

        db_device_id = self._repo.upsert(
            user_id, fingerprint, device_id, user_agent, screen, platform, ip, now_iso
        )
        if capped and db_device_id:
            self._repo.add_screen_time(db_device_id, user_id, date, capped, now_iso)

        return {
            "device_id": device_id or db_device_id,
            "today_seconds": self._repo.daily_screen_time(user_id, date),
            "total_seconds": self._repo.total_screen_time(user_id),
        }

    def screen_time_summary(self, user_id: int) -> dict[str, Any]:
        date = datetime.now(timezone.utc).date().isoformat()
        return {
            "today_seconds": self._repo.daily_screen_time(user_id, date),
            "total_seconds": self._repo.total_screen_time(user_id),
            "devices": self._repo.user_devices(user_id),
        }
