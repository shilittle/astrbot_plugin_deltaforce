# AstrBot Delta OpenAPI Plugin Rules

## Session Bootstrap

Before design, coding, search, or network evidence collection, read:

1. `AGENTS.md`
2. `README.md`
3. `docs/api_contract.md`

`docs/api_contract.md` is the final contract. Apifox is only a discovery
source for filling TODO items in that contract.

## Scope

This repository is a new AstrBot plugin for Delta Force open-platform query
APIs. It is not a patch to an old plugin.

Allowed in the current phase:
- Platform open query APIs.
- Server-side token query mode.
- Documented player authorization helper APIs.
- Documented player-state read APIs that use the returned cookie fields.
- Cache-backed API reads.
- Local item data/index bootstrap.
- Text-plus-image QQ output for successful queries.

Forbidden in the current phase:
- Undocumented player authorization flow.
- Manual cookie capture, browser login automation, or user-supplied raw cookie
  strings.
- Browser crawler.
- ACGICE page screenshot extraction.
- Entertainment features.
- TTS.
- Login-state management.
- Push jobs.

## Hard Rules

- Do not guess undocumented params, fields, headers, cookies, or auth flows.
- Update `docs/api_contract.md` before changing code that depends on API details.
- Do not expose token values in code output, logs, docs examples, exceptions, or QQ messages.
- Do not expose player authorization cookie values, callback URLs, or raw
  authorization payloads in logs, docs examples, exceptions, or QQ messages.
- All upstream requests must go through the API client.
- All user queries must go through the cache layer.
- Initialize `item_info_all` and `item_price_all` before business commands.
- Item search and price lookup must prefer the local index.
- Successful QQ replies should use concise text plus locally rendered images.
- QQ-facing errors are one Chinese line.
- Do not return raw JSON, full payloads, token values, or tracebacks to QQ.

## Required Deliverables

- `AGENTS.md`
- `README.md`
- `docs/api_contract.md`
- `.codex/config.toml`
- `metadata.yaml`
- `requirements.txt`
- AstrBot plugin entrypoint
- API client
- Cache layer
- Config schema
- Self-check script
- Base item data bootstrap
- Six query commands
