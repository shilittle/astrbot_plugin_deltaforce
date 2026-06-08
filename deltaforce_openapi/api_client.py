from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - exercised only without optional dependency.
    aiohttp = None  # type: ignore[assignment]

from .cache import TTLCache
from .config import PluginConfig
from .errors import DeltaForceUpstreamError


ENDPOINTS: dict[str, str] = {
    "item_info_all": "/v1/sjz_api/item_info_all",
    "item_price_all": "/v1/sjz_api/item_price_all",
    "map_pwd": "/v1/sjz_api/map_pwd",
    "jzv3_zb_plus": "/v1/sjz_api/jzv3_zb_plus",
    "minute": "/v1/sjz_api/minute",
    "manufacturePro": "/v1/sjz_api/manufacturePro",
    "keys_day": "/v1/sjz_api/keys_day",
    "keys_day_yc": "/v1/sjz_api/keys_day_yc",
    "ammo_pack": "/v1/sjz_api/ammo_pack",
    "ammo_day": "/v1/sjz_api/ammo_day",
    "ammo_zr_yc": "/v1/sjz_api/ammo_zr_yc",
    "item_list_pro_key": "/v1/sjz_api/item_list_pro_key",
    "item_list_pro": "/v1/sjz_api/item_list_pro",
    "player_oauth_url": "/v1/sjz_api_ex/z_GetOauthUrl",
    "player_oauth_verify": "/v1/sjz_api_ex/z_OauthUrl",
    "player_oauth_quid": "/v1/sjz_api_ex/z_GetOauthQuid",
}

OFFICIAL_PLAYER_ENDPOINTS: dict[str, str] = {
    "player_role": "https://comm.ams.game.qq.com/ide/",
    "player_detail": "https://comm.ams.game.qq.com/ide/",
    "player_money": "https://comm.ams.game.qq.com/ide/",
    "player_battle_v2": "https://comm.ams.game.qq.com/ide/",
    "player_room_v2": "https://comm.ams.game.qq.com/ide/",
}


class DeltaForceApiClient:
    def __init__(self, config: PluginConfig, cache: TTLCache | None = None) -> None:
        self.config = config
        self.cache = cache or TTLCache()

    async def get(
        self,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        ttl_seconds: int | float = 60,
    ) -> dict[str, Any]:
        if endpoint not in ENDPOINTS:
            raise DeltaForceUpstreamError("接口未完成：请求端点尚未在文档中确认")

        safe_params = self._normalize_params(params or {})
        cache_key = (endpoint, tuple(sorted((k, str(v)) for k, v in safe_params.items())))

        async def factory() -> dict[str, Any]:
            request_params = dict(safe_params)
            request_params["token"] = self.config.get_token()
            return await self._request(endpoint, request_params)

        if ttl_seconds <= 0:
            return await factory()
        return await self.cache.get_or_set(cache_key, ttl_seconds, factory)

    async def post_official(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        cookies: Mapping[str, str],
        auth_cache_key: str,
        ttl_seconds: int | float = 60,
    ) -> dict[str, Any]:
        if endpoint not in OFFICIAL_PLAYER_ENDPOINTS:
            raise DeltaForceUpstreamError("接口未完成：请求端点尚未在文档中确认")
        if not auth_cache_key:
            raise DeltaForceUpstreamError("查询失败：玩家授权未绑定")

        safe_params = self._normalize_params(params)
        safe_cookies = {str(k): str(v) for k, v in cookies.items() if str(k).strip() and str(v).strip()}
        cache_key = (
            "official_post",
            endpoint,
            auth_cache_key,
            tuple(sorted((k, str(v)) for k, v in safe_params.items())),
        )

        async def factory() -> dict[str, Any]:
            return await self._request_official(endpoint, safe_params, safe_cookies)

        if ttl_seconds <= 0:
            return await factory()
        return await self.cache.get_or_set(cache_key, ttl_seconds, factory)

    async def fetch_public_bytes(
        self,
        url: str,
        ttl_seconds: int | float,
        max_bytes: int | None = None,
    ) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise DeltaForceUpstreamError("查询失败：图片地址格式异常")
        limit = max_bytes or self.config.max_image_bytes
        cache_key = ("public_bytes", url)

        async def factory() -> bytes:
            return await self._request_public_bytes(url, limit)

        return await self.cache.get_or_set(cache_key, ttl_seconds, factory)

    def _normalize_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in params.items():
            if value is None:
                continue
            normalized[str(key)] = value
        return normalized

    async def _request(self, endpoint: str, params: Mapping[str, Any]) -> dict[str, Any]:
        if aiohttp is None:
            return await asyncio.to_thread(self._request_sync, endpoint, params)

        path = ENDPOINTS[endpoint]
        url = f"{self.config.base_url}{path}"
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
                async with session.get(
                    url,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "astrbot-plugin-deltaforce/0.1",
                    },
                ) as response:
                    if response.status >= 400:
                        raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用")
                    raw = await response.read()
        except DeltaForceUpstreamError:
            raise
        except TimeoutError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口超时") from exc
        except aiohttp.ClientError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc

        return self._parse_payload(raw)

    async def _request_public_bytes(self, url: str, max_bytes: int) -> bytes:
        if aiohttp is None:
            return await asyncio.to_thread(self._request_public_bytes_sync, url, max_bytes)

        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
                async with session.get(
                    url,
                    headers={"User-Agent": "astrbot-plugin-deltaforce/0.1"},
                ) as response:
                    if response.status >= 400:
                        raise DeltaForceUpstreamError("查询失败：图片资源暂时不可用")
                    raw_buffer = bytearray()
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        raw_buffer.extend(chunk)
                        if len(raw_buffer) > max_bytes:
                            raise DeltaForceUpstreamError("查询失败：图片资源过大")
                    raw = bytes(raw_buffer)
        except DeltaForceUpstreamError:
            raise
        except TimeoutError as exc:
            raise DeltaForceUpstreamError("查询失败：图片资源超时") from exc
        except aiohttp.ClientError as exc:
            raise DeltaForceUpstreamError("查询失败：图片资源暂时不可用") from exc

        return raw

    async def _request_official(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        cookies: Mapping[str, str],
    ) -> dict[str, Any]:
        if aiohttp is None:
            return await asyncio.to_thread(self._request_official_sync, endpoint, params, cookies)

        url = OFFICIAL_PLAYER_ENDPOINTS[endpoint]
        timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
                async with session.post(
                    url,
                    params=params,
                    cookies=dict(cookies),
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "astrbot-plugin-deltaforce/0.1",
                    },
                ) as response:
                    if response.status >= 400:
                        raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用")
                    raw = await response.read()
        except DeltaForceUpstreamError:
            raise
        except TimeoutError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口超时") from exc
        except aiohttp.ClientError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc

        return self._parse_payload(raw)

    def _request_sync(self, endpoint: str, params: Mapping[str, Any]) -> dict[str, Any]:
        path = ENDPOINTS[endpoint]
        url = f"{self.config.base_url}{path}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "astrbot-plugin-deltaforce/0.1",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.config.request_timeout) as response:
                raw = response.read(self.config.max_response_bytes + 1)
        except HTTPError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc
        except URLError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc
        except TimeoutError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口超时") from exc
        except OSError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc

        return self._parse_payload(raw)

    def _request_public_bytes_sync(self, url: str, max_bytes: int) -> bytes:
        request = Request(
            url,
            headers={"User-Agent": "astrbot-plugin-deltaforce/0.1"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.config.request_timeout) as response:
                raw = response.read(max_bytes + 1)
        except HTTPError as exc:
            raise DeltaForceUpstreamError("查询失败：图片资源暂时不可用") from exc
        except URLError as exc:
            raise DeltaForceUpstreamError("查询失败：图片资源暂时不可用") from exc
        except TimeoutError as exc:
            raise DeltaForceUpstreamError("查询失败：图片资源超时") from exc
        except OSError as exc:
            raise DeltaForceUpstreamError("查询失败：图片资源暂时不可用") from exc
        if len(raw) > max_bytes:
            raise DeltaForceUpstreamError("查询失败：图片资源过大")
        return raw

    def _request_official_sync(
        self,
        endpoint: str,
        params: Mapping[str, Any],
        cookies: Mapping[str, str],
    ) -> dict[str, Any]:
        url = f"{OFFICIAL_PLAYER_ENDPOINTS[endpoint]}?{urlencode(params)}"
        request = Request(
            url,
            data=b"",
            headers={
                "Accept": "application/json",
                "Cookie": _cookie_header(cookies),
                "User-Agent": "astrbot-plugin-deltaforce/0.1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.request_timeout) as response:
                raw = response.read(self.config.max_response_bytes + 1)
        except HTTPError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc
        except URLError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc
        except TimeoutError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口超时") from exc
        except OSError as exc:
            raise DeltaForceUpstreamError("查询失败：上游接口暂时不可用") from exc

        return self._parse_payload(raw)

    def _parse_payload(self, raw: bytes) -> dict[str, Any]:
        if len(raw) > self.config.max_response_bytes:
            raise DeltaForceUpstreamError("查询失败：上游响应过大")

        try:
            decoded = raw.decode("utf-8")
            payload = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DeltaForceUpstreamError("查询失败：上游响应格式异常") from exc

        if not isinstance(payload, dict):
            raise DeltaForceUpstreamError("查询失败：上游响应格式异常")

        code = payload.get("code")
        if code not in (None, 0, "0"):
            raise DeltaForceUpstreamError("查询失败：上游接口返回失败")
        for key in ("ret", "iRet"):
            value = payload.get(key)
            if value not in (None, 0, "0"):
                raise DeltaForceUpstreamError("查询失败：上游接口返回失败")
        j_data = payload.get("jData")
        if isinstance(j_data, dict):
            value = j_data.get("iRet")
            if value not in (None, 0, "0"):
                raise DeltaForceUpstreamError("查询失败：上游接口返回失败")

        return payload


def _cookie_header(cookies: Mapping[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in cookies.items())
