from __future__ import annotations

from typing import Any

from ..api_client import DeltaForceApiClient
from ..cache import seconds_until_next_local_time
from ..errors import DeltaForceUpstreamError
from ..renderer import RenderDocument, RenderSection, first_text


MAP_FIELDS = [
    ("a", "零号大坝"),
    ("b", "长弓溪谷"),
    ("c", "巴克什"),
    ("d", "航天基地"),
    ("e", "潮汐监狱"),
]


async def render(client: DeltaForceApiClient) -> RenderDocument:
    ttl = seconds_until_next_local_time(
        client.config.map_refresh_hour,
        client.config.map_refresh_minute,
        minimum=60,
    )
    payload = await client.get("map_pwd", ttl_seconds=ttl)
    data = payload.get("data")
    if not isinstance(data, dict):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")

    lines: list[str] = []
    for key, map_name in MAP_FIELDS:
        pair = data.get(key)
        password, date_text = _extract_pair(pair)
        if password == "-":
            lines.append(f"{map_name}：未更新")
        elif date_text:
            lines.append(f"{map_name}：{password}（{date_text}）")
        else:
            lines.append(f"{map_name}：{password}")
    return RenderDocument(
        title="每日密码",
        summary="已查询今日地图密码，图片内按地图列出密码。",
        sections=(RenderSection(title="地图密码", lines=tuple(lines)),),
    )


def _extract_pair(value: Any) -> tuple[str, str]:
    if isinstance(value, list):
        password = first_text(value[0], "-") if len(value) >= 1 else "-"
        date_text = first_text(value[1], "") if len(value) >= 2 else ""
        return password, date_text
    return "-", ""
