from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
import astrbot.api.message_components as Comp
from astrbot.api.star import Context, Star, register

from .deltaforce_openapi.api_client import DeltaForceApiClient
from .deltaforce_openapi.cache import TTLCache
from .deltaforce_openapi.commands import (
    ammo,
    help as help_command,
    jzv3_zb_plus,
    keys,
    manufacture,
    map_pwd,
    minute,
    player,
)
from .deltaforce_openapi.config import PluginConfig
from .deltaforce_openapi.errors import DeltaForceUserError
from .deltaforce_openapi.item_overview import ItemOverviewStore
from .deltaforce_openapi.item_store import ItemStore
from .deltaforce_openapi.player_auth import PlayerAuthStore
from .deltaforce_openapi.renderer import LocalImageRenderer, RenderBundle, RenderDocument


@register(
    "SSKの三角洲",
    "Codex",
    "SSKの三角洲开放平台查询插件",
    "0.2.0",
)
class DeltaForceOpenApiPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        root_dir = Path(__file__).resolve().parent
        self.config = PluginConfig.from_mapping(root_dir, config or {})
        self.cache = TTLCache()
        self.client = DeltaForceApiClient(self.config, self.cache)
        self.item_store = ItemStore(self.client)
        self.overview_store = ItemOverviewStore(self.client, root_dir)
        self.player_auth_store = PlayerAuthStore(self.config.player_auth_file)
        self.image_renderer = LocalImageRenderer(root_dir, self.client, self.item_store.database)
        self._base_ready = False

    async def initialize(self) -> None:
        try:
            await self.item_store.initialize()
            self._base_ready = True
            logger.info("DeltaForce OpenAPI 插件基础数据初始化完成")
        except DeltaForceUserError as exc:
            self._base_ready = False
            logger.warning(f"DeltaForce OpenAPI 插件初始化未完成：{exc.user_message}")
        except Exception:
            self._base_ready = False
            logger.exception("DeltaForce OpenAPI 插件初始化失败")

    async def terminate(self) -> None:
        await self.cache.clear()

    @filter.command("三角洲帮助", alias={"三角洲查询帮助", "三角洲插件帮助", "deltaforce帮助"})
    async def cmd_help(self, event: AstrMessageEvent) -> AsyncIterator[object]:
        """查看三角洲开放平台查询插件完整使用指南。"""
        async for result in self._reply(event, lambda: _ready_doc(help_command.render())):
            yield result

    @filter.command("每日密码", alias={"今日密码", "地图密码"})
    async def cmd_map_pwd(self, event: AstrMessageEvent) -> AsyncIterator[object]:
        """查询三角洲各地图每日密码。"""
        async for result in self._reply(event, lambda: map_pwd.render(self.client)):
            yield result

    @filter.command("卡战备")
    async def cmd_jz(self, event: AstrMessageEvent, level: str = "") -> AsyncIterator[object]:
        """查询卡战备配置，发送“卡战备 0”查看帮助。"""
        raw_args = _args(event, ["卡战备"])
        raw_level = (raw_args[0] if raw_args else "") or level
        raw_preference = " ".join(raw_args[1:]).strip()
        async for result in self._reply(event, lambda: jzv3_zb_plus.render(self.client, raw_level, raw_preference)):
            yield result

    @filter.command("交易行价格", alias={"价格", "物价", "价格曲线"})
    async def cmd_minute(self, event: AstrMessageEvent, keyword: str = "") -> AsyncIterator[object]:
        """查询交易行价格曲线摘要，发送“交易行价格 0”查看帮助。"""
        raw_keyword = _arg_after(event, ["交易行价格", "价格曲线", "价格", "物价"]) or keyword
        if raw_keyword.startswith("总览"):
            raw_overview = raw_keyword.removeprefix("总览").strip()
            async for result in self._reply(
                event,
                lambda: minute.render_overview(self.client, self.overview_store, raw_overview),
            ):
                yield result
            return
        async for result in self._reply(
            event,
            lambda: minute.render(self.client, self.item_store, raw_keyword),
            need_base=True,
        ):
            yield result

    @filter.command("交易行总览", alias={"物品总览"})
    async def cmd_overview(self, event: AstrMessageEvent, keyword: str = "") -> AsyncIterator[object]:
        """查询交易行物品总览筛选项或指定分类。"""
        raw_args = _arg_after(event, ["交易行总览", "物品总览"]) or keyword
        async for result in self._reply(
            event,
            lambda: minute.render_overview(self.client, self.overview_store, raw_args),
        ):
            yield result

    @filter.command("特勤处制造", alias={"特勤制造"})
    async def cmd_manufacture(
        self,
        event: AstrMessageEvent,
        t: str = "",
        l: str = "",
    ) -> AsyncIterator[object]:
        """查询特勤处制造收益，发送“特勤处制造 0”查看帮助。"""
        raw_args = _args(event, ["特勤处制造", "特勤制造"])
        raw_t = (raw_args[0] if raw_args else "") or t
        raw_l = (raw_args[1] if len(raw_args) >= 2 else "") or l
        raw_sort = " ".join(raw_args[2:]).strip()
        async for result in self._reply(event, lambda: manufacture.render(self.client, raw_t, raw_l, raw_sort)):
            yield result

    @filter.command("钥匙卡分析")
    async def cmd_keys(self, event: AstrMessageEvent, mode: str = "") -> AsyncIterator[object]:
        """查询钥匙卡低价预测，发送“钥匙卡分析 0”查看帮助。"""
        raw_mode = mode or _arg_after(event, ["钥匙卡分析"])
        async for result in self._reply(event, lambda: keys.render(self.client, raw_mode)):
            yield result

    @filter.command("子弹分析")
    async def cmd_ammo(self, event: AstrMessageEvent, mode: str = "") -> AsyncIterator[object]:
        """查询子弹收益和低价预测，发送“子弹分析 0”查看帮助。"""
        raw_mode = mode or _arg_after(event, ["子弹分析"])
        async for result in self._reply(event, lambda: ammo.render(self.client, raw_mode)):
            yield result

    @filter.command("三角洲授权", alias={"玩家授权", "三角洲登录"})
    async def cmd_player_auth(self, event: AstrMessageEvent, account_type: str = "") -> AsyncIterator[object]:
        """获取玩家授权登录链接，发送“三角洲授权 0”查看帮助。"""
        raw_type = _arg_after(event, ["三角洲授权", "玩家授权", "三角洲登录"]) or account_type
        async for result in self._reply(event, lambda: player.render_auth_url(self.client, raw_type)):
            yield result

    @filter.command("三角洲绑定", alias={"玩家绑定"})
    async def cmd_player_bind(self, event: AstrMessageEvent, callback_url: str = "") -> AsyncIterator[object]:
        """保存玩家授权回调链接。"""
        raw_url = _arg_after(event, ["三角洲绑定", "玩家绑定"]) or callback_url
        async for result in self._reply(
            event,
            lambda: player.bind_callback(self.client, self.player_auth_store, _sender_key(event), raw_url),
        ):
            yield result

    @filter.command("三角洲刷新授权", alias={"刷新玩家授权"})
    async def cmd_player_refresh(self, event: AstrMessageEvent) -> AsyncIterator[object]:
        """刷新已保存的玩家授权。"""
        async for result in self._reply(
            event,
            lambda: player.refresh_auth(self.client, self.player_auth_store, _sender_key(event)),
        ):
            yield result

    @filter.command("玩家数据", alias={"三角洲玩家", "玩家信息"})
    async def cmd_player_profile(self, event: AstrMessageEvent, args: str = "") -> AsyncIterator[object]:
        """查询已绑定玩家的角色数据。"""
        raw_args = _arg_after(event, ["玩家数据", "三角洲玩家", "玩家信息"]) or args
        async for result in self._reply(
            event,
            lambda: player.render_profile(self.client, self.player_auth_store, _sender_key(event), raw_args),
        ):
            yield result

    @filter.command("玩家战绩", alias={"三角洲战绩"})
    async def cmd_player_battle(self, event: AstrMessageEvent, args: str = "") -> AsyncIterator[object]:
        """查询已绑定玩家的近期战绩。"""
        raw_args = _arg_after(event, ["玩家战绩", "三角洲战绩"]) or args
        async for result in self._reply(
            event,
            lambda: player.render_battle(self.client, self.player_auth_store, _sender_key(event), raw_args),
        ):
            yield result

    @filter.command("对局详情", alias={"三角洲对局"})
    async def cmd_player_room(self, event: AstrMessageEvent, room_id: str = "") -> AsyncIterator[object]:
        """查询战绩中的对局详情。"""
        raw_room_id = _arg_after(event, ["对局详情", "三角洲对局"]) or room_id
        async for result in self._reply(
            event,
            lambda: player.render_room(self.client, self.player_auth_store, _sender_key(event), raw_room_id),
        ):
            yield result

    async def _reply(
        self,
        event: AstrMessageEvent,
        producer: Callable[[], Awaitable[RenderDocument | RenderBundle]],
        need_base: bool = False,
    ) -> AsyncIterator[object]:
        try:
            if need_base:
                await self._ensure_base_data()
            result = await producer()
            document, image_paths = await self._render_reply_images(result)
            yield event.chain_result(
                [Comp.Plain(document.summary)]
                + [Comp.Image.fromFileSystem(str(image_path)) for image_path in image_paths]
            )
        except DeltaForceUserError as exc:
            yield event.plain_result(exc.user_message)
        except Exception:
            logger.exception("DeltaForce OpenAPI 命令执行失败")
            yield event.plain_result("查询失败：上游接口暂时不可用")

    async def _ensure_base_data(self) -> None:
        if self._base_ready:
            return
        await self.item_store.initialize()
        self._base_ready = True

    async def _render_reply_images(self, result: RenderDocument | RenderBundle) -> tuple[RenderDocument, list[Path]]:
        if isinstance(result, RenderBundle):
            selected = result.selected
            documents = result.cache_documents or (selected,)
            selected_paths: list[Path] | None = None
            for document in documents:
                paths = await self.image_renderer.render_pages(document)
                if document == selected:
                    selected_paths = paths
            if selected_paths is None:
                selected_paths = await self.image_renderer.render_pages(selected)
            return selected, selected_paths
        return result, await self.image_renderer.render_pages(result)


def _arg_after(event: AstrMessageEvent, names: list[str]) -> str:
    args = _args(event, names)
    return " ".join(args).strip()


def _args(event: AstrMessageEvent, names: list[str]) -> list[str]:
    text = (event.message_str or "").strip()
    if text.startswith("/"):
        text = text[1:].strip()
    for name in sorted(names, key=len, reverse=True):
        if text == name:
            return []
        if text.startswith(name + " "):
            return text[len(name) :].strip().split()
    return text.split()[1:] if len(text.split()) > 1 else []


def _sender_key(event: AstrMessageEvent) -> str:
    sender_id = str(event.get_sender_id() or "").strip()
    if not sender_id:
        raise DeltaForceUserError("玩家授权失败：无法识别消息发送者")
    platform = str(getattr(event, "unified_msg_origin", "") or "").split(":", 1)[0]
    return f"{platform or 'default'}:{sender_id}"


async def _ready_doc(document: RenderDocument) -> RenderDocument:
    return document
