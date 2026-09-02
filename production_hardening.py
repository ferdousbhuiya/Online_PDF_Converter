"""Production hardening for PDFMaster Pro.

This module fixes technical weaknesses without changing the UI design.
"""

import os
import re
import shutil
import subprocess
import uuid

from flask import jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from pypdf import PdfReader, PdfWriter, PdfMerger
from reportlab.pdfgen import canvas
from PIL import Image


def _session_name():
    return uuid.uuid4().hex


def _unique_saved_name(upload_dir, original_name):
    safe = secure_filename(original_name or "")
    if not safe:
        safe = "upload"
    stem, ext = os.path.splitext(safe)
    candidate = safe
    counter = 2
    while os.path.exists(os.path.join(upload_dir, candidate)):
        candidate = f"{stem}_{counter}{ext}"
        counter += 1
    return candidate


def make_convert_view(original_app):
    def convert_hardened():
        try:
            tool_id = request.form.get("tool_id", "")
            tool = next((t for t in original_app.TOOLS if t["id"] == tool_id), None)
            if not tool:
                return jsonify({"success": False, "error": "Invalid tool"}), 400

            uploads = [f for f in request.files.getlist("files") if f and f.filename]
            if not uploads:
                return jsonify({"success": False, "error": "No files uploaded"}), 400

            if tool_id == "compare_pdf" and len(uploads) != 2:
                return jsonify({"success": False, "error": "Compare PDFs requires exactly 2 PDF files"}), 400
            if tool_id == "merge" and len(uploads) < 2:
                return jsonify({"success": False, "error": "Merge PDF requires at least 2 PDF files"}), 400
            if not tool.get("multiple", False) and len(uploads) != 1:
                return jsonify({"success": False, "error": "This tool accepts exactly 1 input file"}), 400

            category = tool.get("input")
            for upload in uploads:
                if not original_app.allowed_file(upload.filename, category):
                    return jsonify({
                        "success": False,
                        "error": f"Unsupported file type for {tool['name']}: {upload.filename}",
                    }), 400

            session_id = original_app.get_unique_filename()
            upload_dir = os.path.join(original_app.app.config["UPLOAD_FOLDER"], session_id)
            output_dir = os.path.join(original_app.app.config["OUTPUT_FOLDER"], session_id)
            os.makedirs(upload_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)

            saved_files = []
            for upload in uploads:
                name = _unique_saved_name(upload_dir, upload.filename)
                path = os.path.join(upload_dir, name)
                upload.save(path)
                saved_files.append(path)

            result = original_app.process_tool(tool_id, saved_files, output_dir, request.form)
            if result.get("success"):
                return jsonify({
                    "success": True,
                    "download_url": result["download_url"],
                    "filename": result["filename"],
                    "message": result.get("message", "Conversion successful!"),
                })
            return jsonify({"success": False, "error": result.get("error", "Conversion failed")}), 500
        except Exception as exc:
            return jsonify({"success": False, "error": str(exc)}), 500

    return convert_hardened


def make_download_view(original_app):
    def download_hardened(session_id, filename):
        session_id = secure_filename(session_id)
        filename = secure_filename(filename)
        if not session_id or not filename:
            return "File not found", 404
        directory = os.path.join(original_app.app.config["OUTPUT_FOLDER"], session_id)
        if not os.path.isdir(directory):
            return "File not found", 404
        return send_from_directory(directory, filename, as_attachment=True)

    return download_hardened


def make_health_view(original_app):
    def health_hardened():
        return jsonify({
            "status": "healthy",
            "libreoffice_available": bool(original_app.LO_AVAILABLE),
            "ghostscript_available": bool(shutil.which("gs")),
            "tesseract_available": bool(shutil.which("tesseract")),
        })

    return health_hardened


def _page_size(page):
    return float(page.mediabox.width), float(page.mediabox.height)


def handle_watermark_pdf(files, output_dir, form_data):
    try:
        if not files:
            return {"success": False, "error": "No PDF uploaded"}
        text = (form_data.get("watermark_text") or "CONFIDENTIAL").strip()[:120]
        reader = PdfReader(files[0])
        writer = PdfWriter()

        for idx, page in enumerate(reader.pages):
            width, height = _page_size(page)
            overlay_path = os.path.join(output_dir, f"watermark_{idx}.pdf")
            c = canvas.Canvas(overlay_path, pagesize=(width, height))
            c.saveState()
            font_size = max(24, min(64, width / 9))
            c.setFont("Helvetica-Bold", font_size)
            c.setFillColorRGB(0.45, 0.45, 0.45, alpha=0.25)
            c.translate(width / 2, height / 2)
            c.rotate(45)
            c.drawCentredString(0, 0, text)
            c.restoreState()
            c.save()
            page.merge_page(PdfReader(overlay_path).pages[0])
            writer.add_page(page)
            try:
                os.remove(overlay_path)
            except OSError:
                pass

        out = os.path.join(output_dir, "watermarked.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/watermarked.pdf", "filename": "watermarked.pdf"}
    except Exception as exc:
        return {"success": False, "error": f"Watermark failed: {exc}"}


def handle_page_numbers(files, output_dir, form_data):
    try:
        reader = PdfReader(files[0])
        writer = PdfWriter()
        position = form_data.get("position", "bottom-center")
        total = len(reader.pages)

        for idx, page in enumerate(reader.pages):
            width, height = _page_size(page)
            overlay_path = os.path.join(output_dir, f"number_{idx}.pdf")
            c = canvas.Canvas(overlay_path, pagesize=(width, height))
            c.setFont("Helvetica", 10)
            label = f"Page {idx + 1} of {total}"
            margin = 24
            if position == "bottom-right":
                c.drawRightString(width - margin, margin, label)
            elif position == "top-center":
                c.drawCentredString(width / 2, height - margin, label)
            else:
                c.drawCentredString(width / 2, margin, label)
            c.save()
            page.merge_page(PdfReader(overlay_path).pages[0])
            writer.add_page(page)
            try:
                os.remove(overlay_path)
            except OSError:
                pass

        out = os.path.join(output_dir, "numbered.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/numbered.pdf", "filename": "numbered.pdf"}
    except Exception as exc:
        return {"success": False, "error": f"Page numbering failed: {exc}"}


def handle_sign_pdf(files, output_dir, form_data):
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
                c.drawImage(image_path, width - margin - draw_width, margin, width=draw_width, height=draw_height, preserveAspectRatio=True, mask="auto")
            else:
                text = (form_data.get("signature_text") or "Signed").strip()[:120]
                font = form_data.get("signature_font", "Helvetica-Oblique")
                if font not in ("Helvetica-Oblique", "Times-Italic", "Courier-Oblique"):
                    font = "Helvetica-Oblique"
                size = max(14, min(50, int(form_data.get("signature_size", 30))))
                c.setFont(font, size)
                c.setFillColorRGB(0, 0, 0.65)
                text_width = c.stringWidth(text, font, size)
                c.drawString(max(margin, width - margin - text_width), margin, text)

            c.save()
            page.merge_page(PdfReader(overlay_path).pages[0])
            writer.add_page(page)

        out = os.path.join(output_dir, "signed.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/signed.pdf", "filename": "signed.pdf"}
    except Exception as exc:
        return {"success": False, "error": f"Signing failed: {exc}"}


def handle_remove_pages(files, output_dir, form_data):
    try:
        spec = (form_data.get("page_order") or "").strip()
        if not spec:
            return {"success": False, "error": "Please specify pages to remove"}

        reader = PdfReader(files[0])
        total = len(reader.pages)
        remove_set = set()
        for raw in spec.split(","):
            part = raw.strip()
            if not part:
                continue
            if "-" in part:
                bits = part.split("-", 1)
                start, end = int(bits[0]), int(bits[1])
                if start > end:
                    start, end = end, start
                remove_set.update(range(start, end + 1))
            else:
                remove_set.add(int(part))

        invalid = sorted(p for p in remove_set if p < 1 or p > total)
        if invalid:
            return {"success": False, "error": f"Page number out of range: {invalid[0]} (PDF has {total} pages)"}
        if len(remove_set) >= total:
            return {"success": False, "error": "At least one page must remain in the PDF"}

        writer = PdfWriter()
        for idx, page in enumerate(reader.pages, start=1):
            if idx not in remove_set:
                writer.add_page(page)
        out = os.path.join(output_dir, "pages_removed.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/pages_removed.pdf", "filename": "pages_removed.pdf", "message": f"Removed {len(remove_set)} of {total} pages"}
    except ValueError:
        return {"success": False, "error": "Use page numbers such as 1,3,5-8"}
    except Exception as exc:
        return {"success": False, "error": f"Remove pages failed: {exc}"}


def handle_organize_pdf(files, output_dir, form_data):
    try:
        reader = PdfReader(files[0])
        total = len(reader.pages)
        spec = (form_data.get("page_order") or "").strip()
        if not spec:
            return {"success": False, "error": "Enter the desired page order, for example 1,3,2,4"}
        order = [int(x.strip()) for x in spec.split(",") if x.strip()]
        if not order:
            return {"success": False, "error": "No valid page numbers were provided"}
        invalid = [p for p in order if p < 1 or p > total]
        if invalid:
            return {"success": False, "error": f"Page number out of range: {invalid[0]} (PDF has {total} pages)"}

        writer = PdfWriter()
        for number in order:
            writer.add_page(reader.pages[number - 1])
        out = os.path.join(output_dir, "organized.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/organized.pdf", "filename": "organized.pdf", "message": f"Created PDF with {len(order)} page(s) in the requested order"}
    except ValueError:
        return {"success": False, "error": "Use comma-separated page numbers such as 1,3,2,4"}
    except Exception as exc:
        return {"success": False, "error": f"Organization failed: {exc}"}


def handle_crop_pdf(files, output_dir, form_data):
    try:
        margins = {
            "left": float(form_data.get("margin_left", 0) or 0),
            "right": float(form_data.get("margin_right", 0) or 0),
            "top": float(form_data.get("margin_top", 0) or 0),
            "bottom": float(form_data.get("margin_bottom", 0) or 0),
        }
        if any(value < 0 for value in margins.values()):
            return {"success": False, "error": "Crop margins cannot be negative"}

        reader = PdfReader(files[0])
        writer = PdfWriter()
        for page in reader.pages:
            left, bottom = float(page.mediabox.left), float(page.mediabox.bottom)
            right, top = float(page.mediabox.right), float(page.mediabox.top)
            new_left = left + margins["left"]
            new_right = right - margins["right"]
            new_bottom = bottom + margins["bottom"]
            new_top = top - margins["top"]
            if new_right - new_left < 36 or new_top - new_bottom < 36:
                return {"success": False, "error": "Crop margins are too large for this PDF page"}
            page.cropbox.lower_left = (new_left, new_bottom)
            page.cropbox.upper_right = (new_right, new_top)
            writer.add_page(page)

        out = os.path.join(output_dir, "cropped.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/cropped.pdf", "filename": "cropped.pdf", "message": "PDF cropped successfully"}
    except ValueError:
        return {"success": False, "error": "Crop margins must be numeric"}
    except Exception as exc:
        return {"success": False, "error": f"Crop failed: {exc}"}


def _installed_tesseract_languages():
    result = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines()[1:] if line.strip()}


def handle_ocr_pdf(files, output_dir, form_data):
    """Create a genuinely searchable PDF using Tesseract's PDF text layer."""
    try:
        if not shutil.which("tesseract"):
            return {"success": False, "error": "OCR engine is not available on the server"}

        lang = form_data.get("ocr_lang", "eng")
        supported = {"eng", "fra", "deu", "spa", "ita"}
        if lang not in supported:
            lang = "eng"
        installed = _installed_tesseract_languages()
        if lang not in installed:
            return {"success": False, "error": f"OCR language '{lang}' is not installed on the server"}

        from pdf2image import convert_from_path
        images = convert_from_path(files[0], dpi=220, fmt="png")
        if not images:
            return {"success": False, "error": "The PDF contains no pages"}

        page_pdfs = []
        for idx, image in enumerate(images, start=1):
            image_path = os.path.join(output_dir, f"ocr_input_{idx}.png")
            output_base = os.path.join(output_dir, f"ocr_page_{idx}")
            image.save(image_path, "PNG", optimize=True)
            result = subprocess.run(
                ["tesseract", image_path, output_base, "-l", lang, "pdf"],
                capture_output=True,
                text=True,
                timeout=180,
            )
            page_pdf = output_base + ".pdf"
            if result.returncode != 0 or not os.path.exists(page_pdf):
                raise RuntimeError(result.stderr.strip() or "Tesseract failed to create OCR output")
            page_pdfs.append(page_pdf)

        merger = PdfMerger()
        for page_pdf in page_pdfs:
            merger.append(page_pdf)
        out = os.path.join(output_dir, "ocr_result.pdf")
        merger.write(out)
        merger.close()
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/ocr_result.pdf", "filename": "ocr_result.pdf", "message": f"OCR completed on {len(page_pdfs)} page(s). Text is searchable/selectable."}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "OCR timed out. Try a smaller PDF."}
    except Exception as exc:
        return {"success": False, "error": f"OCR failed: {exc}"}


def handle_html_to_pdf(files, output_dir, form_data):
    try:
        from xhtml2pdf import pisa
        with open(files[0], "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        # xhtml2pdf does not execute JavaScript; remove scripts explicitly and
        # block remote URL attributes so uploaded HTML cannot make server-side requests.
        html = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html, flags=re.I | re.S)
        html = re.sub(r"\s(?:src|href)\s*=\s*([\"'])\s*(?:https?:|file:|ftp:)[^\"']*\1", "", html, flags=re.I)
        out = os.path.join(output_dir, "converted.pdf")
        with open(out, "wb") as dest:
            status = pisa.CreatePDF(html, dest=dest, encoding="utf-8")
        if status.err or not os.path.exists(out) or os.path.getsize(out) == 0:
            return {"success": False, "error": "HTML rendering failed. Some modern CSS may not be supported."}
        return {"success": True, "download_url": f"/download/{os.path.basename(output_dir)}/converted.pdf", "filename": "converted.pdf", "message": "HTML converted with document structure and supported CSS preserved"}
    except Exception as exc:
        return {"success": False, "error": f"HTML to PDF failed: {exc}"}
