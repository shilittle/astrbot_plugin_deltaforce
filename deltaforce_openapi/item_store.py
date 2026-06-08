from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .api_client import DeltaForceApiClient
from .errors import DeltaForceUpstreamError, DeltaForceUserError
from .item_database import ItemDatabase


@dataclass(slots=True)
class ItemRecord:
    base_id: int
    market_id: int | None
    oid: int | None
    object_id: int | None
    object_name: str
    pic: str
    grade: int | None
    primary_class: str
    second_class: str
    second_class_cn: str
    latest_price: int | None = None
    price_update_time: int | None = None
    price_start: int | None = None
    day_change: float | None = None


class ItemStore:
    def __init__(self, client: DeltaForceApiClient) -> None:
        self.client = client
        self.database = ItemDatabase(client.config.root_dir / "cache" / "item_db.sqlite3")
        self._items: list[ItemRecord] = []
        self._by_market_id: dict[int, ItemRecord] = {}
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def initialize(self, force: bool = False) -> None:
        async with self._lock:
            now = time.monotonic()
            if not force and self._items and now - self._loaded_at < self.client.config.item_cache_seconds:
                return
            info_payload = await self.client.get(
                "item_info_all",
                ttl_seconds=self.client.config.item_cache_seconds,
            )
            price_payload = await self.client.get(
                "item_price_all",
                {"isZb": 0},
                ttl_seconds=self.client.config.item_cache_seconds,
            )
            self._build(info_payload, price_payload)
            self._loaded_at = now

    async def ensure_ready(self) -> None:
        if not self._items:
            await self.initialize()

    def _build(self, info_payload: dict[str, Any], price_payload: dict[str, Any]) -> None:
        info_items = info_payload.get("data")
        price_items = price_payload.get("data")
        if not isinstance(info_items, list) or not isinstance(price_items, list):
            raise DeltaForceUpstreamError("查询失败：基础数据格式异常")

        price_by_tid: dict[int, dict[str, Any]] = {}
        for raw in price_items:
            if not isinstance(raw, dict):
                continue
            tid = _to_int(raw.get("tid"))
            if tid is not None:
                price_by_tid[tid] = raw

        items: list[ItemRecord] = []
        by_market_id: dict[int, ItemRecord] = {}
        for raw in info_items:
            if not isinstance(raw, dict):
                continue
            base_id = _to_int(raw.get("id"))
            name = str(raw.get("objectName") or "").strip()
            if base_id is None or not name:
                continue
            price = price_by_tid.get(base_id, {})
            market_id = _to_int(price.get("id")) or _to_int(raw.get("oid"))
            record = ItemRecord(
                base_id=base_id,
                market_id=market_id,
                oid=_to_int(raw.get("oid")),
                object_id=_to_int(raw.get("objectID")),
                object_name=name,
                pic=str(raw.get("pic") or "").strip(),
                grade=_to_int(raw.get("grade")),
                primary_class=str(raw.get("primaryClass") or ""),
                second_class=str(raw.get("secondClass") or ""),
                second_class_cn=str(raw.get("secondClassCN") or ""),
                latest_price=_to_int(price.get("price")),
                price_update_time=_to_int(price.get("is_get_time")),
                price_start=_to_int(price.get("price_start")),
                day_change=_to_float(price.get("bl")),
            )
            items.append(record)
            if market_id is not None and market_id > 0:
                by_market_id[market_id] = record

        if not items:
            raise DeltaForceUpstreamError("查询失败：基础数据为空")
        self._items = items
        self._by_market_id = by_market_id
        self.database.upsert_items(items)

    async def search(self, keyword: str, limit: int | None = None) -> list[ItemRecord]:
        await self.ensure_ready()
        keyword = keyword.strip()
        if not keyword:
            raise DeltaForceUserError("参数错误：请使用“交易行价格 0”查看帮助")
        needle = keyword.lower()
        scored: list[tuple[tuple[int, int, int, str], ItemRecord]] = []
        for item in self._items:
            haystacks = [
                item.object_name,
                item.primary_class,
                item.second_class,
                item.second_class_cn,
            ]
            exact = item.object_name == keyword
            contains = any(needle in h.lower() for h in haystacks if h)
            if not exact and not contains:
                continue
            score = (
                0 if exact else 1,
                0 if item.latest_price is not None else 1,
                len(item.object_name),
                item.object_name,
            )
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0])
        return [item for _, item in scored[: limit or self.client.config.result_limit]]


def _to_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
