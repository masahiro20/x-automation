"""投稿に添える図解画像（比較表・チェックリスト）を PNG で描く。"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
PADDING = 56
MIN_HEIGHT = 675
MAX_HEIGHT = 1500

BG = (248, 249, 251)
HEADER_BG = (22, 34, 56)
HEADER_FG = (255, 255, 255)
TEXT = (28, 32, 40)
SUBTLE = (110, 118, 130)
ACCENT = (255, 140, 0)
ROW_ALT = (236, 240, 245)
TABLE_HEAD_BG = (52, 72, 104)
LINE = (210, 216, 224)

FONT_CANDIDATES = {
    "bold": [
        os.environ.get("FONT_BOLD", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    ],
    "regular": [
        os.environ.get("FONT_REGULAR", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ],
}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES[weight]:
        if path and Path(path).exists():
            # .ttc の index 0 は日本語（JP）
            return ImageFont.truetype(path, size, index=0)
    raise FileNotFoundError("日本語フォント（Noto Sans CJK）が見つかりません")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """1 文字ずつ幅を測って折り返す（日本語は単語区切りがないため）。"""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        line = ""
        for ch in paragraph:
            if draw.textlength(line + ch, font=font) > max_width and line:
                lines.append(line)
                line = ch
            else:
                line += ch
        lines.append(line)
    return lines


def _line_height(font) -> int:
    ascent, descent = font.getmetrics()
    return int((ascent + descent) * 1.25)


class _Canvas:
    """高さが決まる前に描画内容を積んでおき、最後にまとめて描く。"""

    def __init__(self) -> None:
        self.ops: list[tuple] = []
        self.y = 0

    def add(self, *op) -> None:
        self.ops.append(op)


def _layout_header(c: _Canvas, measure, title: str) -> None:
    font = _font("bold", 52)
    lines = _wrap(measure, title, font, WIDTH - PADDING * 2)
    lh = _line_height(font)
    height = PADDING + lh * len(lines) + PADDING // 2
    c.add("rect", (0, 0, WIDTH, height), HEADER_BG)
    c.add("rect", (0, height, WIDTH, height + 8), ACCENT)
    for i, line in enumerate(lines):
        c.add("text", (PADDING, PADDING * 0.8 + lh * i), line, font, HEADER_FG)
    c.y = height + 8 + PADDING // 2


def _layout_table(c: _Canvas, measure, headers: list[str], rows: list[list[str]]) -> None:
    ncol = max(len(headers), max((len(r) for r in rows), default=0))
    if ncol == 0:
        return
    headers = headers + [""] * (ncol - len(headers))
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    inner = WIDTH - PADDING * 2
    # 列幅は各列の最長文字数に比例させる（極端に狭くならないよう下限を置く）
    longest = [max(len(str(x)) for x in [headers[i]] + [r[i] for r in rows]) for i in range(ncol)]
    weights = [max(n, 4) for n in longest]
    widths = [int(inner * w / sum(weights)) for w in weights]
    cell_pad = 16
    head_font = _font("bold", 30)
    body_font = _font("regular", 30)
    first_col_font = _font("bold", 30)

    def layout_row(cells, fonts, bg, fg):
        wrapped = [
            _wrap(measure, str(cell), f, w - cell_pad * 2) for cell, f, w in zip(cells, fonts, widths)
        ]
        lh = _line_height(body_font)
        h = max(len(w) for w in wrapped) * lh + cell_pad * 2
        c.add("rect", (PADDING, c.y, PADDING + inner, c.y + h), bg)
        x = PADDING
        for lines, f, w in zip(wrapped, fonts, widths):
            for i, line in enumerate(lines):
                c.add("text", (x + cell_pad, c.y + cell_pad + lh * i), line, f, fg)
            x += w
        c.y += h

    layout_row(headers, [head_font] * ncol, TABLE_HEAD_BG, HEADER_FG)
    for i, row in enumerate(rows):
        fonts = [first_col_font] + [body_font] * (ncol - 1)
        layout_row(row, fonts, ROW_ALT if i % 2 else BG, TEXT)
        c.add("rect", (PADDING, c.y, PADDING + inner, c.y + 1), LINE)
    c.y += PADDING // 2


def _layout_checklist(c: _Canvas, measure, items: list[str]) -> None:
    font = _font("regular", 36)
    mark_font = _font("bold", 36)
    lh = _line_height(font)
    indent = 64
    for item in items:
        lines = _wrap(measure, item, font, WIDTH - PADDING * 2 - indent)
        c.add("text", (PADDING, c.y), "✓", mark_font, ACCENT)
        for i, line in enumerate(lines):
            c.add("text", (PADDING + indent, c.y + lh * i), line, font, TEXT)
        c.y += lh * len(lines) + 18
    c.y += PADDING // 2


def _layout_footer(c: _Canvas, measure, note: str) -> None:
    if not note:
        return
    font = _font("regular", 24)
    lh = _line_height(font)
    for line in _wrap(measure, note, font, WIDTH - PADDING * 2):
        c.add("text", (PADDING, c.y), line, font, SUBTLE)
        c.y += lh
    c.y += PADDING // 2


def render(spec: dict, out_path: Path) -> Path:
    """spec: {kind: "table"|"checklist", title, headers, rows, items, note}"""
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    c = _Canvas()
    _layout_header(c, measure, spec["title"])
    if spec["kind"] == "table":
        _layout_table(c, measure, spec.get("headers", []), spec.get("rows", []))
    else:
        _layout_checklist(c, measure, spec.get("items", []))
    _layout_footer(c, measure, spec.get("note", ""))

    height = min(max(int(c.y + PADDING // 2), MIN_HEIGHT), MAX_HEIGHT)
    img = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(img)
    for op in c.ops:
        if op[0] == "rect":
            draw.rectangle(op[1], fill=op[2])
        else:
            _, xy, text, font, fill = op
            draw.text(xy, text, font=font, fill=fill)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path
