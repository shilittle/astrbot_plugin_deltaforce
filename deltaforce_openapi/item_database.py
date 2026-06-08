from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class ItemImageRef:
    url: str
    local_path: Path | None = None


class ItemDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def upsert_items(self, items: Iterable[Any]) -> None:
        now = time.time()
        rows = []
        aliases = []
        for item in items:
            rows.append(
                (
                    item.base_id,
                    item.market_id,
                    item.oid,
                    item.object_id,
                    item.object_name,
                    item.pic,
                    item.grade,
                    item.primary_class,
                    item.second_class,
                    item.second_class_cn,
                    item.latest_price,
                    item.price_update_time,
                    item.price_start,
                    item.day_change,
                    now,
                )
            )
            for alias in _aliases(item):
                aliases.append((alias, item.base_id))
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO items (
                    base_id, market_id, oid, object_id, object_name, pic, grade,
                    primary_class, second_class, second_class_cn, latest_price,
                    price_update_time, price_start, day_change, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(base_id) DO UPDATE SET
                    market_id=excluded.market_id,
                    oid=excluded.oid,
                    object_id=excluded.object_id,
                    object_name=excluded.object_name,
                    pic=excluded.pic,
                    grade=excluded.grade,
                    primary_class=excluded.primary_class,
                    second_class=excluded.second_class,
                    second_class_cn=excluded.second_class_cn,
                    latest_price=excluded.latest_price,
                    price_update_time=excluded.price_update_time,
                    price_start=excluded.price_start,
                    day_change=excluded.day_change,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
            conn.executemany(
                """
                INSERT INTO item_aliases(alias, base_id)
                VALUES (?, ?)
                ON CONFLICT(alias) DO UPDATE SET base_id=excluded.base_id
                """,
                aliases,
            )

    def resolve_image_url(self, name: str, fallback_url: str = "") -> str:
        normalized = _normalize_alias(name)
        if not normalized:
            return fallback_url
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT items.pic FROM item_aliases
                JOIN items ON items.base_id = item_aliases.base_id
                WHERE item_aliases.alias = ?
                """,
                (normalized,),
            ).fetchone()
        if row and row[0]:
            return str(row[0])
        return fallback_url

    def resolve_image_ref(self, name: str, fallback_url: str = "") -> ItemImageRef | None:
        url = self.resolve_image_url(name, fallback_url).strip()
        if not url:
            return None
        return ItemImageRef(url=url, local_path=self.get_image_path(url))

    def get_image_path(self, url: str) -> Path | None:
        if not url:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT local_path FROM item_images WHERE url = ?",
                (url,),
            ).fetchone()
        if not row or not row[0]:
            return None
        path = Path(str(row[0]))
        return path if path.exists() else None

    def set_image_path(self, url: str, path: Path) -> None:
        if not url:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO item_images(url, local_path, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    local_path=excluded.local_path,
                    fetched_at=excluded.fetched_at
                """,
                (url, str(path), time.time()),
            )

    def list_image_urls(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT pic FROM items WHERE pic IS NOT NULL AND pic != '' ORDER BY pic"
            ).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    def image_stats(self) -> tuple[int, int]:
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(DISTINCT pic) FROM items WHERE pic IS NOT NULL AND pic != ''"
            ).fetchone()[0]
            cached = conn.execute("SELECT COUNT(*) FROM item_images").fetchone()[0]
        return int(total or 0), int(cached or 0)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    base_id INTEGER PRIMARY KEY,
                    market_id INTEGER,
                    oid INTEGER,
                    object_id INTEGER,
                    object_name TEXT NOT NULL,
                    pic TEXT,
                    grade INTEGER,
                    primary_class TEXT,
                    second_class TEXT,
                    second_class_cn TEXT,
                    latest_price INTEGER,
                    price_update_time INTEGER,
                    price_start INTEGER,
                    day_change REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS item_aliases (
                    alias TEXT PRIMARY KEY,
                    base_id INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS item_images (
                    url TEXT PRIMARY KEY,
                    local_path TEXT NOT NULL,
                    fetched_at REAL NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _aliases(item: Any) -> set[str]:
    aliases = {_normalize_alias(item.object_name)}
    for prefix, value in (
        ("base", item.base_id),
        ("market", item.market_id),
        ("oid", item.oid),
        ("object", item.object_id),
    ):
        if value is not None:
            aliases.add(f"{prefix}:{value}")
    return {alias for alias in aliases if alias}


def _normalize_alias(value: object) -> str:
    return str(value or "").strip().lower()
