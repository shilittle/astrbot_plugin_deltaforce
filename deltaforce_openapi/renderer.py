from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from .api_client import DeltaForceApiClient
from .item_database import ItemDatabase, ItemImageRef


@dataclass(frozen=True, slots=True)
class RenderItem:
    name: str
    image_url: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    lines: tuple[str, ...] = ()
    badges: tuple[str, ...] = ()
    rank: str = ""


@dataclass(frozen=True, slots=True)
class RenderSection:
    title: str
    lines: tuple[str, ...] = ()
    items: tuple[RenderItem, ...] = ()


@dataclass(frozen=True, slots=True)
class RenderDocument:
    title: str
    summary: str
    meta: tuple[str, ...] = ()
    lines: tuple[str, ...] = ()
    sections: tuple[RenderSection, ...] = ()
    author: str = "sskの三角洲"


@dataclass(frozen=True, slots=True)
class RenderBundle:
    selected: RenderDocument
    cache_documents: tuple[RenderDocument, ...] = ()


@dataclass(frozen=True, slots=True)
class _ResolvedAsset:
    url: str
    local_path: Path | None = None


class LocalImageRenderer:
    def __init__(
        self,
        root_dir: Path,
        client: DeltaForceApiClient,
        item_database: ItemDatabase | None = None,
    ) -> None:
        self.client = client
        self.item_database = item_database
        self.cache_dir = root_dir / "cache"
        self.render_dir = self.cache_dir / "rendered"
        self.asset_dir = self.cache_dir / "assets"
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self._fonts = _Fonts()

    async def render(self, document: RenderDocument) -> Path:
        return (await self.render_pages(document))[0]

    async def render_pages(self, document: RenderDocument) -> list[Path]:
        resolved = self._resolved_assets(document)
        digest = self._digest(document, resolved)
        output = self.render_dir / f"{digest}.png"
        if self._is_fresh(output, self.client.config.image_cache_seconds):
            return await asyncio.to_thread(self._split_pages, output, digest)

        assets = await self._load_assets(resolved)
        await asyncio.to_thread(self._render_sync, document, resolved, assets, output)
        pages = await asyncio.to_thread(self._split_pages, output, digest)
        self._cleanup_old_files()
        return pages

    def _digest(self, document: RenderDocument, resolved: dict[tuple[str, str], _ResolvedAsset]) -> str:
        payload = {
            "renderer": "2026-04-22-tactical-4",
            "document": asdict(document),
            "assets": self._asset_digest_payload(resolved),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:24]

    def _resolved_assets(self, document: RenderDocument) -> dict[tuple[str, str], _ResolvedAsset]:
        resolved: dict[tuple[str, str], _ResolvedAsset] = {}
        for section in document.sections:
            for item in section.items:
                ref: ItemImageRef | None = None
                if self.item_database is not None:
                    ref = self.item_database.resolve_image_ref(item.name, item.image_url)
                elif item.image_url:
                    ref = ItemImageRef(url=item.image_url)
                if ref is not None and ref.url:
                    resolved[(item.name, item.image_url)] = _ResolvedAsset(ref.url, ref.local_path)
        return resolved

    def _asset_digest_payload(self, resolved: dict[tuple[str, str], _ResolvedAsset]) -> dict[str, dict[str, object]]:
        payload: dict[str, dict[str, object]] = {}
        for (name, fallback_url), ref in resolved.items():
            local_state: dict[str, object] | None = None
            if ref.local_path is not None:
                local_state = {"path": str(ref.local_path)}
                try:
                    stat = ref.local_path.stat()
                except OSError:
                    pass
                else:
                    local_state.update({"mtime_ns": stat.st_mtime_ns, "size": stat.st_size})
            payload[f"{name}\0{fallback_url}"] = {"url": ref.url, "local": local_state}
        return payload

    async def _load_assets(self, resolved: dict[tuple[str, str], _ResolvedAsset]) -> dict[str, Image.Image]:
        refs = {self._asset_source_key(ref): ref for ref in resolved.values() if ref.url}
        if not refs:
            return {}
        images = await asyncio.gather(*(self._load_asset(ref) for ref in refs.values()))
        return {key: image for key, image in zip(refs.keys(), images, strict=True) if image is not None}

    def _asset_source_key(self, ref: _ResolvedAsset) -> str:
        if ref.local_path is not None:
            return f"file:{ref.local_path}"
        return f"url:{ref.url}"

    async def _load_asset(self, ref: _ResolvedAsset) -> Image.Image | None:
        if ref.local_path is not None:
            image = self._open_cached_asset(ref.local_path)
            if image is not None:
                return image
        url = ref.url
        path = self.asset_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.img"
        if self._is_fresh(path, self.client.config.image_asset_cache_seconds):
            image = self._open_cached_asset(path)
            if image is not None:
                return image
        try:
            raw = await self.client.fetch_public_bytes(
                url,
                ttl_seconds=self.client.config.image_asset_cache_seconds,
                max_bytes=self.client.config.max_image_bytes,
            )
            path.write_bytes(raw)
        except Exception:
            if path.exists():
                return self._open_cached_asset(path, remove_invalid=False)
            return None
        image = self._open_cached_asset(path)
        if image is None:
            return None
        if self.item_database is not None:
            self.item_database.set_image_path(url, path)
        return image

    def _open_cached_asset(self, path: Path, remove_invalid: bool = True) -> Image.Image | None:
        try:
            return Image.open(path).convert("RGBA")
        except (OSError, UnidentifiedImageError):
            if remove_invalid:
                self._remove_cached_asset(path)
            return None

    def _remove_cached_asset(self, path: Path) -> None:
        try:
            if path.resolve().parent != self.asset_dir.resolve():
                return
            path.unlink(missing_ok=True)
        except OSError:
            return

    def _render_sync(
        self,
        document: RenderDocument,
        resolved: dict[tuple[str, str], _ResolvedAsset],
        assets: dict[str, Image.Image],
        output: Path,
    ) -> None:
        width = _TOKENS.width
        pad = _TOKENS.pad
        image = Image.new("RGB", (width, 1800), _TOKENS.page_bg)
        draw = ImageDraw.Draw(image)

        def ensure_height(required: int) -> None:
            nonlocal image, draw
            if required <= image.height:
                return
            new_height = max(required + 800, image.height * 2)
            expanded = Image.new("RGB", (width, new_height), _TOKENS.page_bg)
            expanded.paste(image, (0, 0))
            image = expanded
            draw = ImageDraw.Draw(image)

        y = self._draw_header(draw, document, pad, 32, width - pad * 2)

        if document.lines:
            for text in document.lines:
                ensure_height(y + 84)
                y = self._draw_briefing_bar(draw, text, pad, y, width - pad * 2)
                y += _TOKENS.gap

        for section in document.sections:
            ensure_height(y + 120)
            y += 12
            if _is_nav_section(section):
                nav_height = self._nav_section_height(draw, section, width - pad * 2)
                ensure_height(y + nav_height + _TOKENS.gap)
                y = self._draw_nav_section(draw, section, pad, y, width - pad * 2)
                y += _TOKENS.gap
                continue

            self._draw_section_title(draw, section.title, pad, y, len(section.items))
            y += 54
            if section.lines:
                summary_lines = _summary_lines(document.meta, section.lines)
                summary_height = self._summary_card_height(draw, summary_lines, width - pad * 2)
                ensure_height(y + summary_height + _TOKENS.gap)
                y = self._draw_summary_card(draw, "方案总览", summary_lines, pad, y, width - pad * 2)
                y += _TOKENS.gap
            for item in section.items:
                height = self._item_height(draw, item, width - pad * 2)
                ensure_height(y + height + 26)
                image_ref = resolved.get((item.name, item.image_url))
                asset_key = self._asset_source_key(image_ref) if image_ref is not None else ""
                self._draw_item(image, draw, item, assets.get(asset_key), pad, y, width - pad * 2, height)
                y += height + _TOKENS.gap

        final = image.crop((0, 0, width, min(image.height, y + 26)))
        final.save(output, format="PNG", optimize=True)

    def _split_pages(self, output: Path, digest: str) -> list[Path]:
        with Image.open(output) as image:
            if image.height <= self.client.config.max_render_page_height:
                return [output]
            pages: list[Path] = []
            page_height = self.client.config.max_render_page_height
            for index, top in enumerate(range(0, image.height, page_height), start=1):
                page = image.crop((0, top, image.width, min(image.height, top + page_height)))
                page_path = self.render_dir / f"{digest}_p{index}.png"
                if not self._is_fresh(page_path, self.client.config.image_cache_seconds):
                    page.save(page_path, format="PNG", optimize=True)
                pages.append(page_path)
            return pages

    def _item_height(self, draw: ImageDraw.ImageDraw, item: RenderItem, card_width: int) -> int:
        text_width = card_width - 388
        name_lines = _wrap_text(draw, item.name, self._fonts.item_name, text_width)
        primary = _primary_field(item.fields)
        chip_fields = _auxiliary_fields(item.fields, primary)
        chip_rows = _chip_rows(draw, chip_fields, self._fonts.badge, card_width - 420)
        line_rows = sum(max(1, len(_wrap_text(draw, line, self._fonts.small, card_width - 420))) for line in item.lines)
        badge_rows = _badge_rows(draw, item.badges, self._fonts.badge, 230) if item.badges else 0
        cost_height = 132 if _cost_field_groups(item.fields) else 0
        text_height = 34 + len(name_lines) * 36 + cost_height + max(0, chip_rows) * 42 + line_rows * 32
        return max(154, 30 + max(text_height, 106 + badge_rows * 36) + 28)

    def _draw_item(
        self,
        canvas: Image.Image,
        draw: ImageDraw.ImageDraw,
        item: RenderItem,
        item_image: Image.Image | None,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        _draw_shadow(draw, (x, y, x + width, y + height), _TOKENS.radius)
        draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=_TOKENS.radius,
            fill=_TOKENS.card,
            outline=_TOKENS.stroke,
            width=1,
        )
        icon_box = (x + 24, y + 24, x + 132, y + 132)
        if item_image is None:
            draw.rounded_rectangle(icon_box, radius=14, fill=_TOKENS.image_bg, outline="#dbe2e9", width=1)
            draw.line((x + 48, y + 82, x + 108, y + 54), fill="#c8d0d8", width=4)
            draw.ellipse((x + 52, y + 52, x + 68, y + 68), fill="#cfd7df")
        else:
            icon = _fit_image(item_image, 108, 108)
            draw.rounded_rectangle(icon_box, radius=14, fill=_TOKENS.image_bg)
            canvas.paste(icon, (x + 24, y + 24), icon)

        if item.rank:
            _draw_pill(draw, f"#{item.rank}", x + 18, y + 18, self._fonts.badge, "rank")

        tx = x + 154
        right_w = 232
        tw = width - 184 - right_w
        primary = _primary_field(item.fields)
        grade = _field_value(item.fields, "等级")
        ty = y + 26
        name_lines = _wrap_text(draw, item.name, self._fonts.item_name, tw)
        for line in name_lines[:2]:
            draw.text((tx, ty), line, font=self._fonts.item_name, fill=_TOKENS.text)
            ty += 36
        if grade:
            _draw_pill(draw, f"{grade}级", tx, ty + 2, self._fonts.badge, "neutral")
            ty += 40

        cost_groups = _cost_field_groups(item.fields)
        if cost_groups:
            ty = self._draw_cost_columns(draw, cost_groups, tx, ty + 8, tw)

        chip_fields = _auxiliary_fields(item.fields, primary)
        ty = _draw_chip_flow(draw, chip_fields, tx, ty + 4, tw, self._fonts.badge)
        for line in item.lines:
            for wrapped in _wrap_text(draw, line, self._fonts.small, tw):
                draw.text((tx, ty + 4), wrapped, font=self._fonts.small, fill=_TOKENS.muted)
                ty += 32

        rx = x + width - right_w - 24
        if primary:
            draw.text((rx, y + 30), primary[0], font=self._fonts.tiny, fill=_TOKENS.subtle)
            value_font = self._fonts.metric if len(primary[1]) <= 10 else self._fonts.item_name
            _draw_right_text(draw, primary[1], x + width - 26, y + 58, value_font, _semantic_color(primary[0], primary[1]))
        by = y + 104 if primary else y + 30
        for badge in item.badges[:4]:
            bw = _text_width(draw, badge, self._fonts.badge) + 28
            _draw_pill(draw, badge, x + width - 26 - bw, by, self._fonts.badge, _badge_tone(badge))
            by += 36

    def _draw_cost_columns(
        self,
        draw: ImageDraw.ImageDraw,
        groups: dict[str, list[tuple[str, str]]],
        x: int,
        y: int,
        width: int,
    ) -> int:
        height = 124
        gap = 10
        col_w = (width - gap) // 2
        for index, title in enumerate(("兑换", "购买")):
            cx = x + index * (col_w + gap)
            draw.rounded_rectangle((cx, y, cx + col_w, y + height), radius=14, fill="#eef2f4")
            draw.text((cx + 14, y + 10), title, font=self._fonts.tiny, fill=_TOKENS.text)
            fields = groups.get(title, [])
            if not fields:
                draw.text((cx + 14, y + 44), "本项未使用", font=self._fonts.tiny, fill=_TOKENS.subtle)
                continue
            row_y = y + 38
            for key, value in fields[:4]:
                draw.text((cx + 14, row_y), key, font=self._fonts.tiny, fill=_TOKENS.subtle)
                _draw_right_text(
                    draw,
                    _clip_text(draw, value, self._fonts.tiny, col_w - 82),
                    cx + col_w - 14,
                    row_y,
                    self._fonts.tiny,
                    _semantic_color(key, value),
                )
                row_y += 24
        return y + height + 8

    def _cleanup_old_files(self) -> None:
        cutoff = time.time() - max(3600, self.client.config.image_cache_seconds * 4)
        for path in self.render_dir.glob("*.png"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue

    def _is_fresh(self, path: Path, ttl_seconds: int | float) -> bool:
        try:
            stat = path.stat()
        except OSError:
            return False
        return time.time() - stat.st_mtime < float(ttl_seconds)

    def _draw_header(
        self,
        draw: ImageDraw.ImageDraw,
        document: RenderDocument,
        x: int,
        y: int,
        width: int,
    ) -> int:
        height = 224
        _draw_shadow(draw, (x, y, x + width, y + height), _TOKENS.header_radius, alpha=34)
        draw.rounded_rectangle((x, y, x + width, y + height), radius=_TOKENS.header_radius, fill=_TOKENS.dark)
        draw.rectangle((x, y + height - 20, x + width, y + height), fill=_TOKENS.dark)
        draw.rounded_rectangle((x + 28, y + 28, x + 132, y + 40), radius=6, fill=_TOKENS.green)
        draw.rounded_rectangle((x + width - 140, y + 28, x + width - 46, y + 40), radius=6, fill=_TOKENS.orange)
        draw.text((x + 32, y + 56), document.author, font=self._fonts.brand, fill="#ffffff")
        draw.text((x + 34, y + 116), document.title, font=self._fonts.title, fill="#e9edf2")
        subtitle = _header_subtitle(document)
        for line in _wrap_text(draw, subtitle, self._fonts.subtitle, width - 70):
            draw.text((x + 36, y + 166), line, font=self._fonts.subtitle, fill="#aeb9c7")
            break

        chip_x = x + width - 36
        for meta in reversed(document.meta[:3]):
            label = _compact_meta(meta)
            chip_w = _text_width(draw, label, self._fonts.tiny) + 30
            chip_x -= chip_w
            _draw_pill(draw, label, chip_x, y + 58, self._fonts.tiny, "dark")
            chip_x -= 10
        return y + height + 28

    def _draw_briefing_bar(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: int,
        y: int,
        width: int,
    ) -> int:
        lines = _wrap_text(draw, text, self._fonts.body, width - 64)
        height = 58 + (len(lines) - 1) * 30
        _draw_shadow(draw, (x, y, x + width, y + height), _TOKENS.radius, alpha=18)
        draw.rounded_rectangle((x, y, x + width, y + height), radius=_TOKENS.radius, fill="#f7f8f5")
        draw.rounded_rectangle((x + 18, y + 17, x + 28, y + height - 17), radius=5, fill=_TOKENS.green)
        ty = y + 15
        for line in lines:
            draw.text((x + 44, ty), line, font=self._fonts.body, fill=_TOKENS.text)
            ty += 30
        return y + height

    def _draw_section_title(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        x: int,
        y: int,
        item_count: int,
    ) -> None:
        draw.rounded_rectangle((x, y + 9, x + 12, y + 45), radius=6, fill=_TOKENS.green)
        draw.text((x + 24, y), title, font=self._fonts.section, fill=_TOKENS.text)
        if item_count:
            label = f"{item_count} 项情报"
            chip_w = _text_width(draw, label, self._fonts.badge) + 28
            _draw_pill(draw, label, x + _TOKENS.content_width - chip_w, y + 4, self._fonts.badge, "neutral")

    def _nav_section_height(
        self,
        draw: ImageDraw.ImageDraw,
        section: RenderSection,
        width: int,
    ) -> int:
        height = 82
        for item in section.items:
            desc = _field_value(item.fields, "说明")
            name_lines = _wrap_text(draw, item.name, self._fonts.item_name, width - 250)[:2]
            desc_lines = _wrap_text(draw, desc, self._fonts.small, width - 60)[:2] if desc else []
            height += max(78, 18 + len(name_lines) * 34 + len(desc_lines) * 28)
        return height + 16

    def _draw_nav_section(
        self,
        draw: ImageDraw.ImageDraw,
        section: RenderSection,
        x: int,
        y: int,
        width: int,
    ) -> int:
        height = self._nav_section_height(draw, section, width)
        _draw_shadow(draw, (x, y, x + width, y + height), _TOKENS.radius)
        draw.rounded_rectangle((x, y, x + width, y + height), radius=_TOKENS.radius, fill=_TOKENS.card)
        draw.rounded_rectangle((x + 24, y + 24, x + 36, y + 56), radius=6, fill=_TOKENS.green)
        draw.text((x + 50, y + 17), section.title, font=self._fonts.section, fill=_TOKENS.text)
        cy = y + 76
        for index, item in enumerate(section.items):
            desc = _field_value(item.fields, "说明")
            row_top = cy
            name_lines = _wrap_text(draw, item.name, self._fonts.item_name, width - 250)[:2]
            desc_lines = _wrap_text(draw, desc, self._fonts.small, width - 60)[:2] if desc else []
            row_h = max(78, 18 + len(name_lines) * 34 + len(desc_lines) * 28)
            if index:
                draw.line((x + 28, cy - 10, x + width - 28, cy - 10), fill="#e4e8ed", width=1)
            ty = row_top + 4
            for line in name_lines:
                draw.text((x + 30, ty), line, font=self._fonts.item_name, fill=_TOKENS.text)
                ty += 34
            for line in desc_lines[:2]:
                draw.text((x + 30, ty), line, font=self._fonts.small, fill=_TOKENS.muted)
                ty += 28
            bx = x + width - 30
            for badge in item.badges[:2]:
                bw = _text_width(draw, badge, self._fonts.badge) + 28
                bx -= bw
                _draw_pill(draw, badge, bx, row_top + 8, self._fonts.badge, _badge_tone(badge))
                bx -= 8
            cy += row_h
        return y + height

    def _summary_card_height(
        self,
        draw: ImageDraw.ImageDraw,
        lines: Sequence[str],
        width: int,
    ) -> int:
        stats = [_parse_key_value(line) for line in lines if _parse_key_value(line)]
        if not stats:
            return 84
        rows = (len(stats) + 2) // 3
        return 78 + rows * 82

    def _draw_summary_card(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        lines: Sequence[str],
        x: int,
        y: int,
        width: int,
    ) -> int:
        stats = [item for item in (_parse_key_value(line) for line in lines) if item]
        height = self._summary_card_height(draw, lines, width)
        _draw_shadow(draw, (x, y, x + width, y + height), _TOKENS.radius)
        draw.rounded_rectangle((x, y, x + width, y + height), radius=_TOKENS.radius, fill=_TOKENS.card)
        draw.text((x + 28, y + 22), title, font=self._fonts.body, fill=_TOKENS.text)
        col_w = (width - 56 - 24 * 2) // 3
        for index, (key, value) in enumerate(stats):
            row = index // 3
            col = index % 3
            sx = x + 28 + col * (col_w + 24)
            sy = y + 68 + row * 82
            draw.rounded_rectangle((sx, sy, sx + col_w, sy + 62), radius=14, fill="#eef2f4")
            draw.text((sx + 16, sy + 11), key, font=self._fonts.tiny, fill=_TOKENS.subtle)
            _draw_right_text(
                draw,
                value,
                sx + col_w - 16,
                sy + 28,
                self._fonts.badge,
                _semantic_color(key, value),
            )
        return y + height


class _Fonts:
    def __init__(self) -> None:
        font_path = _find_font()
        self.title = _load_font(font_path, 38)
        self.brand = _load_font(font_path, 34)
        self.section = _load_font(font_path, 31)
        self.item_name = _load_font(font_path, 28)
        self.metric = _load_font(font_path, 32)
        self.body = _load_font(font_path, 26)
        self.small = _load_font(font_path, 23)
        self.badge = _load_font(font_path, 21)
        self.subtitle = _load_font(font_path, 23)
        self.tiny = _load_font(font_path, 19)


class _Tokens:
    width = 1000
    pad = 38
    content_width = width - pad * 2
    gap = 16
    radius = 18
    header_radius = 20
    page_bg = "#eceff2"
    card = "#f8f9fb"
    dark = "#111820"
    text = "#18212b"
    muted = "#556170"
    subtle = "#7a8594"
    stroke = "#d9dee5"
    image_bg = "#eef2f4"
    green = "#39b878"
    green_bg = "#e4f5ec"
    orange = "#e15f3f"
    orange_bg = "#fae7df"
    neutral_bg = "#e9edf1"
    shadow = "#c9d0d7"


_TOKENS = _Tokens()


def _is_nav_section(section: RenderSection) -> bool:
    return bool(section.items) and all(_field_value(item.fields, "说明") for item in section.items)


def _summary_lines(meta: Sequence[str], section_lines: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    for line in meta:
        if line.startswith("档位：") or line.startswith("更新时间："):
            result.append(line)
    result.extend(section_lines)
    return tuple(result)


def _parse_key_value(line: str) -> tuple[str, str] | None:
    if "：" in line:
        key, value = line.split("：", 1)
    elif ":" in line:
        key, value = line.split(":", 1)
    else:
        return None
    key = key.strip()
    value = value.strip()
    if not key or not value:
        return None
    return key, value


def _field_value(fields: Sequence[tuple[str, str]], key: str) -> str:
    for field_key, value in fields:
        if field_key == key and value:
            return value
    return ""


def _primary_field(fields: Sequence[tuple[str, str]]) -> tuple[str, str] | None:
    priorities = ("价格", "最新价", "总价", "每小时", "到手", "收益")
    for priority in priorities:
        value = _field_value(fields, priority)
        if value:
            return priority, value
    for key, value in fields:
        if value:
            return key, value
    return None


def _auxiliary_fields(
    fields: Sequence[tuple[str, str]],
    primary: tuple[str, str] | None,
) -> list[tuple[str, str]]:
    hidden = {primary[0] if primary else "", "等级"}
    return [
        (key, value)
        for key, value in fields
        if value and key not in hidden and not _is_cost_field(key)
    ]


def _cost_field_groups(fields: Sequence[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    groups = {"兑换": [], "购买": []}
    for key, value in fields:
        if not value:
            continue
        if key.startswith("兑换"):
            groups["兑换"].append((key.removeprefix("兑换") or "价格", value))
        elif key in {"限购", "刷新"}:
            groups["兑换"].append((key, value))
        elif key.startswith("购买"):
            groups["购买"].append((key.removeprefix("购买") or "价格", value))
    return {key: value for key, value in groups.items() if value}


def _is_cost_field(key: str) -> bool:
    return key.startswith(("兑换", "购买")) or key in {"限购", "刷新"}


def _header_subtitle(document: RenderDocument) -> str:
    if document.lines:
        return document.lines[0]
    if document.summary:
        return document.summary
    return "查询结果已整理。"


def _compact_meta(meta: str) -> str:
    if "：" in meta:
        key, value = meta.split("：", 1)
        if key in {"更新时间", "查询时间", "筛选项更新时间"}:
            return value.strip()
    return meta.strip()


def _draw_shadow(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    alpha: int = 26,
) -> None:
    x1, y1, x2, y2 = box
    color = _TOKENS.shadow
    for offset, shrink in ((8, 0), (4, 2)):
        draw.rounded_rectangle(
            (x1 + shrink, y1 + offset, x2 - shrink, y2 + offset),
            radius=radius,
            fill=color,
        )


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    tone: str,
) -> int:
    fill, text_fill, outline = _pill_colors(tone)
    width = _text_width(draw, text, font) + 28
    height = 30
    draw.rounded_rectangle((x, y, x + width, y + height), radius=15, fill=fill, outline=outline, width=1)
    draw.text((x + 14, y + 4), text, font=font, fill=text_fill)
    return width


def _pill_colors(tone: str) -> tuple[str, str, str]:
    if tone == "green":
        return _TOKENS.green_bg, "#17633f", "#bde4cf"
    if tone == "orange":
        return _TOKENS.orange_bg, "#94351f", "#f1c5b6"
    if tone == "rank":
        return _TOKENS.dark, "#ffffff", _TOKENS.dark
    if tone == "dark":
        return "#1f2933", "#dfe6ee", "#31404f"
    return _TOKENS.neutral_bg, "#344150", "#d4dbe2"


def _badge_tone(text: str) -> str:
    if any(word in text for word in ("上涨", "增加", "正值")):
        return "green"
    if any(word in text for word in ("下跌", "减少", "负值")):
        return "orange"
    return "neutral"


def _semantic_color(key: str, value: str) -> str:
    text = f"{key}{value}"
    if value.strip().startswith("-"):
        return _TOKENS.orange
    if any(word in text for word in ("差值", "变化", "涨跌", "收益", "节省")):
        return _TOKENS.green if not value.strip().startswith("-") else _TOKENS.orange
    if key in {"价格", "最新价", "总价", "每小时", "到手", "战备", "战备值"}:
        return _TOKENS.text
    return _TOKENS.muted


def _draw_chip_flow(
    draw: ImageDraw.ImageDraw,
    fields: Sequence[tuple[str, str]],
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.ImageFont,
) -> int:
    cx = x
    cy = y
    row_height = 38
    for key, value in fields:
        text = f"{key} {value}"
        chip_width = min(max_width, _text_width(draw, text, font) + 30)
        if cx > x and cx + chip_width > x + max_width:
            cx = x
            cy += row_height
        fill, text_fill, outline = _pill_colors("neutral")
        if _semantic_color(key, value) == _TOKENS.green:
            fill, text_fill, outline = _pill_colors("green")
        elif _semantic_color(key, value) == _TOKENS.orange:
            fill, text_fill, outline = _pill_colors("orange")
        draw.rounded_rectangle((cx, cy, cx + chip_width, cy + 30), radius=15, fill=fill, outline=outline, width=1)
        label = _clip_text(draw, text, font, chip_width - 28)
        draw.text((cx + 14, cy + 4), label, font=font, fill=text_fill)
        cx += chip_width + 8
    return cy + (row_height if fields else 0)


def _chip_rows(
    draw: ImageDraw.ImageDraw,
    fields: Sequence[tuple[str, str]],
    font: ImageFont.ImageFont,
    max_width: int,
) -> int:
    if not fields:
        return 0
    rows = 1
    cx = 0
    for key, value in fields:
        chip_width = min(max_width, _text_width(draw, f"{key} {value}", font) + 30)
        if cx and cx + chip_width > max_width:
            rows += 1
            cx = 0
        cx += chip_width + 8
    return rows


def _badge_rows(
    draw: ImageDraw.ImageDraw,
    badges: Sequence[str],
    font: ImageFont.ImageFont,
    max_width: int,
) -> int:
    if not badges:
        return 0
    rows = 1
    x = 0
    for badge in badges:
        width = _text_width(draw, badge, font) + 28
        if x and x + width > max_width:
            rows += 1
            x = 0
        x += width + 8
    return rows


def _draw_right_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    right: int,
    y: int,
    font: ImageFont.ImageFont,
    fill: str,
) -> None:
    draw.text((right - _text_width(draw, text, font), y), text, font=font, fill=fill)


def _clip_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if _text_width(draw, text, font) <= max_width:
        return text
    ellipsis = "..."
    result = ""
    for char in text:
        if _text_width(draw, result + char + ellipsis, font) > max_width:
            return result + ellipsis
        result += char
    return result


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def money(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return "未知"


def number(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "未知"
    if n.is_integer():
        return str(int(n))
    return f"{n:.2f}".rstrip("0").rstrip(".")


def first_text(value: object, default: str = "未知") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def trend_summary(prices: Sequence[object]) -> str:
    values: list[int] = []
    for item in prices:
        try:
            values.append(int(float(item)))
        except (TypeError, ValueError):
            continue
    if len(values) < 2:
        return "趋势：数据不足"
    start = values[0]
    end = values[-1]
    delta = end - start
    sign = "+" if delta > 0 else ""
    return f"24h趋势：{sign}{money(delta)}"


def compact_lines(lines: Iterable[str]) -> str:
    return "\n".join(line.rstrip() for line in lines if line is not None).strip()


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str,
) -> int:
    for line in _wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += 30
    return y


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    result: list[str] = []
    for raw_line in str(text).splitlines() or [""]:
        current = ""
        for char in raw_line:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if current and bbox[2] - bbox[0] > max_width:
                result.append(current)
                current = char
            else:
                current = test
        result.append(current)
    return result


def _fit_image(image: Image.Image, width: int, height: int) -> Image.Image:
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    working = image.copy()
    working.thumbnail((width, height), Image.Resampling.LANCZOS)
    x = (width - working.width) // 2
    y = (height - working.height) // 2
    canvas.alpha_composite(working, (x, y))
    return canvas


def _find_font() -> str | None:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def _load_font(path: str | None, size: int) -> ImageFont.ImageFont:
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()
