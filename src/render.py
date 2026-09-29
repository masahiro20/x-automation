"""投稿に添える図解画像（比較表・チェックリスト・数字カード）を PNG で描く。

X のタイムラインで目に止まり、保存されやすい「手作りの図解」に寄せたデザイン。
- 見出しは大きく、キーワードに黄色マーカー
- 比較表は ◎○△× を色付きの記号で、おすすめ列にバッジ
- 一番下に一言の結論バー、右下にアカウント名
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
PAD = 64
MIN_HEIGHT = 675
MAX_HEIGHT = 1500
BRAND = "ガジェットの選び方ノート"

BG = (255, 250, 243)
CARD = (255, 255, 255)
NAVY = (26, 36, 58)
TEXT = (40, 44, 52)
SUBTLE = (128, 132, 140)
ORANGE = (255, 118, 0)
ORANGE_SOFT = (255, 240, 224)
MARKER = (255, 221, 51)
LINE = (232, 226, 216)
HEAD_BG = (241, 236, 228)
VERDICT_COLORS = {"買い": (22, 150, 80), "待ち": (255, 118, 0), "見送り": (120, 124, 132)}
STAMP = 170
SYMBOL_COLORS = {"◎": (22, 150, 80), "○": (40, 110, 200), "△": (230, 150, 0), "×": (215, 50, 50)}

FONT_CANDIDATES = {
    "bold": [
        os.environ.get("FONT_BOLD", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    ],
    "medium": [
        os.environ.get("FONT_MEDIUM", ""),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
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


def _lh(font, ratio: float = 1.3) -> int:
    ascent, descent = font.getmetrics()
    return int((ascent + descent) * ratio)


def _draw_verdict(img: Image.Image, verdict: str) -> None:
    """右上に「判定」のハンコを少し傾けて押す。"""
    color = VERDICT_COLORS.get(verdict)
    if not color:
        return
    stamp = Image.new("RGBA", (STAMP, STAMP), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stamp)
    sd.ellipse((4, 4, STAMP - 4, STAMP - 4), fill=(255, 255, 255, 255), outline=color + (255,), width=8)
    sd.ellipse((18, 18, STAMP - 18, STAMP - 18), outline=color + (255,), width=3)
    label_font = _font("bold", 22)
    font = _font("bold", 50 if len(verdict) <= 2 else 38)
    lw = sd.textlength("判定", font=label_font)
    sd.text(((STAMP - lw) / 2, 34), "判定", font=label_font, fill=color + (255,))
    vw = sd.textlength(verdict, font=font)
    sd.text(((STAMP - vw) / 2, 62 if len(verdict) <= 2 else 70), verdict, font=font, fill=color + (255,))
    stamp = stamp.rotate(12, resample=Image.BICUBIC, expand=False)
    img.paste(stamp, (WIDTH - PAD - STAMP + 10, PAD - 20), stamp)


def _balance(d, text: str, font, max_w: int) -> list[str] | None:
    """2 行目に 1〜3 文字だけ残る折り返しを避ける。「、」の後ろ、なければ真ん中あたりで分ける。"""
    candidates = [i + 1 for i, ch in enumerate(text) if ch in "、，,"]
    mid = len(text) // 2
    candidates += sorted(range(1, len(text)), key=lambda i: abs(i - mid))
    for i in candidates:
        a, b = text[:i], text[i:]
        if len(b) > 3 and d.textlength(a, font=font) <= max_w and d.textlength(b, font=font) <= max_w:
            return [a, b]
    return None


def _draw_title(d: ImageDraw.ImageDraw, y: int, tag: str, title: str, highlight: str, reserve: int = 0) -> int:
    if tag:
        tag_font = _font("bold", 28)
        w = int(d.textlength(tag, font=tag_font)) + 36
        d.rounded_rectangle((PAD, y, PAD + w, y + 48), radius=24, fill=ORANGE)
        d.text((PAD + 18, y + 6), tag, font=tag_font, fill=(255, 255, 255))
        y += 72
    size = 66
    font = _font("bold", size)
    lh = int(size * 1.4)
    max_w = WIDTH - PAD * 2 - reserve
    lines = _wrap(d, title, font, max_w)
    if len(lines) == 2 and len(lines[1]) <= 3:
        lines = _balance(d, title, font, max_w) or lines
    for line in lines:
        if highlight and highlight in line:
            # キーワードの下半分に黄色マーカーを引く
            x0 = PAD + d.textlength(line[: line.index(highlight)], font=font)
            x1 = x0 + d.textlength(highlight, font=font)
            d.rectangle((x0 - 4, y + size * 0.72, x1 + 4, y + size * 1.28), fill=MARKER)
        d.text((PAD, y), line, font=font, fill=NAVY)
        y += lh
    return y + 28


def _draw_table(d, y: int, headers: list[str], rows: list[list[str]], recommend_col: int) -> int:
    ncol = max(len(headers), max((len(r) for r in rows), default=0))
    if ncol == 0:
        return y
    headers = headers + [""] * (ncol - len(headers))
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    inner = WIDTH - PAD * 2
    longest = [max(len(str(x)) for x in [headers[i]] + [r[i] for r in rows]) for i in range(ncol)]
    weights = [max(n, 5) for n in longest]
    widths = [int(inner * w / sum(weights)) for w in weights]
    xs = [PAD + sum(widths[:i]) for i in range(ncol)]
    cp = 20
    head_font = _font("bold", 32)
    label_font = _font("bold", 30)
    body_font = _font("medium", 30)
    symbol_font = _font("bold", 44)
    has_rec = 0 < recommend_col < ncol

    # 見出し行の上に「おすすめ」バッジを載せる余白
    if has_rec:
        y += 30
    top = y

    def cell_lines(text, font, w):
        return _wrap(d, str(text), font, w - cp * 2)

    # 行ごとの高さを先に計算する
    head_lines = [cell_lines(h, head_font, w) for h, w in zip(headers, widths)]
    head_h = max(len(ls) for ls in head_lines) * _lh(head_font) + cp * 2
    row_layouts = []
    for row in rows:
        cells = []
        for i, (cell, w) in enumerate(zip(row, widths)):
            if cell in SYMBOL_COLORS:
                cells.append(("symbol", cell))
            else:
                cells.append(("text", cell_lines(cell, label_font if i == 0 else body_font, w)))
        n = max((len(c[1]) if c[0] == "text" else 1) for c in cells)
        row_h = max(n * _lh(body_font), _lh(symbol_font, 1.1)) + cp * 2
        row_layouts.append((cells, row_h))
    bottom = top + head_h + sum(h for _, h in row_layouts)

    # カード本体と、おすすめ列の下地
    d.rounded_rectangle((PAD, top, PAD + inner, bottom), radius=20, fill=CARD, outline=LINE, width=2)
    d.rounded_rectangle((PAD, top, PAD + inner, top + head_h), radius=20, fill=HEAD_BG)
    d.rectangle((PAD, top + head_h - 20, PAD + inner, top + head_h), fill=HEAD_BG)
    if has_rec:
        x0, x1 = xs[recommend_col], xs[recommend_col] + widths[recommend_col]
        d.rounded_rectangle((x0 + 4, top - 26, x1 - 4, bottom - 4), radius=16, fill=ORANGE_SOFT, outline=ORANGE, width=4)
        badge_font = _font("bold", 26)
        label = "おすすめ"
        bw = d.textlength(label, font=badge_font) + 32
        bx = x0 + (widths[recommend_col] - bw) / 2
        d.rounded_rectangle((bx, top - 44, bx + bw, top - 4), radius=20, fill=ORANGE)
        d.text((bx + 16, top - 41), label, font=badge_font, fill=(255, 255, 255))

    # 見出し行
    for x, w, lines in zip(xs, widths, head_lines):
        for j, line in enumerate(lines):
            tw = d.textlength(line, font=head_font)
            d.text((x + (w - tw) / 2, top + cp + j * _lh(head_font)), line, font=head_font, fill=NAVY)

    # データ行
    ry = top + head_h
    for r, (cells, row_h) in enumerate(row_layouts):
        if r > 0:
            d.line((PAD + 16, ry, PAD + inner - 16, ry), fill=LINE, width=2)
        for i, ((kind, content), x, w) in enumerate(zip(cells, xs, widths)):
            if kind == "symbol":
                tw = d.textlength(content, font=symbol_font)
                d.text((x + (w - tw) / 2, ry + (row_h - _lh(symbol_font, 1.1)) / 2), content,
                       font=symbol_font, fill=SYMBOL_COLORS[content])
                continue
            font = label_font if i == 0 else body_font
            color = SUBTLE if i == 0 else TEXT
            block_h = len(content) * _lh(font)
            for j, line in enumerate(content):
                tw = d.textlength(line, font=font)
                tx = x + cp if i == 0 else x + (w - tw) / 2
                d.text((tx, ry + (row_h - block_h) / 2 + j * _lh(font)), line, font=font, fill=color)
        ry += row_h
    return bottom + 36


def _draw_checklist(d, y: int, items: list[str]) -> int:
    font = _font("medium", 36)
    num_font = _font("bold", 30)
    lh = _lh(font)
    for n, item in enumerate(items, 1):
        lines = _wrap(d, item, font, WIDTH - PAD * 2 - 130)
        h = max(len(lines) * lh, 64) + 36
        d.rounded_rectangle((PAD, y, WIDTH - PAD, y + h), radius=18, fill=CARD, outline=LINE, width=2)
        cy = y + h / 2
        d.ellipse((PAD + 28, cy - 28, PAD + 84, cy + 28), fill=ORANGE)
        num = str(n)
        d.text((PAD + 56 - d.textlength(num, font=num_font) / 2, cy - 22), num, font=num_font, fill=(255, 255, 255))
        ty = y + (h - len(lines) * lh) / 2 + 6
        for j, line in enumerate(lines):
            d.text((PAD + 112, ty + j * lh), line, font=font, fill=TEXT)
        y += h + 16
    return y + 20


def _draw_number(d, y: int, big_text: str, caption: str) -> int:
    inner = WIDTH - PAD * 2
    size = 150
    font = _font("bold", size)
    while d.textlength(big_text, font=font) > inner - 60 and size > 60:
        size -= 10
        font = _font("bold", size)
    h = _lh(font, 1.15) + 60
    d.rounded_rectangle((PAD, y, WIDTH - PAD, y + h), radius=24, fill=CARD, outline=LINE, width=2)
    # 「A → B」は A を灰色、B をオレンジで
    parts = big_text.split("→", 1)
    total = d.textlength(big_text, font=font)
    x = PAD + (inner - total) / 2
    ty = y + 24
    if len(parts) == 2:
        left, right = parts[0], "→" + parts[1]
        d.text((x, ty), left, font=font, fill=SUBTLE)
        d.text((x + d.textlength(left, font=font), ty), right, font=font, fill=ORANGE)
    else:
        d.text((x, ty), big_text, font=font, fill=ORANGE)
    y += h + 20
    if caption:
        cap_font = _font("bold", 42)
        for line in _wrap(d, caption, cap_font, inner):
            d.text((PAD + (inner - d.textlength(line, font=cap_font)) / 2, y), line, font=cap_font, fill=NAVY)
            y += _lh(cap_font)
    return y + 28


def _draw_conclusion(d, y: int, text: str) -> int:
    if not text:
        return y
    label_font = _font("bold", 30)
    font = _font("bold", 38)
    label = "結論"
    lw = d.textlength(label, font=label_font) + 36
    lines = _wrap(d, text, font, WIDTH - PAD * 2 - lw - 60)
    h = max(len(lines) * _lh(font), 60) + 40
    d.rounded_rectangle((PAD, y, WIDTH - PAD, y + h), radius=18, fill=NAVY)
    d.rounded_rectangle((PAD + 20, y + h / 2 - 24, PAD + 20 + lw, y + h / 2 + 24), radius=12, fill=ORANGE)
    d.text((PAD + 38, y + h / 2 - 20), label, font=label_font, fill=(255, 255, 255))
    ty = y + (h - len(lines) * _lh(font)) / 2
    for j, line in enumerate(lines):
        d.text((PAD + lw + 44, ty + j * _lh(font)), line, font=font, fill=(255, 255, 255))
    return y + h + 28


def _draw_footer(d, y: int, note: str) -> int:
    note_font = _font("regular", 24)
    brand_font = _font("bold", 26)
    if note:
        d.text((PAD, y), note, font=note_font, fill=SUBTLE)
    bw = d.textlength(BRAND, font=brand_font)
    d.rectangle((WIDTH - PAD - bw - 26, y + 8, WIDTH - PAD - bw - 12, y + 22), fill=ORANGE)
    d.text((WIDTH - PAD - bw, y), BRAND, font=brand_font, fill=NAVY)
    return y + 44


def render(spec: dict, out_path: Path, tag: str = "") -> Path:
    """spec: ImageSpec（generate.py）を dict にしたもの。kind は table / checklist / number。
    verdict（買い / 待ち / 見送り）があれば右上に判定のハンコを押す。"""
    # 高さが決まる前に大きめのキャンバスへ描き、最後に使った分だけ切り出す
    img = Image.new("RGB", (WIDTH, MAX_HEIGHT * 2), BG)
    d = ImageDraw.Draw(img)
    verdict = spec.get("verdict", "")
    reserve = STAMP if verdict in VERDICT_COLORS else 0
    y = _draw_title(d, PAD, tag, spec["title"], spec.get("highlight", ""), reserve)
    if reserve:
        y = max(y, PAD + STAMP)
    if spec["kind"] == "table":
        y = _draw_table(d, y, spec.get("headers", []), spec.get("rows", []), spec.get("recommend_col", -1))
    elif spec["kind"] == "checklist":
        y = _draw_checklist(d, y, spec.get("items", []))
    elif spec["kind"] == "number":
        y = _draw_number(d, y, spec.get("big_text", ""), spec.get("caption", ""))
    y = _draw_conclusion(d, y, spec.get("conclusion", ""))
    y = _draw_footer(d, max(y, MIN_HEIGHT - PAD - 44), spec.get("note", ""))
    _draw_verdict(img, verdict)
    height = min(max(y + PAD - 20, MIN_HEIGHT), MAX_HEIGHT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.crop((0, 0, WIDTH, height)).save(out_path, "PNG", optimize=True)
    return out_path
