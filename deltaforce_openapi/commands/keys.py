from __future__ import annotations

import asyncio
from typing import Any

from ..api_client import DeltaForceApiClient
from ..errors import DeltaForceUserError
from ..renderer import RenderDocument, RenderItem, RenderSection, first_text, money


MAPS = {
    1: "零号大坝",
    2: "航天基地",
    3: "长弓溪谷",
    4: "巴克什",
    5: "潮汐监狱",
}

MODES = {
    "1": ("keys_day", "今日钥匙卡低价预测"),
    "2": ("keys_day_yc", "明日钥匙卡低价预测"),
}

HELP = """钥匙卡分析用法
钥匙卡分析 1：今日钥匙卡低价预测
钥匙卡分析 2：明日钥匙卡低价预测"""


async def render(client: DeltaForceApiClient, raw_mode: str) -> RenderDocument:
    mode = raw_mode.strip()
    if mode == "0":
        return _help_document()
    if mode not in MODES:
        raise DeltaForceUserError("参数错误：请使用“钥匙卡分析 0”查看帮助")

    endpoint, title = MODES[mode]
    ttl = client.config.map_cache_seconds if endpoint == "keys_day" else client.config.conservative_cache_seconds
    tasks = [
        client.get(endpoint, {"mid": mid}, ttl_seconds=ttl)
        for mid in MAPS
    ]
    payloads = await asyncio.gather(*tasks)

    sections: list[RenderSection] = []
    for mid, payload in zip(MAPS, payloads, strict=True):
        entries = _collect_entries(payload.get("data"), mid)
        if not entries:
            sections.append(RenderSection(title=MAPS[mid], lines=("暂无数据",)))
            continue
        items: list[RenderItem] = []
        for item in entries[: client.config.result_limit]:
            items.append(
                RenderItem(
                    name=first_text(item.get("name")),
                    image_url=str(item.get("pic") or ""),
                    fields=(
                        ("等级", first_text(item.get("grade"))),
                        ("价格", money(item.get("price"))),
                    ),
                )
            )
        sections.append(RenderSection(title=MAPS[mid], items=tuple(items)))
    return RenderDocument(
        title=f"钥匙卡分析：{title}",
        summary=f"已查询{title}，图片内按地图分组展示钥匙卡。",
        sections=tuple(sections),
    )


def _collect_entries(value: Any, mid: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _walk_items(value):
        if not isinstance(item, dict):
            continue
        item_mid = item.get("mid")
        if item_mid not in (None, mid):
            continue
        key = str(item.get("id") or item.get("oid") or item.get("name"))
        if not key or key in seen:
            continue
        if not {"name", "grade", "price"}.issubset(item.keys()):
            continue
        seen.add(key)
        entries.append(item)
    return entries


def _walk_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        found: list[Any] = []
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("data"), list):
                found.extend(_walk_items(item["data"]))
            else:
                found.append(item)
        return found
    return []


def _help_document() -> RenderDocument:
    return RenderDocument(
        title="钥匙卡分析用法",
        summary="钥匙卡分析帮助已生成，按图片中的模式发送命令。",
        sections=(RenderSection(title="模式", lines=tuple(HELP.splitlines()[1:])),),
    )
