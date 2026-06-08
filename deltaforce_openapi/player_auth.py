from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import DeltaForceUserError


COOKIE_KEYS = ("access_token", "acctype", "appid", "openid", "vopenid")


@dataclass(frozen=True, slots=True)
class PlayerAuthRecord:
    user_key: str
    quid: str
    pt: str
    expire: int
    token: dict[str, str]
    updated_at: int

    @property
    def is_expired(self) -> bool:
        return bool(self.expire and self.expire <= int(time.time()))

    @property
    def cookie_token(self) -> dict[str, str]:
        return {key: self.token[key] for key in COOKIE_KEYS if self.token.get(key)}


class PlayerAuthStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, user_key: str) -> PlayerAuthRecord | None:
        raw = self._read_all().get(user_key)
        if not isinstance(raw, dict):
            return None
        return _record_from_mapping(user_key, raw)

    def require(self, user_key: str) -> PlayerAuthRecord:
        record = self.get(user_key)
        if record is None:
            raise DeltaForceUserError("请先发送“三角洲授权 qq”并完成“三角洲绑定 <回调链接>”")
        if not record.cookie_token:
            raise DeltaForceUserError("玩家授权已失效：请重新发送“三角洲授权 qq”")
        return record

    def put_from_payload(self, user_key: str, payload: Mapping[str, Any]) -> PlayerAuthRecord:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise DeltaForceUserError("绑定失败：授权接口返回格式异常")

        old = self.get(user_key)
        token = data.get("token")
        if not isinstance(token, Mapping):
            raise DeltaForceUserError("绑定失败：授权接口未返回有效授权")

        record = PlayerAuthRecord(
            user_key=user_key,
            quid=str(data.get("quid") or (old.quid if old else "")).strip(),
            pt=str(data.get("pt") or (old.pt if old else "")).strip(),
            expire=_to_int(data.get("expire"), old.expire if old else 0),
            token=_normalize_token(token),
            updated_at=int(time.time()),
        )
        if not record.quid:
            raise DeltaForceUserError("绑定失败：授权接口未返回用户标识")
        if not record.cookie_token:
            raise DeltaForceUserError("绑定失败：授权接口未返回有效授权")
        self.put_record(record)
        return record

    def put_record(self, record: PlayerAuthRecord) -> None:
        raw = self._read_all()
        raw[record.user_key] = {
            "quid": record.quid,
            "pt": record.pt,
            "expire": record.expire,
            "token": record.token,
            "updated_at": record.updated_at,
        }
        self._write_all(raw)

    def _read_all(self) -> dict[str, Any]:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise DeltaForceUserError("玩家授权读取失败：请检查插件缓存目录权限") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DeltaForceUserError("玩家授权读取失败：本地授权文件格式异常") from exc
        return data if isinstance(data, dict) else {}

    def _write_all(self, data: Mapping[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            raise DeltaForceUserError("玩家授权保存失败：请检查插件缓存目录权限") from exc


def _record_from_mapping(user_key: str, raw: Mapping[str, Any]) -> PlayerAuthRecord | None:
    token = raw.get("token")
    if not isinstance(token, Mapping):
        return None
    return PlayerAuthRecord(
        user_key=user_key,
        quid=str(raw.get("quid") or "").strip(),
        pt=str(raw.get("pt") or "").strip(),
        expire=_to_int(raw.get("expire"), 0),
        token=_normalize_token(token),
        updated_at=_to_int(raw.get("updated_at"), 0),
    )


def _normalize_token(raw: Mapping[str, Any]) -> dict[str, str]:
    token: dict[str, str] = {}
    for key in COOKIE_KEYS:
        value = str(raw.get(key) or "").strip()
        if value:
            token[key] = value
    return token


def _to_int(value: object, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default
