import os
from datetime import date

from flask import request
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas


def _page_size(page):
    return float(page.mediabox.width), float(page.mediabox.height)


def handle_sign_pdf(files, output_dir, form_data):
    """Add a styled text or image signature to the final PDF page."""
    try:
        reader = PdfReader(files[0])
        if not reader.pages:
            return {"success": False, "error": "PDF has no pages"}

        writer = PdfWriter()
        last_index = len(reader.pages) - 1
        sig_type = form_data.get("sig_type", "text")

        for idx, page in enumerate(reader.pages):
            if idx != last_index:
                writer.add_page(page)
                continue

            width, height = _page_size(page)
            overlay_path = os.path.join(output_dir, "signature_overlay.pdf")
            c = canvas.Canvas(overlay_path, pagesize=(width, height))
            margin = 36

            if sig_type == "image":
                upload = request.files.get("signature_image")
                if not upload or not upload.filename:
                    return {"success": False, "error": "Please upload a PNG or JPG signature image"}
                ext = os.path.splitext(upload.filename)[1].lower()
                if ext not in (".png", ".jpg", ".jpeg"):
                    return {"success": False, "error": "Signature image must be PNG or JPG"}
                image_path = os.path.join(output_dir, f"signature{ext}")
                upload.save(image_path)
                requested_width = max(50, min(400, int(form_data.get("signature_width", 150))))
                with Image.open(image_path) as im:
                    ratio = im.height / max(im.width, 1)
                draw_width = min(float(requested_width), width * 0.4)
                draw_height = draw_width * ratio
                x = width - margin - draw_width
                y = margin + 16
                c.drawImage(image_path, x, y, width=draw_width, height=draw_height,
                            preserveAspectRatio=True, mask="auto")
                if form_data.get("include_date") == "yes":
                    c.setFillColorRGB(0.2, 0.2, 0.2)
                    c.setFont("Helvetica", 8)
                    c.drawRightString(width - margin, margin, form_data.get("signature_date") or date.today().strftime("%b %d, %Y"))
            else:
                text = (form_data.get("signature_text") or "Signed").strip()[:120]
                font = form_data.get("signature_font", "Helvetica-Oblique")
                if font not in ("Helvetica-Oblique", "Times-Italic", "Courier-Oblique"):
                    font = "Helvetica-Oblique"
                size = max(14, min(50, int(form_data.get("signature_size", 30))))
                style = form_data.get("signature_style", "formal")
                include_date = form_data.get("include_date") == "yes"
                date_text = (form_data.get("signature_date") or date.today().strftime("%b %d, %Y"))[:40]

                c.setFillColorRGB(0, 0, 0.65)
                c.setFont(font, size)
                text_width = c.stringWidth(text, font, size)
                block_width = min(max(text_width + 18, 155), width * 0.45)
                x = max(margin, width - margin - block_width)

                if style == "classic":
                    c.drawRightString(width - margin, margin + 7, text)
                else:
                    baseline = margin + 31
                    c.drawCentredString(x + block_width / 2, baseline, text)
                    c.setStrokeColorRGB(0.15, 0.15, 0.15)
                    c.setLineWidth(0.8)
                    c.line(x, margin + 24, x + block_width, margin + 24)
                    c.setFillColorRGB(0.2, 0.2, 0.2)
                    c.setFont("Helvetica", 8.5)
                    c.drawString(x, margin + 11, "Signature")
                    if style == "formal" and include_date:
                        c.drawRightString(x + block_width, margin + 11, date_text)

            c.save()
            page.merge_page(PdfReader(overlay_path).pages[0])
            writer.add_page(page)
            try:
                os.remove(overlay_path)
            except OSError:
                pass

        out = os.path.join(output_dir, "signed.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        return {
            "success": True,
            "download_url": f"/download/{os.path.basename(output_dir)}/signed.pdf",
            "filename": "signed.pdf",
            "message": "Signature added to the final page.",
        }
    except Exception as exc:
        return {"success": False, "error": f"Signing failed: {exc}"}
