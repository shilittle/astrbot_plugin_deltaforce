from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from ..api_client import DeltaForceApiClient
from ..errors import DeltaForceUserError
from ..renderer import RenderDocument, RenderItem, RenderSection, first_text, money


MODES = {
    "1": ("ammo_pack", "子弹自选包收益"),
    "2": ("ammo_day", "今日倒子弹低价预测"),
    "3": ("ammo_zr_yc", "昨日倒子弹最高收益"),
}

HELP = """子弹分析用法
子弹分析 1：子弹自选包收益
子弹分析 2：今日倒子弹低价预测
子弹分析 3：昨日倒子弹最高收益"""


async def render(client: DeltaForceApiClient, raw_mode: str) -> RenderDocument:
    mode = raw_mode.strip()
    if mode == "0":
        return _help_document()
    if mode not in MODES:
        raise DeltaForceUserError("参数错误：请使用“子弹分析 0”查看帮助")

    endpoint, title = MODES[mode]
    payloads = await asyncio.gather(
        *[
            client.get(endpoint, {"grade": grade}, ttl_seconds=client.config.conservative_cache_seconds)
            for grade in range(7)
        ]
    )

    if endpoint == "ammo_pack":
        return _render_pack(title, payloads, client.config.result_limit)
    return _render_day(title, payloads, client.config.result_limit)


def _render_pack(title: str, payloads: list[dict[str, Any]], limit: int) -> RenderDocument:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for payload in payloads:
        data = payload.get("data")
        if not isinstance(data, dict):
            continue
        for group_name, items in data.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or not {"name", "grade", "price"}.issubset(item.keys()):
                    continue
                key = (str(group_name), str(item.get("id") or item.get("name")))
                if key in seen:
                    continue
                seen.add(key)
                groups[str(group_name)].append(item)

    if not groups:
        return RenderDocument(
            title=f"子弹分析：{title}",
            summary=f"已查询{title}，当前暂无数据。",
            sections=(RenderSection(title="子弹", lines=("暂无数据",)),),
        )
    sections: list[RenderSection] = []
    for group_name, items in groups.items():
        render_items: list[RenderItem] = []
        for idx, item in enumerate(items[:limit], start=1):
            render_items.append(
                RenderItem(
                    name=first_text(item.get("name")),
                    image_url=str(item.get("pic") or ""),
                    fields=(
                        ("价格", money(item.get("price"))),
                        ("等级", first_text(item.get("grade"))),
                        ("收益", money(item.get("sy_price"))),
                        ("数量", first_text(item.get("num"))),
                    ),
                    rank=str(idx),
                )
            )
        sections.append(RenderSection(title=group_name, items=tuple(render_items)))
    return RenderDocument(
        title=f"子弹分析：{title}",
        summary=f"已查询{title}，图片内按自选包分组展示收益。",
        sections=tuple(sections),
    )


def _render_day(title: str, payloads: list[dict[str, Any]], limit: int) -> RenderDocument:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in payloads:
        for item in _walk_items(payload.get("data")):
            if not isinstance(item, dict) or not {"name", "grade", "price"}.issubset(item.keys()):
                continue
            key = str(item.get("id") or item.get("oid") or item.get("name"))
            if key in seen:
                continue
            seen.add(key)
            entries.append(item)

    if not entries:
        return RenderDocument(
            title=f"子弹分析：{title}",
            summary=f"已查询{title}，当前暂无已确认可展示数据。",
            sections=(RenderSection(title="子弹", lines=("暂无已确认可展示数据",)),),
        )
    items: list[RenderItem] = []
    for idx, item in enumerate(entries[:limit], start=1):
        items.append(
            RenderItem(
                name=first_text(item.get("name")),
                image_url=str(item.get("pic") or ""),
                fields=(
                    ("价格", money(item.get("price"))),
                    ("等级", first_text(item.get("grade"))),
                ),
                rank=str(idx),
            )
        )
    return RenderDocument(
        title=f"子弹分析：{title}",
        summary=f"已查询{title}，图片内展示可确认字段。",
        sections=(RenderSection(title="子弹", items=tuple(items)),),
    )


def _walk_items(value: Any) -> list[Any]:
    if isinstance(value, list):
        found: list[Any] = []
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("data"), list):
                found.extend(_walk_items(item["data"]))
            else:
                found.append(item)
        return found
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_walk_items(item))
        return found
    return []


def _help_document() -> RenderDocument:
    return RenderDocument(
        title="子弹分析用法",
        summary="子弹分析帮助已生成，按图片中的模式发送命令。",
        sections=(RenderSection(title="模式", lines=tuple(HELP.splitlines()[1:])),),
    )
