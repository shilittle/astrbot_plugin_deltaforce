#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "AGENTS.md",
    "README.md",
    "docs/api_contract.md",
    ".codex/config.toml",
    "main.py",
    "_conf_schema.json",
    "metadata.yaml",
    "requirements.txt",
    "deltaforce_openapi/api_client.py",
    "deltaforce_openapi/cache.py",
    "deltaforce_openapi/config.py",
    "deltaforce_openapi/item_store.py",
    "deltaforce_openapi/item_database.py",
    "deltaforce_openapi/item_overview.py",
    "deltaforce_openapi/player_auth.py",
    "deltaforce_openapi/commands/player.py",
    "scripts/check_connection.py",
    "scripts/prefetch_item_images.py",
]

FORBIDDEN_CODE_TERMS = [
    "playwright",
    "selenium",
    "acgice",
    "ACGICE",
]


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append(f"缺少文件：{rel}")

    contract = (ROOT / "docs/api_contract.md").read_text(encoding="utf-8")
    metadata = (ROOT / "metadata.yaml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for marker in [
        "https://orzice.com/workApi",
        "/v1/sjz_api/item_info_all",
        "/v1/sjz_api/item_price_all",
        "/v1/sjz_api/map_pwd",
        "/v1/sjz_api/jzv3_zb_plus",
        "/v1/sjz_api/minute",
        "/v1/sjz_api/manufacturePro",
        "/v1/sjz_api/keys_day",
        "/v1/sjz_api/keys_day_yc",
        "/v1/sjz_api/ammo_pack",
        "/v1/sjz_api/ammo_day",
        "/v1/sjz_api/ammo_zr_yc",
        "/v1/sjz_api/item_list_pro_key",
        "/v1/sjz_api/item_list_pro",
        "/v1/sjz_api_ex/z_GetOauthUrl",
        "/v1/sjz_api_ex/z_OauthUrl",
        "/v1/sjz_api_ex/z_GetOauthQuid",
        "https://comm.ams.game.qq.com/ide/",
        "iChartId=317814",
        "iChartId=316969",
        "iChartId=319386",
        "iChartId=450526",
        "iChartId=450471",
    ]:
        if marker not in contract:
            errors.append(f"合同缺少：{marker}")

    for marker in [
        "display_name:",
        "astrbot_version: \">=4.17.0,<5\"",
        "support_platforms:",
        "- aiocqhttp",
        "- qq_official",
    ]:
        if marker not in metadata:
            errors.append(f"metadata.yaml 缺少：{marker}")

    if "aiohttp" not in requirements:
        errors.append("requirements.txt 缺少：aiohttp")
    if "Pillow" not in requirements:
        errors.append("requirements.txt 缺少：Pillow")

    main_py = (ROOT / "main.py").read_text(encoding="utf-8")
    for marker in [
        "@register(",
        "SSKの三角洲",
        "@filter.command(\"三角洲帮助\"",
        "@filter.command(\"每日密码\"",
        "@filter.command(\"卡战备\")",
        "@filter.command(\"交易行价格\"",
        "@filter.command(\"交易行总览\"",
        "@filter.command(\"特勤处制造\"",
        "@filter.command(\"钥匙卡分析\")",
        "@filter.command(\"子弹分析\")",
        "@filter.command(\"三角洲授权\"",
        "@filter.command(\"三角洲绑定\"",
        "@filter.command(\"三角洲刷新授权\"",
        "@filter.command(\"玩家数据\"",
        "@filter.command(\"玩家战绩\"",
        "@filter.command(\"对局详情\"",
    ]:
        if marker not in main_py:
            errors.append(f"main.py 缺少：{marker}")

    for py_file in [ROOT / "main.py", *(ROOT / "deltaforce_openapi").rglob("*.py")]:
        text = py_file.read_text(encoding="utf-8")
        lowered = text.lower()
        for term in FORBIDDEN_CODE_TERMS:
            if term.lower() in lowered:
                errors.append(f"代码包含禁用项：{py_file.relative_to(ROOT)} -> {term}")
        try:
            compile(text, str(py_file), "exec")
        except SyntaxError as exc:
            errors.append(f"编译失败：{py_file.relative_to(ROOT)} -> {exc}")

    for py_file in [
        ROOT / "scripts/check_connection.py",
        ROOT / "scripts/self_check.py",
        ROOT / "scripts/prefetch_item_images.py",
    ]:
        try:
            compile(py_file.read_text(encoding="utf-8"), str(py_file), "exec")
        except SyntaxError as exc:
            errors.append(f"编译失败：{py_file.relative_to(ROOT)} -> {exc}")

    if errors:
        for item in errors:
            print(item)
        return 1
    print("self-check 通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
