from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api_client import DeltaForceApiClient
from .errors import DeltaForceUpstreamError, DeltaForceUserError


SORT_LABELS = {
    "1": "今日涨跌从小到大",
    "1-1": "今日涨跌从小到大",
    "1-2": "今日涨跌从大到小",
    "2-1": "金额从小到大",
    "2-2": "金额从大到小",
    "3-1": "价值从小到大",
    "3-2": "价值从大到小",
    "5-1": "3天涨跌排序",
    "5-2": "3天涨跌排序",
    "7-1": "7天涨跌排序",
    "7-2": "7天涨跌排序",
    "30-1": "30天涨跌排序",
    "30-2": "30天涨跌排序",
}


@dataclass(slots=True)
class OverviewQueryResult:
    key1: str
    key2: str
    sort: str
    grade: int | None
    count: int | None
    rows: list[dict[str, Any]]
    updated_at: float
    filter_updated_at: float


class ItemOverviewStore:
    def __init__(self, client: DeltaForceApiClient, root_dir: Path) -> None:
        self.client = client
        self.cache_dir = root_dir / "cache" / "overview"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._filter_data: list[dict[str, Any]] | None = None
        self._filter_updated_at = 0.0
        self._lock = asyncio.Lock()

    async def get_filters(self) -> tuple[list[dict[str, Any]], float]:
        async with self._lock:
            if self._filter_data and self._is_fresh(self._filter_updated_at, self.client.config.overview_key_cache_seconds):
                return self._filter_data, self._filter_updated_at

            disk = self._read_json(self.cache_dir / "filters.json")
            if isinstance(disk, dict):
                data = disk.get("data")
                fetched_at = _to_float(disk.get("fetched_at")) or 0.0
                if isinstance(data, list) and self._is_fresh(fetched_at, self.client.config.overview_key_cache_seconds):
                    self._filter_data = [item for item in data if isinstance(item, dict)]
                    self._filter_updated_at = fetched_at
                    return self._filter_data, self._filter_updated_at

            payload = await self.client.get(
                "item_list_pro_key",
                ttl_seconds=self.client.config.overview_key_cache_seconds,
            )
            data = payload.get("data")
            if not isinstance(data, list):
                raise DeltaForceUpstreamError("查询失败：筛选项格式异常")
            self._filter_data = [item for item in data if isinstance(item, dict)]
            self._filter_updated_at = time.time()
            self._write_json(
                self.cache_dir / "filters.json",
                {"fetched_at": self._filter_updated_at, "data": self._filter_data},
            )
            return self._filter_data, self._filter_updated_at

    async def query(self, args: list[str]) -> OverviewQueryResult:
        filters, filter_updated_at = await self.get_filters()
        key1 = self._resolve_key1(filters, args[0] if args else "全部")
        key2 = self._resolve_key2(key1, args[1] if len(args) >= 2 else "")
        sort = args[2] if len(args) >= 3 else "2-2"
        if sort not in SORT_LABELS:
            raise DeltaForceUserError("参数错误：交易行总览排序参数不正确")
        grade = self._resolve_grade(args[3] if len(args) >= 4 else "")

        params: dict[str, Any] = {
            "key1": str(key1.get("label") or ""),
            "key2": str(key2.get("label") or ""),
            "sort": sort,
        }
        if grade is not None:
            params["grade"] = grade

        disk_path = self.cache_dir / f"query_{self._params_digest(params)}.json"
        disk = self._read_json(disk_path)
        if isinstance(disk, dict):
            fetched_at = _to_float(disk.get("fetched_at")) or 0.0
            payload = disk.get("payload")
            if isinstance(payload, dict) and self._is_fresh(fetched_at, self.client.config.overview_cache_seconds):
                return self._build_result(params, payload, fetched_at, filter_updated_at)

        payload = await self.client.get(
            "item_list_pro",
            params,
            ttl_seconds=self.client.config.overview_cache_seconds,
        )
        fetched_at = time.time()
        self._write_json(disk_path, {"fetched_at": fetched_at, "params": params, "payload": payload})
        return self._build_result(params, payload, fetched_at, filter_updated_at)

    def _resolve_key1(self, filters: list[dict[str, Any]], label: str) -> dict[str, Any]:
        target = label.strip() or "全部"
        for item in filters:
            if str(item.get("label") or "") == target:
                return item
        raise DeltaForceUserError("参数错误：交易行总览一级筛选不存在")

    def _resolve_key2(self, key1: dict[str, Any], label: str) -> dict[str, Any]:
        children = [item for item in key1.get("children", []) if isinstance(item, dict)]
        if not children:
            raise DeltaForceUserError("参数错误：交易行总览二级筛选不存在")
        target = label.strip() or "全部"
        for item in children:
            if str(item.get("label") or "") == target:
                return item
        raise DeltaForceUserError("参数错误：交易行总览二级筛选不存在")

    def _resolve_grade(self, raw: str) -> int | None:
        if not raw:
            return None
        try:
            grade = int(raw)
        except ValueError as exc:
            raise DeltaForceUserError("参数错误：交易行总览等级必须是0到6") from exc
        if grade < 0 or grade > 6:
            raise DeltaForceUserError("参数错误：交易行总览等级必须是0到6")
        return grade

    def _build_result(
        self,
        params: dict[str, Any],
        payload: dict[str, Any],
        fetched_at: float,
        filter_updated_at: float,
    ) -> OverviewQueryResult:
        data = payload.get("data")
        if not isinstance(data, list):
            raise DeltaForceUpstreamError("查询失败：物品总览格式异常")
        rows = [item for item in data if isinstance(item, dict)]
        count_raw = payload.get("count")
        count = int(count_raw) if isinstance(count_raw, int) else None
        return OverviewQueryResult(
            key1=str(params.get("key1") or ""),
            key2=str(params.get("key2") or ""),
            sort=str(params.get("sort") or ""),
            grade=params.get("grade") if isinstance(params.get("grade"), int) else None,
            count=count,
            rows=rows,
            updated_at=fetched_at,
            filter_updated_at=filter_updated_at,
        )

    def _params_digest(self, params: dict[str, Any]) -> str:
        raw = json.dumps(params, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def _read_json(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _is_fresh(self, fetched_at: float, ttl_seconds: int | float) -> bool:
        return fetched_at > 0 and time.time() - fetched_at < float(ttl_seconds)


def format_time(timestamp: float) -> str:
    if timestamp <= 0:
        return "未知"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def _to_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
