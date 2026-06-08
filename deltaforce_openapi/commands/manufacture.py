from __future__ import annotations

from typing import Any

from ..api_client import DeltaForceApiClient
from ..errors import DeltaForceUpstreamError, DeltaForceUserError
from ..renderer import RenderDocument, RenderItem, RenderSection, first_text, money, number


TYPES = {
    "1": "技术中心",
    "2": "工作台",
    "3": "制药台",
    "4": "防具台",
}

LEVELS = {
    "1": "等级1",
    "2": "等级2",
    "3": "等级3",
}

SORTS = {
    "": ("price_hour", "小时收益"),
    "小时": ("price_hour", "小时收益"),
    "小时收益": ("price_hour", "小时收益"),
    "总": ("price", "总收益"),
    "总收益": ("price", "总收益"),
}

HELP = """特勤处制造用法
特勤处制造 <t> [l] [小时收益|总收益]
t：1技术中心 2工作台 3制药台 4防具台
l：1等级1 2等级2 3等级3，默认等级3
排序：默认小时收益，也可使用总收益"""


async def render(client: DeltaForceApiClient, raw_t: str, raw_l: str = "", raw_sort: str = "") -> RenderDocument:
    t = raw_t.strip()
    l = raw_l.strip()
    sort_text = raw_sort.strip()
    if l and l not in LEVELS and not sort_text:
        sort_text = l
        l = ""
    l = l or "3"
    sort_key, sort_label = _resolve_sort(sort_text)
    if t == "0":
        return _help_document()
    if t not in TYPES or l not in LEVELS:
        raise DeltaForceUserError("参数错误：请使用“特勤处制造 0”查看帮助")

    payload = await client.get(
        "manufacturePro",
        {"t": int(t), "l": int(l)},
        ttl_seconds=client.config.manufacture_cache_seconds,
    )
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")

    typed_rows = [row for row in rows if isinstance(row, dict)]
    typed_rows.sort(key=lambda row: _to_int(row.get(sort_key)), reverse=True)

    if not typed_rows:
        return RenderDocument(
            title=f"特勤处制造：{TYPES[t]} {LEVELS[l]}",
            summary=f"已查询{TYPES[t]} {LEVELS[l]}制造收益，当前暂无数据。",
            sections=(RenderSection(title="制造收益", lines=("暂无数据",)),),
        )

    items: list[RenderItem] = []
    for idx, row in enumerate(typed_rows[: client.config.result_limit], start=1):
        items.append(
            RenderItem(
                name=first_text(row.get("name")),
                image_url=str(row.get("pic") or ""),
                fields=(
                    ("每小时", money(row.get("price_hour"))),
                    ("到手", money(row.get("price"))),
                    ("手续费", money(row.get("sxf"))),
                    ("时长", f"{number(row.get('period'))}h"),
                    ("解锁", number(row.get("unlockLevel"))),
                    ("分类", first_text(row.get("secondClassCN"), "")),
                ),
                rank=str(idx),
            )
        )
    return RenderDocument(
        title=f"特勤处制造：{TYPES[t]} {LEVELS[l]}",
        summary=f"已查询{TYPES[t]} {LEVELS[l]}制造收益，图片按{sort_label}排序。",
        sections=(RenderSection(title=f"制造收益：{sort_label}", items=tuple(items)),),
    )


def _to_int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return -10**18


def _resolve_sort(raw_sort: str) -> tuple[str, str]:
    if raw_sort in SORTS:
        return SORTS[raw_sort]
    if raw_sort:
        raise DeltaForceUserError("参数错误：排序只能用“小时收益”或“总收益”")
    return SORTS[""]


def _help_document() -> RenderDocument:
    return RenderDocument(
        title="特勤处制造用法",
        summary="特勤处制造帮助已生成，按图片中的参数发送命令。",
        sections=(RenderSection(title="参数", lines=tuple(HELP.splitlines()[1:])),),
    )
