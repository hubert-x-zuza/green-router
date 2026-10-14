"""Build the 2-page submission description (PDF) from docs/submission/opis.md.

Needs reportlab and pillow (not project dependencies; install into a scratch venv):
    uv venv /tmp/pdfenv && uv pip install --python /tmp/pdfenv/bin/python reportlab pillow
    /tmp/pdfenv/bin/python docs/submission/build_opis_pdf.py
Fonts: Arial from macOS (it has the Polish letters; the built-in PDF fonts do not).
Screenshots: docs/submission/img/*.jpg (route view and planner view of the running demo).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).resolve().parent
SRC = HERE / "opis.md"
OUT = HERE / "Zdrowa_Trasa_opis.pdf"
FONT_DIR = Path("/System/Library/Fonts/Supplemental")
GREEN = colors.HexColor("#17603a")

# body size and screenshot width are the two knobs that decide whether the text fits in 2 pages
BODY_PT = 10.2
SHOT_W = 87 * mm


def register_fonts() -> None:
    for name, file in (
        ("Arial", "Arial.ttf"),
        ("Arial-Bold", "Arial Bold.ttf"),
        ("Arial-Italic", "Arial Italic.ttf"),
        ("Arial-BoldItalic", "Arial Bold Italic.ttf"),
    ):
        path = FONT_DIR / file
        if not path.exists():
            sys.exit(f"font not found: {path}")
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily(
        "Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-BoldItalic"
    )


def inline(text: str) -> str:
    """Markdown inline -> reportlab markup."""
    t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"`([^`]+)`", r'<font name="Courier" size="%s">\1</font>' % (BODY_PT - 0.6), t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"(https?://[^\s<)]+)", r'<a href="\1" color="#17603a"><u>\1</u></a>', t)
    t = t.replace("NO₂", "NO<sub>2</sub>")  # subscript glyphs are missing in many fonts
    return t


def parse(md: str) -> list[tuple[str, str]]:
    """Return [(kind, text)] with kind in h1, h2, p, li, nl (numbered)."""
    blocks: list[tuple[str, str]] = []
    cur: list[str] = []
    kind = "p"

    def flush() -> None:
        nonlocal cur, kind
        if cur:
            blocks.append((kind, " ".join(s.strip() for s in cur)))
        cur, kind = [], "p"

    for line in md.splitlines():
        if not line.strip():
            flush()
        elif line.startswith("# "):
            flush()
            blocks.append(("h1", line[2:].strip()))
        elif line.startswith("## "):
            flush()
            blocks.append(("h2", line[3:].strip()))
        elif re.match(r"^- ", line):
            flush()
            kind, cur = "li", [line[2:]]
        elif re.match(r"^\d+\. ", line):
            flush()
            kind, cur = "nl", [line]
        elif line.startswith("  ") and cur:
            cur.append(line)
        else:
            if kind in ("li", "nl"):
                flush()
            cur.append(line)
    flush()
    return blocks


def main() -> None:
    register_fonts()
    base = ParagraphStyle("base", fontName="Arial", fontSize=BODY_PT, leading=BODY_PT * 1.33,
                          alignment=TA_LEFT, spaceAfter=4.5)
    st = {
        "h1": ParagraphStyle("h1", parent=base, fontName="Arial-Bold", fontSize=19, leading=23,
                             textColor=GREEN, spaceAfter=2),
        "h2": ParagraphStyle("h2", parent=base, fontName="Arial-Bold", fontSize=11.6, leading=14,
                             textColor=GREEN, spaceBefore=8, spaceAfter=3),
        "p": base,
        "li": ParagraphStyle("li", parent=base, leftIndent=9, bulletIndent=0, spaceAfter=2),
        "nl": ParagraphStyle("nl", parent=base, leftIndent=11, bulletIndent=0, spaceAfter=2.4),
        "cap": ParagraphStyle("cap", parent=base, fontSize=7.2, leading=8.6, textColor=colors.HexColor("#555555"),
                              spaceAfter=0),
        "meta": ParagraphStyle("meta", parent=base, fontSize=8.4, textColor=colors.HexColor("#333333"),
                               spaceAfter=4),
    }

    def shots() -> Table:
        cells, caps = [], []
        for file, cap in (
            ("route.jpg", "Zakładka „Trasa”: najszybsza trasa (szara) i trasy zdrowsze, pokolorowane według hałasu."),
            ("planner.jpg", "Zakładka „Dla miasta”: ranking miejsc, gdzie ekspozycja spotyka wielu wrażliwych użytkowników."),
        ):
            img = Image(str(HERE / "img" / file))
            ratio = img.imageHeight / img.imageWidth
            img.drawWidth, img.drawHeight = SHOT_W, SHOT_W * ratio
            cells.append(img)
            caps.append(Paragraph(cap, st["cap"]))
        t = Table([cells, caps], colWidths=[SHOT_W + 3 * mm] * 2)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, 0), 2), ("BOTTOMPADDING", (0, 1), (-1, 1), 0)]))
        return t

    story: list = []
    blocks = parse(SRC.read_text(encoding="utf-8"))
    for i, (kind, text) in enumerate(blocks):
        if kind == "h1":
            story.append(Paragraph(inline(text), st["h1"]))
        elif kind == "h2":
            story.append(Paragraph(inline(text), st["h2"]))
        elif kind == "li":
            story.append(Paragraph(inline(text), st["li"], bulletText="•"))
        elif kind == "nl":
            num, rest = text.split(". ", 1)
            story.append(Paragraph(inline(rest), st["nl"], bulletText=f"{num}."))
        else:
            style = st["meta"] if text.startswith("**Zespół") else st["p"]
            story.append(Paragraph(inline(text), style))
        # screenshots go right after the "Rozwiązanie" section
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if nxt and nxt[0] == "h2" and nxt[1] == "Dane":
            story += [Spacer(1, 3), shots()]

    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=13 * mm,
        title="Zdrowa Trasa: zdrowsze trasy po Krakowie", author="Zuzanna Jarlaczyńska, Hubert Nowak",
        subject="Open Data App Kraków: opis projektu i jego celu",
    )
    doc.build(story)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
