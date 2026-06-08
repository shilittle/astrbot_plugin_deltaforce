# SSKの三角洲

This is a from-zero AstrBot plugin for Delta Force open-platform data queries.
It uses confirmed open APIs from the final contract in
`docs/api_contract.md` and returns concise text plus locally rendered images in
QQ messages.

## Source of Truth

Priority order:

1. `docs/api_contract.md`
2. Confirmed Apifox evidence used to update the contract
3. `README.md`

Do not implement undocumented params, fields, headers, cookies, or auth models.

## Features

- Base data bootstrap:
  - `item_info_all`
  - `item_price_all`
- Commands:
  - `三角洲帮助` / `三角洲查询帮助` / `三角洲插件帮助`
  - `每日密码` / `今日密码` / `地图密码`
  - `卡战备 <n> [均衡|枪优先|胸挂优先]`
  - `交易行价格 <keyword>` / `价格` / `物价` / `价格曲线`
  - `交易行价格 总览 [key1] [key2] [sort] [grade]`
  - `交易行总览 [key1] [key2] [sort] [grade]` / `物品总览`
  - `特勤处制造 <t> [l] [小时收益|总收益]` / `特勤制造`
  - `钥匙卡分析 <n>`
  - `子弹分析 <n>`
  - `三角洲授权 <qq|微信>` / `三角洲绑定 <回调链接>` / `三角洲刷新授权`
  - `玩家数据 [烽火|战场] [赛季ID]`
  - `玩家战绩 [烽火|全面] [页码]`
  - `对局详情 <房间号>`
- Server-side token query.
- Player authorization through the documented open-platform OAuth helper APIs.
- Cache layer.
- Local item index.
- Local item database with item image records.
- Text-plus-image QQ output for successful queries.
- Local rendered image cache and local API item image cache.

## Out of Scope

- Browser crawlers.
- ACGICE screenshot extraction.
- TTS.
- Push.
- Entertainment features.
- Login-state management.

Player authorization is intentionally limited to the documented Apifox flow:
generate an authorization URL, verify the callback URL, store the returned
`quid` and cookie fields locally, and refresh through `quid`. The plugin does
not implement an independent login flow.

## Configuration

The plugin reads the open-platform token from configuration key `api_token`.
If that value is empty, it reads `key.txt` in this plugin directory by default.

`key.txt` is treated as a local secret and must never be printed or sent to QQ.

Player authorization is stored in `cache/player_auth.json` by default. Treat
that file as a local secret as well.

For local file-based configuration, copy `key.txt.example` to `key.txt` and put
the token on a single line. `key.txt`, `cache/`, SQLite databases, rendered
images, and Python bytecode are intentionally ignored by Git.

## Repository Layout

- `main.py`: AstrBot plugin entrypoint and command handlers.
- `deltaforce_openapi/`: API client, cache layer, data stores, renderers, and
  command implementations.
- `docs/api_contract.md`: final API contract used by the implementation.
- `scripts/`: local maintenance and validation helpers.
- `metadata.yaml`, `_conf_schema.json`, `requirements.txt`: AstrBot plugin
  metadata, WebUI config schema, and runtime dependencies.

## AstrBot Compatibility

The plugin follows the current AstrBot Star plugin layout:

- `main.py` contains the `Star` subclass and command handlers.
- `metadata.yaml` declares metadata, display name, supported platforms, and the
  AstrBot version range.
- `_conf_schema.json` declares WebUI-managed configuration.
- `requirements.txt` declares `aiohttp` for async upstream HTTP requests and
  `Pillow` for local image rendering.
- Successful command replies use AstrBot message chains with text plus a local
  rendered image.
- The item overview feature uses `item_list_pro_key` and `item_list_pro`
  lazily. It does not bulk refresh at startup; each requested overview option is
  cached with a local update time.

Required AstrBot version:

- `>=4.17.0,<5`

## Local Checks

Run:

```bash
python3 scripts/self_check.py
python3 scripts/check_connection.py
```

`check_connection.py` reads the configured token source and performs a safe
open-interface connection check without printing the token.

Before publishing to GitHub, initialize the repository from this directory and
review the staged file list:

```bash
git init
git add .
git status --short
```
