#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from deltaforce_openapi.api_client import DeltaForceApiClient
from deltaforce_openapi.cache import TTLCache
from deltaforce_openapi.config import PluginConfig
from deltaforce_openapi.item_store import ItemStore


async def main() -> int:
    config = PluginConfig.from_mapping(ROOT, {})
    client = DeltaForceApiClient(config, TTLCache())
    store = ItemStore(client)
    await store.initialize(force=True)

    asset_dir = ROOT / "cache" / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    urls = store.database.list_image_urls()
    total, cached_before = store.database.image_stats()
    print(f"物品数据库初始化完成：{total} 个图片地址，已缓存 {cached_before} 个")

    semaphore = asyncio.Semaphore(16)
    ok = 0
    skipped = 0
    failed = 0

    async def fetch(url: str) -> None:
        nonlocal ok, skipped, failed
        existing = store.database.get_image_path(url)
        if existing is not None:
            skipped += 1
            return
        async with semaphore:
            try:
                raw = await client.fetch_public_bytes(
                    url,
                    ttl_seconds=config.image_asset_cache_seconds,
                    max_bytes=config.max_image_bytes,
                )
                path = asset_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.img"
                path.write_bytes(raw)
                store.database.set_image_path(url, path)
                ok += 1
            except Exception:
                failed += 1

    await asyncio.gather(*(fetch(url) for url in urls))
    total_after, cached_after = store.database.image_stats()
    print(
        f"图片预拉取完成：新增 {ok}，跳过 {skipped}，失败 {failed}，"
        f"数据库记录 {cached_after}/{total_after}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
