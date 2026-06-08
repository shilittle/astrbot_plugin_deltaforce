#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deltaforce_openapi.api_client import DeltaForceApiClient
from deltaforce_openapi.config import PluginConfig
from deltaforce_openapi.errors import DeltaForceUserError


async def main() -> int:
    config = PluginConfig.from_mapping(ROOT, {"key_file": "key.txt", "request_timeout": 10.0})
    client = DeltaForceApiClient(config)
    try:
        payload = await client.get("map_pwd", ttl_seconds=1)
    except DeltaForceUserError as exc:
        print(exc.user_message)
        return 1
    except Exception:
        print("连接失败：开放平台暂时不可用")
        return 1

    data = payload.get("data")
    if not isinstance(data, dict):
        print("连接失败：开放平台响应格式异常")
        return 1
    print("连接成功：开放平台可用")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

