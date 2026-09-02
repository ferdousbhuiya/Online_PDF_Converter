import difflib
import os

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape


def _extract_pages(path):
    with pdfplumber.open(path) as pdf:
        return [(page.extract_text() or "") for page in pdf.pages]


def _clean_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _cell_text(lines, empty_label=""):
    if not lines:
        return escape(empty_label)
    return "<br/>".join(escape(line) for line in lines)


def handle_compare_pdf(files, output_dir, form_data):
    """Create a useful page-by-page text comparison report for two PDFs."""
    try:
        if len(files) != 2:
            return {
                "success": False,
                "error": "Please upload exactly 2 PDF files to compare",
            }

        pages_a = _extract_pages(files[0])
        pages_b = _extract_pages(files[1])
        max_pages = max(len(pages_a), len(pages_b))

        if max_pages == 0:
            return {"success": False, "error": "Both PDFs appear to be empty"}

        total_extractable = sum(len(t.strip()) for t in pages_a + pages_b)
        if total_extractable == 0:
            return {
                "success": False,
                "error": (
                    "No extractable text was found in either PDF. "
                    "If these are scanned/image PDFs, run OCR first and compare the OCR results."
                ),
            }

        page_results = []
        changed_pages = 0
        added_lines = 0
        removed_lines = 0

        for page_index in range(max_pages):
            text_a = pages_a[page_index] if page_index < len(pages_a) else ""
            text_b = pages_b[page_index] if page_index < len(pages_b) else ""
            lines_a = _clean_lines(text_a)
            lines_b = _clean_lines(text_b)

            matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
            blocks = []

            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue

                left = lines_a[i1:i2]
                right = lines_b[j1:j2]
                if tag in ("delete", "replace"):
                    removed_lines += len(left)
                if tag in ("insert", "replace"):
                    added_lines += len(right)

                blocks.append({"tag": tag, "left": left, "right": right})

            if blocks:
                changed_pages += 1

            page_results.append(
                {
                    "page": page_index + 1,
                    "blocks": blocks,
                    "missing_a": page_index >= len(pages_a),
                    "missing_b": page_index >= len(pages_b),
                }
            )

        output_file = os.path.join(output_dir, "comparison.pdf")
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="CompareTitle",
                parent=styles["Title"],
                fontSize=20,
                leading=24,
                alignment=TA_CENTER,
                spaceAfter=8,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CompareSmall",
                parent=styles["BodyText"],
                fontSize=8,
                leading=10,
            )
        )
        styles.add(
            ParagraphStyle(
                name="CompareCell",
                parent=styles["BodyText"],
                fontSize=8,
                leading=10,
                wordWrap="CJK",
            )
        )

        doc = SimpleDocTemplate(
            output_file,
            pagesize=A4,
            rightMargin=14 * mm,
            leftMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            title="PDF Comparison Report",
        )
        story = []

        story.append(Paragraph("PDF Comparison Report", styles["CompareTitle"]))
        story.append(
            Paragraph(
                f"<b>PDF A:</b> {escape(os.path.basename(files[0]))}<br/>"
                f"<b>PDF B:</b> {escape(os.path.basename(files[1]))}",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 8))

        same = changed_pages == 0 and len(pages_a) == len(pages_b)
        status_text = "No text differences found" if same else "Differences found"
        summary_data = [
            ["Result", "Pages A", "Pages B", "Changed pages", "Removed lines", "Added lines"],
            [
                status_text,
                str(len(pages_a)),
                str(len(pages_b)),
                str(changed_pages),
                str(removed_lines),
                str(added_lines),
            ],
        ]
        summary = Table(summary_data, colWidths=[48 * mm, 20 * mm, 20 * mm, 27 * mm, 27 * mm, 27 * mm])
        summary.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9ECEF")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9CDD2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(summary)
        story.append(Spacer(1, 10))

        if same:
            story.append(
                Paragraph(
                    "The extracted text is identical page by page. Visual-only changes such as images, colors, positioning, or fonts are not detected by this text comparison.",
                    styles["BodyText"],
                )
            )
        else:
            story.append(
                Paragraph(
                    "The sections below show text removed from PDF A on the left and text added in PDF B on the right. Replacement blocks appear in both columns.",
                    styles["CompareSmall"],
                )
            )
            story.append(PageBreak())

            changed_results = [r for r in page_results if r["blocks"] or r["missing_a"] or r["missing_b"]]
            for idx, result in enumerate(changed_results):
                page_no = result["page"]
                story.append(Paragraph(f"Page {page_no}", styles["Heading2"]))

                if result["missing_a"]:
                    story.append(Paragraph("This page exists only in PDF B.", styles["BodyText"]))
                elif result["missing_b"]:
                    story.append(Paragraph("This page exists only in PDF A.", styles["BodyText"]))

                rows = [[
                    Paragraph("PDF A - removed/original", styles["CompareSmall"]),
                    Paragraph("PDF B - added/modified", styles["CompareSmall"]),
                ]]

                if result["blocks"]:
                    for block in result["blocks"]:
                        left_label = "No text" if not block["left"] else ""
                        right_label = "No text" if not block["right"] else ""
                        rows.append(
                            [
                                Paragraph(_cell_text(block["left"], left_label), styles["CompareCell"]),
                                Paragraph(_cell_text(block["right"], right_label), styles["CompareCell"]),
                            ]
                        )
                else:
                    rows.append(
                        [
                            Paragraph("Page missing", styles["CompareCell"]),
                            Paragraph("Page missing", styles["CompareCell"]),
                        ]
                    )

                diff_table = Table(rows, colWidths=[88 * mm, 88 * mm], repeatRows=1)
                diff_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9ECEF")),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#FFF1F1")),
                            ("BACKGROUND", (1, 1), (1, -1), colors.HexColor("#EEFFF2")),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9CDD2")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 5),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ]
                    )
                )
                story.append(diff_table)

                if idx < len(changed_results) - 1:
                    story.append(PageBreak())

        doc.build(story)

        return {
            "success": True,
            "download_url": f"/download/{os.path.basename(output_dir)}/comparison.pdf",
            "filename": "comparison.pdf",
            "message": (
                "No text differences found"
                if same
                else f"Compared {max_pages} page(s): {changed_pages} page(s) contain text differences"
            ),
        }
    except Exception as exc:
        return {"success": False, "error": f"Compare failed: {str(exc)}"}
