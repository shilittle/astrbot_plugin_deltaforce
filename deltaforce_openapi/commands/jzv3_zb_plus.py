from __future__ import annotations

from typing import Any

from ..api_client import DeltaForceApiClient
from ..errors import DeltaForceUpstreamError, DeltaForceUserError
from ..renderer import RenderBundle, RenderDocument, RenderItem, RenderSection, first_text, money


LEVELS = {
    "1": (0, "11W 机密配置"),
    "2": (1, "18W 机密配置"),
    "3": (2, "55W 绝密巴克什"),
    "4": (3, "60W 绝密航天"),
    "5": (4, "24W 适应监狱"),
    "6": (5, "78W 绝密监狱"),
}

PREFERENCES = {
    "": "均衡套装",
    "均衡": "均衡套装",
    "均衡套装": "均衡套装",
    "枪": "枪械优先",
    "枪优先": "枪械优先",
    "枪械优先": "枪械优先",
    "胸挂": "胸挂优先",
    "胸挂优先": "胸挂优先",
}

HELP = """卡战备用法
卡战备 1 [均衡|枪优先|胸挂优先]：11W 机密配置
卡战备 2 [均衡|枪优先|胸挂优先]：18W 机密配置
卡战备 3 [均衡|枪优先|胸挂优先]：55W 绝密巴克什
卡战备 4 [均衡|枪优先|胸挂优先]：60W 绝密航天
卡战备 5 [均衡|枪优先|胸挂优先]：24W 适应监狱
卡战备 6 [均衡|枪优先|胸挂优先]：78W 绝密监狱"""


async def render(client: DeltaForceApiClient, raw_level: str, raw_preference: str = "") -> RenderDocument | RenderBundle:
    level = raw_level.strip()
    if level == "0":
        return _help_document()
    if level not in LEVELS:
        raise DeltaForceUserError("参数错误：请使用“卡战备 0”查看帮助")
    preference = PREFERENCES.get(raw_preference.strip())
    if preference is None:
        raise DeltaForceUserError("参数错误：卡战备偏好只能用“均衡”“枪优先”“胸挂优先”")

    lv, label = LEVELS[level]
    payload = await client.get(
        "jzv3_zb_plus",
        {"lv": lv},
        ttl_seconds=client.config.card_cache_seconds,
    )
    root = payload.get("data")
    if not isinstance(root, dict):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")
    rows = root.get("data")
    if not isinstance(rows, list):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")

    meta = [f"档位：{label}"]
    updated_at = first_text(root.get("time"), "")
    if updated_at:
        meta.append(f"更新时间：{updated_at}")
    if not rows:
        return RenderDocument(
            title=f"卡战备：{label}",
            summary=f"已查询{label}，当前暂无数据。",
            meta=tuple(meta),
            sections=(RenderSection(title="方案", lines=("暂无数据",)),),
        )

    documents: list[RenderDocument] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_name = first_text(row.get("name"))
        item_rows = _item_rows(row.get("data"))
        title = f"{row_name}：{label}"
        lines = (
            f"总价：{money(row.get('price'))}",
            f"战备：{money(row.get('jz'))}",
            f"节省：{_saving_money(row.get('cz'))}",
            f"物品数：{len(item_rows)}",
        )
        items: list[RenderItem] = []
        for item in item_rows:
            fields = [
                ("战备值", _battle_value_money(item)),
            ]
            if _is_exchange_item(item):
                fields.extend(
                    [
                        ("兑换价格", money(item.get("price"))),
                        ("兑换节省", _saving_money(item.get("jz"))),
                    ]
                )
                fields.extend(_exchange_fields(item))
            else:
                fields.extend(
                    [
                        ("购买价格", money(item.get("price"))),
                        ("购买节省", _saving_money(item.get("jz"))),
                    ]
                )
            items.append(
                RenderItem(
                    name=first_text(item.get("name")),
                    image_url=str(item.get("pic") or ""),
                    fields=tuple(fields),
                )
            )
        documents.append(
            RenderDocument(
                title=title,
                summary=f"已查询{label}卡战备：{_preference_label(row_name)}，图片中展示该方案全部物品。",
                meta=tuple(meta),
                sections=(RenderSection(title=row_name, lines=lines, items=tuple(items)),),
            )
        )
    if not documents:
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")
    selected = _select_document(documents, preference)
    return RenderBundle(selected=selected, cache_documents=tuple(documents))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _item_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _collect_item_rows(value, rows)
    return rows


def _collect_item_rows(value: Any, rows: list[dict[str, Any]]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_item_rows(item, rows)
        return
    if not isinstance(value, dict):
        return
    if _looks_like_item(value):
        rows.append(value)
        return

    nested_keys = ("data", "items", "list", "rows", "children")
    nested_values = [value[key] for key in nested_keys if key in value]
    if not nested_values:
        nested_values = [item for item in value.values() if isinstance(item, (dict, list))]
    for item in nested_values:
        _collect_item_rows(item, rows)


def _looks_like_item(value: dict[str, Any]) -> bool:
    if not first_text(value.get("name")):
        return False
    return any(key in value for key in ("pic", "price", "jz", "id", "type"))


def _is_exchange_item(item: dict[str, Any]) -> bool:
    return bool(str(item.get("exchange") or "").strip())


def _battle_value_money(item: dict[str, Any]) -> str:
    price = _to_int(item.get("price"))
    delta = _to_int(item.get("jz"))
    if price is None or delta is None:
        return "未知"
    return money(price - delta)


def _saving_money(value: object) -> str:
    delta = _to_int(value)
    if delta is None:
        return "未知"
    return money(-delta)


def _to_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _exchange_fields(item: dict[str, Any]) -> list[tuple[str, str]]:
    exchange = str(item.get("exchange") or "").strip()
    exchange_plus = item.get("exchange_plus")
    if not exchange or not isinstance(exchange_plus, dict):
        return []
    purchase_count = first_text(exchange_plus.get("purchaseCount"), "未知")
    purchase_duration = first_text(exchange_plus.get("purchaseDuration"), "未知")
    return [
        ("限购", purchase_count),
        ("刷新", purchase_duration),
    ]


def _select_document(documents: list[RenderDocument], preference: str) -> RenderDocument:
    for document in documents:
        if document.title.startswith(preference):
            return document
    if preference == "均衡套装":
        for document in documents:
            if "均衡" in document.title:
                return document
    return documents[0]


def _preference_label(row_name: str) -> str:
    if "枪" in row_name:
        return "枪优先"
    if "胸挂" in row_name:
        return "胸挂优先"
    if "均衡" in row_name:
        return "均衡"
    return row_name


def _help_document() -> RenderDocument:
    return RenderDocument(
        title="卡战备用法",
        summary="卡战备帮助已生成，按图片中的档位发送命令。",
        sections=(RenderSection(title="可用档位", lines=tuple(HELP.splitlines()[1:])),),
    )
