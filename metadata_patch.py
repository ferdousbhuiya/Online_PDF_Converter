"""PDF metadata inspection and editing helpers for PDFMaster Pro."""

import os
from flask import jsonify, request
from pypdf import PdfReader, PdfWriter


EDITABLE_FIELDS = {
    "title": "/Title",
    "author": "/Author",
    "subject": "/Subject",
    "keywords": "/Keywords",
    "creator": "/Creator",
    "producer": "/Producer",
}


def _safe_metadata_value(value):
    """Convert a PDF metadata value to a browser-safe string."""
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def make_pdf_metadata_view():
    """Return a Flask view that reads metadata from one uploaded PDF."""
    def pdf_metadata_view():
        uploaded = request.files.get("file")
        if not uploaded or not uploaded.filename:
            return jsonify({"success": False, "error": "Please select a PDF file."}), 400

        if not uploaded.filename.lower().endswith(".pdf"):
            return jsonify({"success": False, "error": "Metadata can only be read from PDF files."}), 400

        try:
            reader = PdfReader(uploaded.stream)
            metadata = reader.metadata or {}
            fields = {
                field: _safe_metadata_value(metadata.get(pdf_key))
                for field, pdf_key in EDITABLE_FIELDS.items()
            }
            populated = sum(1 for value in fields.values() if value.strip())
            return jsonify({
                "success": True,
                "metadata": fields,
                "populated_count": populated,
            })
        except Exception:
            return jsonify({"success": False, "error": "Unable to read metadata from this PDF."}), 400

    return pdf_metadata_view


def handle_edit_metadata(files, output_dir, form_data):
    """Edit selected metadata fields or remove all document metadata."""
    try:
        if not files:
            return {"success": False, "error": "No PDF file was provided."}

        reader = PdfReader(files[0])
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return {"success": False, "error": "This PDF is password protected. Unlock it first."}

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        remove_all = str(form_data.get("remove_all_metadata", "no")).lower() in {"yes", "true", "1", "on"}

        if not remove_all:
            existing = reader.metadata or {}
            updated = {}

            # Preserve metadata entries that this editor does not expose.
            for key, value in existing.items():
                if not isinstance(key, str) or not key.startswith("/") or value is None:
                    continue
                if key not in EDITABLE_FIELDS.values():
                    updated[key] = _safe_metadata_value(value)

            # The visible fields are authoritative: a blank value removes that field.
            for field, pdf_key in EDITABLE_FIELDS.items():
                value = str(form_data.get(field, "") or "").strip()
                if value:
                    updated[pdf_key] = value

            if updated:
                writer.add_metadata(updated)

        os.makedirs(output_dir, exist_ok=True)
        filename = "metadata_edited.pdf"
        output_file = os.path.join(output_dir, filename)
        with open(output_file, "wb") as fh:
            writer.write(fh)

        if remove_all:
            message = "All PDF metadata removed successfully."
        else:
            message = "PDF metadata updated successfully."

        session_id = os.path.basename(output_dir.rstrip(os.sep))
        return {
            "success": True,
            "download_url": f"/download/{session_id}/{filename}",
            "filename": filename,
            "message": message,
        }
    except Exception:
        return {"success": False, "error": "Unable to update PDF metadata."}
