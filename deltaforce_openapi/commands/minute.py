from __future__ import annotations

from typing import Any

from ..api_client import DeltaForceApiClient
from ..errors import DeltaForceUpstreamError, DeltaForceUserError
from ..item_overview import ItemOverviewStore, OverviewQueryResult, SORT_LABELS, format_time
from ..item_store import ItemStore
from ..renderer import RenderDocument, RenderItem, RenderSection, first_text, money, trend_summary


HELP = """交易行价格用法
交易行价格 <物品名>
价格 <物品名>
物价 <物品名>
价格曲线 <物品名>
交易行价格 总览：查看物品总览筛选项
交易行价格 总览 <一级分类> [二级分类] [排序] [等级]
交易行总览 <一级分类> [二级分类] [排序] [等级]
物品总览 <一级分类> [二级分类] [排序] [等级]"""


async def render(client: DeltaForceApiClient, store: ItemStore, keyword: str) -> RenderDocument:
    keyword = keyword.strip()
    if keyword == "0":
        return help_document()
    if not keyword:
        raise DeltaForceUserError("参数错误：请使用“交易行价格 0”查看帮助")

    matches = await store.search(keyword, limit=max(client.config.result_limit, 5))
    if not matches:
        raise DeltaForceUserError("查询失败：未找到匹配物品")

    item = next((record for record in matches if record.market_id), matches[0])
    if not item.market_id:
        raise DeltaForceUserError("查询失败：该物品没有已确认的交易行 ID")

    payload = await client.get(
        "minute",
        {"id": item.market_id, "isZb": 1},
        ttl_seconds=client.config.minute_cache_seconds,
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")

    times = _as_list(data.get("a"))
    prices = _as_list(data.get("b"))
    zbs = _as_list(data.get("zb"))
    latest_idx = _latest_index(prices)
    if latest_idx is None:
        raise DeltaForceUpstreamError("查询失败：上游价格数据为空")

    meta: list[str] = []
    if len(matches) > 1:
        alternatives = "、".join(match.object_name for match in matches[1:4])
        if alternatives:
            meta.append(f"其他匹配：{alternatives}")
    fields = [("最新价", money(prices[latest_idx]))]
    if latest_idx < len(times):
        fields.append(("时间", first_text(times[latest_idx])))
    if latest_idx < len(zbs) and zbs[latest_idx] not in (None, ""):
        fields.append(("战备值", money(zbs[latest_idx])))
    fields.append(("趋势", trend_summary(prices).replace("24h趋势：", "")))
    if item.second_class_cn:
        fields.append(("分类", item.second_class_cn))
    return RenderDocument(
        title=f"交易行价格：{item.object_name}",
        summary=f"已查询{item.object_name}价格，图片内包含最新价和趋势摘要。",
        meta=tuple(meta),
        sections=(
            RenderSection(
                title="价格摘要",
                items=(
                    RenderItem(
                        name=item.object_name,
                        image_url=item.pic,
                        fields=tuple(fields),
                    ),
                ),
            ),
        ),
    )


async def render_overview(
    client: DeltaForceApiClient,
    overview_store: ItemOverviewStore,
    raw_args: str,
) -> RenderDocument:
    args = raw_args.strip().split()
    if not args:
        return await _overview_filter_document(overview_store)
    result = await overview_store.query(args)
    return _overview_result_document(client, result)


def help_document() -> RenderDocument:
    return RenderDocument(
        title="交易行查询用法",
        summary="交易行查询帮助已生成，价格查询和物品总览都在图片中列出。",
        sections=(RenderSection(title="命令", lines=tuple(HELP.splitlines()[1:])),),
    )


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _latest_index(values: list[Any]) -> int | None:
    for idx in range(len(values) - 1, -1, -1):
        if values[idx] not in (None, ""):
            return idx
    return None


async def _overview_filter_document(overview_store: ItemOverviewStore) -> RenderDocument:
    filters, updated_at = await overview_store.get_filters()
    lines: list[str] = []
    for item in filters:
        label = first_text(item.get("label"), "")
        children = [child for child in item.get("children", []) if isinstance(child, dict)]
        child_labels = "、".join(first_text(child.get("label"), "") for child in children[:8])
        if len(children) > 8:
            child_labels += " ..."
        lines.append(f"{label}：{child_labels or '无二级筛选'}")
    return RenderDocument(
        title="交易行物品总览",
        summary="已查询物品总览筛选项，按图片示例继续查询具体分类。",
        meta=(
            f"筛选项更新时间：{format_time(updated_at)}",
            "示例：交易行价格 总览 钥匙 零号大坝 2-2 6",
        ),
        sections=(RenderSection(title="可用筛选项", lines=tuple(lines)),),
    )


def _overview_result_document(client: DeltaForceApiClient, result: OverviewQueryResult) -> RenderDocument:
    grade_text = f" 等级{result.grade}" if result.grade is not None else ""
    title = f"物品总览：{result.key1}/{result.key2}{grade_text}"
    meta = [
        f"排序：{result.sort} {SORT_LABELS.get(result.sort, '')}".strip(),
        f"查询时间：{format_time(result.updated_at)}",
        f"筛选项更新时间：{format_time(result.filter_updated_at)}",
    ]
    if result.count is not None:
        meta.append(f"匹配数量：{result.count}")
    items: list[RenderItem] = []
    for row in result.rows[: client.config.result_limit]:
        fields = [
            ("等级", first_text(row.get("grade"))),
            ("价格", money(row.get("price"))),
            ("今日涨跌", first_text(row.get("bl"))),
            ("7日价格", money(row.get("day_7_price"))),
            ("30日价格", money(row.get("day_30_price"))),
        ]
        sell_type = _shop_sell_type(row.get("ShopSellType"))
        if sell_type:
            fields.append(("推荐出售", sell_type))
        items.append(
            RenderItem(
                name=first_text(row.get("name")),
                image_url=str(row.get("pic") or ""),
                fields=tuple(fields),
            )
        )
    if not items:
        return RenderDocument(
            title=title,
            summary=f"已查询{result.key1}/{result.key2}物品总览，当前没有匹配数据。",
            meta=tuple(meta),
            sections=(RenderSection(title="物品", lines=("暂无数据",)),),
        )
    return RenderDocument(
        title=title,
        summary=f"已查询{result.key1}/{result.key2}物品总览，图片展示最新结果。",
        meta=tuple(meta),
        sections=(RenderSection(title="物品", items=tuple(items)),),
    )


def _shop_sell_type(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return ""
    method = first_text(value[0], "")
    grade = first_text(value[1], "") if len(value) >= 2 else ""
    instant = money(value[2]) if len(value) >= 3 else ""
    parts = [method]
    if grade:
        parts.append(f"推荐等级{grade}")
    if instant:
        parts.append(f"秒出价{instant}")
    return " ".join(part for part in parts if part)
