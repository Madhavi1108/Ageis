#!/usr/bin/env python3
"""Render docs/AEGIS_IMPLEMENTATION_PLAN.md to docs/AEGIS_IMPLEMENTATION_PLAN.pdf.

Self-contained Markdown-subset renderer built on reportlab.platypus.
Supported syntax: # .. #### headings, paragraphs, blank-line breaks,
- / * bullets (2-space indent = nesting), 1. numbered lists, | pipe | tables
with a |---| separator row, ``` fenced code blocks, --- horizontal rules,
**bold**, `inline code`.

Usage:  python scripts/build_plan_pdf.py [input.md] [output.pdf]
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / "docs" / "AEGIS_IMPLEMENTATION_PLAN.md"
DEFAULT_OUT = ROOT / "docs" / "AEGIS_IMPLEMENTATION_PLAN.pdf"

DOC_TITLE = "AEGIS — Detailed Phase-by-Phase Implementation Plan"

# --------------------------------------------------------------------------- styles
_ss = getSampleStyleSheet()
BODY = ParagraphStyle(
    "Body", parent=_ss["BodyText"], fontName="Helvetica", fontSize=9.3,
    leading=13.5, spaceBefore=2, spaceAfter=6, alignment=TA_LEFT,
)
H1 = ParagraphStyle(
    "H1", parent=_ss["Heading1"], fontName="Helvetica-Bold", fontSize=18,
    leading=22, spaceBefore=6, spaceAfter=12, textColor=colors.HexColor("#1a2b45"),
)
H2 = ParagraphStyle(
    "H2", parent=_ss["Heading2"], fontName="Helvetica-Bold", fontSize=13.5,
    leading=17, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1a2b45"),
)
H3 = ParagraphStyle(
    "H3", parent=_ss["Heading3"], fontName="Helvetica-Bold", fontSize=11,
    leading=14, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#33475b"),
)
H4 = ParagraphStyle(
    "H4", parent=_ss["Heading4"], fontName="Helvetica-BoldOblique", fontSize=9.6,
    leading=13, spaceBefore=8, spaceAfter=3, textColor=colors.HexColor("#33475b"),
)
CODE = ParagraphStyle(
    "Code", parent=_ss["Code"], fontName="Courier", fontSize=7.7, leading=9.6,
    backColor=colors.HexColor("#f4f5f7"), borderPadding=5, spaceBefore=4, spaceAfter=8,
    textColor=colors.HexColor("#20262e"),
)
CELL = ParagraphStyle(
    "Cell", parent=BODY, fontSize=8.0, leading=10.8, spaceBefore=0, spaceAfter=0,
)
CELL_H = ParagraphStyle(
    "CellH", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white,
)
TITLE_STYLE = ParagraphStyle(
    "TitleBig", parent=H1, fontSize=25, leading=30, spaceAfter=18,
)
SUBTITLE_STYLE = ParagraphStyle(
    "Subtitle", parent=BODY, fontSize=11, leading=16, textColor=colors.HexColor("#33475b"),
)

_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def inline(text: str) -> str:
    """Escape HTML then re-apply the tiny inline markup we support."""
    text = html.escape(text, quote=False)
    text = _INLINE_CODE.sub(
        lambda m: f'<font face="Courier" size="8">{m.group(1)}</font>', text
    )
    text = _BOLD.sub(lambda m: f"<b>{m.group(1)}</b>", text)
    return text


def _flush_para(buf: list[str], out: list) -> None:
    if buf:
        out.append(Paragraph(inline(" ".join(buf)), BODY))
        buf.clear()


def _make_table(rows: list[list[str]], out: list) -> None:
    if not rows:
        return
    header, body = rows[0], rows[1:]
    ncols = len(header)
    data = [[Paragraph(inline(c), CELL_H) for c in header]]
    for r in body:
        r = (r + [""] * ncols)[:ncols]
        data.append([Paragraph(inline(c), CELL) for c in r])
    page_w = A4[0] - 4 * cm
    tbl = Table(data, colWidths=[page_w / ncols] * ncols, repeatRows=1, hAlign="LEFT")
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#33475b")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c1c7d0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f4f5f7")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    out.append(Spacer(1, 2))
    out.append(tbl)
    out.append(Spacer(1, 8))


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _emit_list(items: list[tuple[int, str, bool]], out: list) -> None:
    """items: (indent_level, text, ordered). Build nested ListFlowables."""

    def build(idx: int, level: int):
        flow = []
        while idx < len(items):
            lvl, text, ordered = items[idx]
            if lvl < level:
                break
            if lvl > level:
                idx = idx  # handled by recursion below
                break
            para = Paragraph(inline(text), BODY)
            # look ahead for children
            children = []
            j = idx + 1
            if j < len(items) and items[j][0] > level:
                children, j = build(j, level + 1)
            if children:
                flow.append(ListItem([para, ListFlowable(
                    children,
                    bulletType="1" if items[idx][2] else "bullet",
                    leftIndent=14, bulletFontSize=8,
                )], value=None))
            else:
                flow.append(ListItem(para, value=None))
            idx = j
        return flow, idx

    # Simpler robust approach: flat rendering by level using leftIndent.
    flat = []
    for lvl, text, ordered in items:
        flat.append(
            ListItem(
                Paragraph(inline(text), BODY),
                leftIndent=6 + lvl * 14,
                value=None,
            )
        )
    ordered_first = items[0][2] if items else False
    out.append(
        ListFlowable(
            flat,
            bulletType="1" if ordered_first else "bullet",
            bulletFontName="Helvetica",
            bulletFontSize=8,
            leftIndent=12,
            spaceBefore=2,
            spaceAfter=8,
        )
    )


def render_markdown(md: str) -> list:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list = []
    para: list[str] = []
    i = 0
    first_h1_seen = False
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # fenced code
        if stripped.startswith("```"):
            _flush_para(para, out)
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            out.append(Preformatted("\n".join(code_lines) or " ", CODE))
            continue

        # table (needs a separator row as line 2)
        if stripped.startswith("|") and (i + 1) < n and re.match(
            r"^\s*\|?[\s:-]+\|[\s:|-]*$", lines[i + 1]
        ):
            _flush_para(para, out)
            rows = [_split_row(stripped)]
            i += 2  # skip header + separator
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i].strip()))
                i += 1
            _make_table(rows, out)
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            _flush_para(para, out)
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                if first_h1_seen:
                    out.append(PageBreak())
                first_h1_seen = True
                out.append(Paragraph(inline(text), H1))
                out.append(HRFlowable(width="100%", thickness=1.1,
                                      color=colors.HexColor("#1a2b45"),
                                      spaceBefore=2, spaceAfter=10))
            else:
                out.append(Paragraph(inline(text), {2: H2, 3: H3, 4: H4}[level]))
            i += 1
            continue

        # horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            _flush_para(para, out)
            out.append(HRFlowable(width="100%", thickness=0.6,
                                  color=colors.HexColor("#c1c7d0"),
                                  spaceBefore=6, spaceAfter=10))
            i += 1
            continue

        # list block (contiguous bullet / numbered lines)
        if re.match(r"^\s*([-*]|\d+\.)\s+\S", line):
            _flush_para(para, out)
            items: list[tuple[int, str, bool]] = []
            while i < n and re.match(r"^\s*([-*]|\d+\.)\s+\S", lines[i]):
                raw = lines[i]
                indent = len(raw) - len(raw.lstrip(" "))
                lvl = indent // 2
                lm = re.match(r"^\s*([-*]|(\d+)\.)\s+(.*)$", raw)
                ordered = lm.group(2) is not None
                items.append((lvl, lm.group(3).strip(), ordered))
                i += 1
            # normalize levels so the smallest present level is 0
            if items:
                base = min(it[0] for it in items)
                items = [(it[0] - base, it[1], it[2]) for it in items]
            _emit_list(items, out)
            continue

        # blank line -> paragraph break
        if not stripped:
            _flush_para(para, out)
            i += 1
            continue

        para.append(stripped)
        i += 1

    _flush_para(para, out)
    return out


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#7a869a"))
    canvas.drawString(2 * cm, 1.1 * cm, "AEGIS Implementation Plan")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"p. {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#c1c7d0"))
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


def title_page() -> list:
    return [
        Spacer(1, 5 * cm),
        Paragraph("AEGIS", TITLE_STYLE),
        Paragraph(
            "Autonomous Engineering, Generation, Intelligence &amp; Self-Repair System",
            SUBTITLE_STYLE,
        ),
        Spacer(1, 1.2 * cm),
        Paragraph("Detailed Phase-by-Phase Implementation Plan", H2),
        Paragraph(
            "Phase 0 output — greenfield build. Derived from "
            "<i>AUTONOMOUS SOFTWARE ENGINEERING.pdf</i> (the Specification, Sections 0–56).",
            SUBTITLE_STYLE,
        ),
        Spacer(1, 0.8 * cm),
        Paragraph(
            "Covers strategic positioning and the wedge, a capability spike and "
            "walking-skeleton delivery strategy with kill gates, cost / latency "
            "economics, and trust / governance — then Phase 0 and Phases 1–28 "
            "(Phase 1 is the walking-skeleton checkpoint), each with objective, "
            "deliverables, design decisions, implementation steps, phase-wise testing "
            "(unit / integration / acceptance / regression), quality gates, 16 objective "
            "metrics, risks, and effort sizing. Appendices: traceability matrix, milestones "
            "and critical path, the 30-point acceptance contract, the absolute-rules audit, "
            "the kill-criteria decision gates, and a cost-model worksheet.",
            SUBTITLE_STYLE,
        ),
        Spacer(1, 1.5 * cm),
        Paragraph("Plan version 1.0", SUBTITLE_STYLE),
        PageBreak(),
    ]


def build(in_path: Path, out_path: Path) -> None:
    md = in_path.read_text(encoding="utf-8")
    story = title_page() + render_markdown(md)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=DOC_TITLE,
        author="AEGIS Phase 0",
        subject="AEGIS phase-by-phase implementation plan",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"wrote {out_path}  ({doc.page} pages, {out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    build(src, dst)
