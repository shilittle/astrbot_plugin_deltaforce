from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Mapping
from urllib.parse import unquote

from ..api_client import DeltaForceApiClient
from ..errors import DeltaForceUpstreamError, DeltaForceUserError
from ..player_auth import PlayerAuthRecord, PlayerAuthStore
from ..renderer import RenderDocument, RenderItem, RenderSection, first_text, money, number


ACCOUNT_TYPES = {
    "": "0",
    "0": "0",
    "qq": "0",
    "QQ": "0",
    "q": "0",
    "企鹅": "0",
    "1": "1",
    "wx": "1",
    "WX": "1",
    "微信": "1",
    "weixin": "1",
}

ROLE_PARAMS = {
    "iChartId": "317814",
    "iSubChartId": "317814",
    "sIdeToken": "QIRBwm",
    "seasonid": "0",
}

MONEY_PARAMS = {
    "iChartId": "319386",
    "iSubChartId": "319386",
    "sIdeToken": "zMemOt",
    "item": "17020000010",
    "type": "3",
}

BATTLE_PARAMS = {
    "iChartId": "450526",
    "iSubChartId": "450526",
    "sIdeToken": "PHq59Y",
}

ROOM_PARAMS = {
    "iChartId": "450471",
    "iSubChartId": "450471",
    "sIdeToken": "ylP3eG",
    "type": "2",
}

DEFAULT_SEASONS = [1, 2, 3, 4, 5, 6]


async def render_auth_url(client: DeltaForceApiClient, raw_type: str) -> RenderDocument:
    account_type = ACCOUNT_TYPES.get(raw_type.strip())
    if account_type is None or raw_type.strip() in {"0", "帮助", "help"}:
        return _auth_help_document()

    payload = await client.get(
        "player_oauth_url",
        {"typs": account_type},
        ttl_seconds=60,
    )
    auth_url = first_text(payload.get("data"), "")
    if not auth_url.startswith(("http://", "https://")):
        raise DeltaForceUpstreamError("授权失败：上游响应格式异常")
    account_label = "QQ" if account_type == "0" else "微信"
    return RenderDocument(
        title="玩家授权",
        summary=f"授权链接：{auth_url}",
        lines=(
            f"账号类型：{account_label}",
            "登录后复制 404 或白屏页面链接，再发送：三角洲绑定 <回调链接>",
            "建议在私聊中完成授权和绑定。",
        ),
        sections=(
            RenderSection(
                title="下一步",
                lines=(
                    "1. 打开授权链接并登录游戏账号。",
                    "2. 复制登录后出现的 404 或白屏页面完整链接。",
                    "3. 发送：三角洲绑定 <回调链接>。",
                ),
            ),
        ),
    )


async def bind_callback(
    client: DeltaForceApiClient,
    store: PlayerAuthStore,
    user_key: str,
    callback_url: str,
) -> RenderDocument:
    url = callback_url.strip()
    if not url.startswith(("http://", "https://")):
        raise DeltaForceUserError("参数错误：请发送“三角洲绑定 <回调链接>”")

    payload = await client.get(
        "player_oauth_verify",
        {"url": url},
        ttl_seconds=0,
    )
    record = store.put_from_payload(user_key, payload)
    return _bound_document(record, "玩家授权绑定完成，可发送“玩家数据”查询。")


async def refresh_auth(
    client: DeltaForceApiClient,
    store: PlayerAuthStore,
    user_key: str,
) -> RenderDocument:
    record = store.require(user_key)
    payload = await client.get(
        "player_oauth_quid",
        {"quid": record.quid},
        ttl_seconds=0,
    )
    refreshed = store.put_from_payload(user_key, payload)
    return _bound_document(refreshed, "玩家授权已刷新，可继续查询玩家数据。")


async def render_profile(
    client: DeltaForceApiClient,
    store: PlayerAuthStore,
    user_key: str,
    raw_args: str,
) -> RenderDocument:
    args = raw_args.split()
    if args and args[0] in {"0", "帮助", "help"}:
        return _query_help_document()

    resource_type, resource_label, seasons, all_seasons = _parse_profile_args(args)
    record = await _active_record(client, store, user_key)
    cookies = record.cookie_token
    auth_cache_key = f"{user_key}:{record.quid}"
    detail_params = _detail_params(resource_type, seasons, all_seasons)

    role_payload, detail_payload, money_payload = await asyncio.gather(
        client.post_official(
            "player_role",
            ROLE_PARAMS,
            cookies,
            auth_cache_key,
            ttl_seconds=client.config.player_cache_seconds,
        ),
        client.post_official(
            "player_detail",
            detail_params,
            cookies,
            auth_cache_key,
            ttl_seconds=client.config.player_cache_seconds,
        ),
        client.post_official(
            "player_money",
            MONEY_PARAMS,
            cookies,
            auth_cache_key,
            ttl_seconds=client.config.player_cache_seconds,
        ),
    )

    user_data, career_data = _role_data(role_payload)
    detail = _detail_data(detail_payload, resource_type)
    total_money = _money_value(money_payload)
    player_name = _decode_text(user_data.get("charac_name"))
    avatar_url = _decode_text(user_data.get("picurl"), "")
    season_label = "全赛季" if all_seasons else "赛季 " + ",".join(str(item) for item in seasons)

    profile_item = RenderItem(
        name=player_name,
        image_url=avatar_url,
        fields=(
            ("账号类型", _account_label(record.pt)),
            ("哈夫币", money(total_money)),
            ("烽火段位分", first_text(career_data.get("rankpoint"))),
            ("全面段位分", first_text(career_data.get("tdmrankpoint"))),
        ),
    )
    career_item = RenderItem(
        name="基础战绩",
        fields=(
            ("烽火对局", first_text(career_data.get("soltotalfght"))),
            ("烽火撤离", first_text(career_data.get("solttotalescape"))),
            ("烽火撤离率", first_text(career_data.get("solescaperatio"))),
            ("烽火击杀", first_text(career_data.get("soltotalkill"))),
            ("全面对局", first_text(career_data.get("tdmtotalfight"))),
            ("全面胜场", first_text(career_data.get("totalwin"))),
            ("全面胜率", first_text(career_data.get("tdmsuccessratio"))),
            ("全面击杀", first_text(career_data.get("tdmtotalkill"))),
        ),
    )
    detail_item = RenderItem(
        name=f"{resource_label}详情",
        fields=tuple(_detail_fields(detail)),
    )

    return RenderDocument(
        title="玩家数据",
        summary=f"已查询 {player_name} 的玩家数据，图片内包含角色、战绩和哈夫币。",
        meta=(f"范围：{resource_label} / {season_label}", _expire_text(record)),
        sections=(
            RenderSection(title="角色", items=(profile_item,)),
            RenderSection(title="统计", items=(career_item, detail_item), lines=tuple(_map_lines(detail))),
        ),
    )


async def render_battle(
    client: DeltaForceApiClient,
    store: PlayerAuthStore,
    user_key: str,
    raw_args: str,
) -> RenderDocument:
    args = raw_args.split()
    if args and args[0] in {"0", "帮助", "help"}:
        return _query_help_document()

    battle_type, label, page = _parse_battle_args(args)
    record = await _active_record(client, store, user_key)
    payload = await client.post_official(
        "player_battle_v2",
        {**BATTLE_PARAMS, "type": battle_type, "page": page},
        record.cookie_token,
        f"{user_key}:{record.quid}",
        ttl_seconds=client.config.player_cache_seconds,
    )
    rows = _jdata(payload).get("data")
    if not isinstance(rows, list):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")

    items = tuple(_battle_item(row) for row in rows[: client.config.result_limit] if isinstance(row, dict))
    lines = ("暂无战绩",) if not items else ()
    return RenderDocument(
        title=f"玩家战绩：{label}",
        summary=f"已查询玩家{label}第 {page} 页战绩。",
        meta=(_expire_text(record),),
        sections=(RenderSection(title="近期对局", lines=lines, items=items),),
    )


async def render_room(
    client: DeltaForceApiClient,
    store: PlayerAuthStore,
    user_key: str,
    room_id: str,
) -> RenderDocument:
    room = room_id.strip()
    if not room or room in {"0", "帮助", "help"}:
        return _query_help_document()
    record = await _active_record(client, store, user_key)
    payload = await client.post_official(
        "player_room_v2",
        {**ROOM_PARAMS, "roomId": room},
        record.cookie_token,
        f"{user_key}:{record.quid}",
        ttl_seconds=client.config.player_cache_seconds,
    )
    rows = _jdata(payload).get("data")
    if not isinstance(rows, list):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")

    items = tuple(_room_item(row, idx) for idx, row in enumerate(rows[:8], start=1) if isinstance(row, dict))
    return RenderDocument(
        title="对局详情",
        summary=f"已查询对局 {room} 详情。",
        meta=(_expire_text(record),),
        sections=(RenderSection(title=f"房间号：{room}", items=items, lines=("暂无详情",) if not items else ()),),
    )


def _auth_help_document() -> RenderDocument:
    return RenderDocument(
        title="玩家授权帮助",
        summary="玩家授权帮助已生成，请按图片中的步骤完成绑定。",
        sections=(
            RenderSection(
                title="授权命令",
                lines=(
                    "三角洲授权 qq：获取 QQ 登录授权链接",
                    "三角洲授权 微信：获取微信登录授权链接",
                    "三角洲绑定 <回调链接>：保存玩家授权",
                    "三角洲刷新授权：刷新已保存授权",
                ),
            ),
        ),
    )


def _query_help_document() -> RenderDocument:
    return RenderDocument(
        title="玩家查询帮助",
        summary="玩家查询帮助已生成，请先完成授权绑定再查询。",
        sections=(
            RenderSection(
                title="玩家数据",
                lines=(
                    "玩家数据：查询烽火全赛季玩家数据",
                    "玩家数据 战场：查询全面战场玩家数据",
                    "玩家数据 烽火 6：查询烽火第 6 赛季数据",
                    "玩家战绩 [烽火|全面] [页码]：查询近期战绩",
                    "对局详情 <房间号>：查询战绩中的对局详情",
                ),
            ),
        ),
    )


def _bound_document(record: PlayerAuthRecord, summary: str) -> RenderDocument:
    return RenderDocument(
        title="玩家授权",
        summary=summary,
        sections=(
            RenderSection(
                title="授权状态",
                lines=(
                    f"账号类型：{_account_label(record.pt)}",
                    _expire_text(record),
                    "授权数据已保存到本地缓存文件，不会发送到群聊。",
                ),
            ),
        ),
    )


async def _active_record(
    client: DeltaForceApiClient,
    store: PlayerAuthStore,
    user_key: str,
) -> PlayerAuthRecord:
    record = store.require(user_key)
    if record.is_expired and record.quid:
        payload = await client.get(
            "player_oauth_quid",
            {"quid": record.quid},
            ttl_seconds=0,
        )
        return store.put_from_payload(user_key, payload)
    return record


def _parse_profile_args(args: list[str]) -> tuple[str, str, list[int], bool]:
    resource_type = "sol"
    resource_label = "烽火地带"
    seasons: list[int] = []
    for arg in args:
        lowered = arg.lower()
        if arg in {"全面", "全面战场", "战场"} or lowered == "mp":
            resource_type = "mp"
            resource_label = "全面战场"
            continue
        if arg in {"烽火", "烽火地带"} or lowered == "sol":
            resource_type = "sol"
            resource_label = "烽火地带"
            continue
        if arg.isdigit():
            seasons.append(int(arg))
    if seasons:
        return resource_type, resource_label, seasons[:6], False
    return resource_type, resource_label, DEFAULT_SEASONS, True


def _parse_battle_args(args: list[str]) -> tuple[str, str, int]:
    battle_type = "4"
    label = "烽火战绩"
    page = 1
    for arg in args:
        lowered = arg.lower()
        if arg in {"全面", "全面战场", "战场"} or lowered == "mp" or arg == "5":
            battle_type = "5"
            label = "全面战绩"
            continue
        if arg in {"烽火", "烽火地带"} or lowered == "sol" or arg == "4":
            battle_type = "4"
            label = "烽火战绩"
            continue
        if arg.isdigit():
            page = max(1, int(arg))
    return battle_type, label, page


def _detail_params(resource_type: str, seasons: list[int], all_seasons: bool) -> dict[str, str]:
    param = {
        "resourceType": resource_type,
        "seasonid": seasons,
        "isAllSeason": all_seasons,
    }
    return {
        "iChartId": "316969",
        "iSubChartId": "316969",
        "sIdeToken": "NoOapI",
        "method": "dfm/center.person.resource",
        "source": "2",
        "param": json.dumps(param, ensure_ascii=False, separators=(",", ":")),
    }


def _role_data(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root = _jdata(payload)
    user_data = root.get("userData")
    career_data = root.get("careerData")
    if not isinstance(user_data, dict) or not isinstance(career_data, dict):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")
    return user_data, career_data


def _detail_data(payload: Mapping[str, Any], resource_type: str) -> dict[str, Any]:
    j_data = _jdata(payload)
    data = j_data.get("data")
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")
    key = f"{resource_type}Detail"
    detail = data.get(key)
    return detail if isinstance(detail, dict) else data


def _money_value(payload: Mapping[str, Any]) -> object:
    rows = _jdata(payload).get("data")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0].get("totalMoney")
    raise DeltaForceUpstreamError("查询失败：上游响应格式异常")


def _jdata(payload: Mapping[str, Any]) -> dict[str, Any]:
    j_data = payload.get("jData")
    if not isinstance(j_data, dict):
        raise DeltaForceUpstreamError("查询失败：上游响应格式异常")
    return j_data


def _detail_fields(detail: Mapping[str, Any]) -> list[tuple[str, str]]:
    total_count, leave_count = _map_totals(detail.get("mapList"))
    fields = [
        ("红货总价值", money(detail.get("redTotalMoney"))),
        ("红货数量", number(detail.get("redTotalCount"))),
    ]
    if total_count:
        fields.append(("地图撤离", f"{leave_count}/{total_count}"))
    fields.extend(
        [
            ("总收益", money(detail.get("totalMoney"))),
            ("击杀", number(detail.get("killCount"))),
            ("对局", number(detail.get("fightCount"))),
        ]
    )
    return [(name, value) for name, value in fields if value != "未知"]


def _map_lines(detail: Mapping[str, Any]) -> list[str]:
    rows = detail.get("mapList")
    if not isinstance(rows, list):
        return []
    maps = [row for row in rows if isinstance(row, dict)]
    maps.sort(key=lambda item: _to_int(item.get("totalCount")), reverse=True)
    lines: list[str] = []
    for item in maps[:5]:
        total = number(item.get("totalCount"))
        leave = number(item.get("leaveCount"))
        lines.append(f"地图 {first_text(item.get('mapID'))}：撤离 {leave}/{total}")
    return lines


def _map_totals(rows: object) -> tuple[int, int]:
    if not isinstance(rows, list):
        return 0, 0
    total = 0
    leave = 0
    for row in rows:
        if isinstance(row, dict):
            total += _to_int(row.get("totalCount"))
            leave += _to_int(row.get("leaveCount"))
    return total, leave


def _battle_item(row: Mapping[str, Any]) -> RenderItem:
    room_id = first_text(row.get("RoomId"))
    return RenderItem(
        name=f"{first_text(row.get('dtEventTime'))}",
        fields=(
            ("地图ID", first_text(row.get("MapId"))),
            ("最终价值", money(row.get("FinalPrice"))),
            ("净收益", money(row.get("flowCalGainedPrice"))),
            ("时长", _duration(row.get("DurationS"))),
            ("击杀", number(row.get("KillCount"))),
            ("AI击杀", number(row.get("KillAICount"))),
            ("房间号", room_id),
        ),
    )


def _room_item(row: Mapping[str, Any], index: int) -> RenderItem:
    is_self = bool(row.get("vopenid"))
    name = first_text(row.get("nickName"), f"队员 {index}")
    return RenderItem(
        name=name,
        badges=("本人",) if is_self else (),
        fields=(
            ("地图ID", first_text(row.get("MapId"))),
            ("最终价值", money(row.get("FinalPrice"))),
            ("时长", _duration(row.get("DurationS"))),
            ("击杀", number(row.get("KillCount"))),
            ("AI击杀", number(row.get("KillAICount"))),
            ("救援", number(row.get("Rescue"))),
            ("撤离原因", first_text(row.get("EscapeFailReason"))),
        ),
    )


def _decode_text(value: object, default: str = "未知") -> str:
    text = first_text(value, default)
    if text == default:
        return text
    return unquote(text)


def _duration(value: object) -> str:
    seconds = _to_int(value)
    if seconds <= 0:
        return "未知"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}小时{minutes}分{sec}秒"
    if minutes:
        return f"{minutes}分{sec}秒"
    return f"{sec}秒"


def _expire_text(record: PlayerAuthRecord) -> str:
    if not record.expire:
        return "授权有效期：未知"
    return "授权有效期：" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.expire))


def _account_label(value: str) -> str:
    if value.lower() == "qq":
        return "QQ"
    if value.lower() in {"wx", "weixin"}:
        return "微信"
    return value or "未知"


def _to_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
