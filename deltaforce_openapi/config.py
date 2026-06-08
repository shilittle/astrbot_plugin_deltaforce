from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .errors import DeltaForceConfigError


@dataclass(slots=True)
class PluginConfig:
    root_dir: Path
    api_token: str = field(default="", repr=False)
    key_file: Path = field(default_factory=lambda: Path("key.txt"), repr=False)
    base_url: str = "https://orzice.com/workApi"
    request_timeout: float = 10.0
    result_limit: int = 5
    item_cache_seconds: int = 3600
    minute_cache_seconds: int = 60
    map_refresh_hour: int = 0
    map_refresh_minute: int = 5
    map_cache_seconds: int = 3600
    card_cache_seconds: int = 120
    manufacture_cache_seconds: int = 600
    conservative_cache_seconds: int = 300
    overview_key_cache_seconds: int = 7 * 24 * 3600
    overview_cache_seconds: int = 20 * 60
    player_cache_seconds: int = 60
    player_auth_file: Path = field(default_factory=lambda: Path("cache/player_auth.json"), repr=False)
    image_cache_seconds: int = 3600
    image_asset_cache_seconds: int = 7 * 24 * 3600
    max_render_page_height: int = 6000
    max_response_bytes: int = 8 * 1024 * 1024
    max_image_bytes: int = 2 * 1024 * 1024

    @classmethod
    def from_mapping(cls, root_dir: Path, raw: Mapping[str, Any] | None) -> "PluginConfig":
        raw = raw or {}
        key_file = Path(str(raw.get("key_file", "key.txt")).strip() or "key.txt")
        if not key_file.is_absolute():
            key_file = root_dir / key_file

        token = str(raw.get("api_token", "") or os.environ.get("DELTAFORCE_OPENAPI_TOKEN", "")).strip()

        return cls(
            root_dir=root_dir,
            api_token=token,
            key_file=key_file,
            base_url=str(raw.get("base_url", "https://orzice.com/workApi")).rstrip("/"),
            request_timeout=float(raw.get("request_timeout", 10.0)),
            result_limit=max(1, int(raw.get("result_limit", 5))),
            item_cache_seconds=max(60, int(raw.get("item_cache_seconds", 3600))),
            minute_cache_seconds=max(15, int(raw.get("minute_cache_seconds", 60))),
            map_refresh_hour=min(23, max(0, int(raw.get("map_refresh_hour", 0)))),
            map_refresh_minute=min(59, max(0, int(raw.get("map_refresh_minute", 5)))),
            map_cache_seconds=max(60, int(raw.get("map_cache_seconds", 3600))),
            card_cache_seconds=max(30, int(raw.get("card_cache_seconds", 120))),
            manufacture_cache_seconds=max(300, int(raw.get("manufacture_cache_seconds", 600))),
            conservative_cache_seconds=max(300, int(raw.get("conservative_cache_seconds", 300))),
            overview_key_cache_seconds=max(3600, int(raw.get("overview_key_cache_seconds", 7 * 24 * 3600))),
            overview_cache_seconds=max(600, int(raw.get("overview_cache_seconds", 20 * 60))),
            player_cache_seconds=max(15, int(raw.get("player_cache_seconds", 60))),
            player_auth_file=_resolve_path(root_dir, raw.get("player_auth_file", "cache/player_auth.json")),
            image_cache_seconds=max(60, int(raw.get("image_cache_seconds", 3600))),
            image_asset_cache_seconds=max(3600, int(raw.get("image_asset_cache_seconds", 7 * 24 * 3600))),
            max_render_page_height=max(1200, int(raw.get("max_render_page_height", 6000))),
            max_response_bytes=max(1024 * 1024, int(raw.get("max_response_bytes", 8 * 1024 * 1024))),
            max_image_bytes=max(256 * 1024, int(raw.get("max_image_bytes", 2 * 1024 * 1024))),
        )

    def get_token(self) -> str:
        if self.api_token:
            return self.api_token
        try:
            token = self.key_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise DeltaForceConfigError("配置错误：请先配置开放平台密钥") from exc
        except OSError as exc:
            raise DeltaForceConfigError("配置错误：无法读取开放平台密钥") from exc
        if not token:
            raise DeltaForceConfigError("配置错误：请先配置开放平台密钥")
        return token


def _resolve_path(root_dir: Path, raw_path: object) -> Path:
    path = Path(str(raw_path or "").strip() or "cache/player_auth.json")
    if path.is_absolute():
        return path
    return root_dir / path
