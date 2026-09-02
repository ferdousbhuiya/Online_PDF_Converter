import json
import os

from flask import jsonify, request
from pypdf import PdfReader, PdfWriter


FIELD_TYPE_NAMES = {
    "/Tx": "text",
    "/Btn": "button",
    "/Ch": "choice",
    "/Sig": "signature",
}


def _field_options(field):
    options = field.get("/Opt") or []
    result = []
    for option in options:
        if isinstance(option, (list, tuple)) and option:
            value = str(option[0])
            label = str(option[-1])
        else:
            value = label = str(option)
        result.append({"value": value, "label": label})
    return result


def _button_options(field):
    try:
        normal = field.get("/AP", {}).get("/N", {})
        return [str(key) for key in normal.keys() if str(key) != "/Off"]
    except Exception:
        return []


def make_pdf_fields_view():
    def inspect_pdf_fields():
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"success": False, "error": "Please select a PDF file"}), 400
        if not upload.filename.lower().endswith(".pdf"):
            return jsonify({"success": False, "error": "Only PDF files are supported"}), 400
        try:
            reader = PdfReader(upload.stream)
            fields = reader.get_fields() or {}
            result = []
            for name, field in fields.items():
                field_type = FIELD_TYPE_NAMES.get(str(field.get("/FT", "/Tx")), "text")
                if field_type == "signature":
                    continue
                item = {
                    "name": str(name),
                    "label": str(field.get("/TU") or field.get("/T") or name),
                    "type": field_type,
                    "value": str(field.get("/V") or ""),
                    "options": _field_options(field),
                }
                if field_type == "button":
                    item["button_options"] = _button_options(field)
                result.append(item)
            return jsonify({"success": True, "fields": result, "count": len(result)})
        except Exception as exc:
            return jsonify({"success": False, "error": f"Could not read PDF form fields: {exc}"}), 400

    return inspect_pdf_fields


def handle_fill_pdf(files, output_dir, form_data):
    """Fill existing AcroForm fields while keeping the output PDF editable."""
    try:
        raw_values = form_data.get("field_values") or "{}"
        values = json.loads(raw_values)
        if not isinstance(values, dict):
            return {"success": False, "error": "Invalid form field data"}

        reader = PdfReader(files[0])
        fields = reader.get_fields() or {}
        if not fields:
            return {"success": False, "error": "This PDF does not contain fillable form fields"}

        writer = PdfWriter()
        writer.clone_document_from_reader(reader)

        cleaned = {}
        for key, value in values.items():
            if key not in fields:
                continue
            cleaned[str(key)] = "" if value is None else str(value)

        for page in writer.pages:
            writer.update_page_form_field_values(page, cleaned, auto_regenerate=True)

        out = os.path.join(output_dir, "filled.pdf")
        with open(out, "wb") as fh:
            writer.write(fh)

        return {
            "success": True,
            "download_url": f"/download/{os.path.basename(output_dir)}/filled.pdf",
            "filename": "filled.pdf",
            "message": f"Filled {len(cleaned)} PDF form field(s).",
        }
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid form field data"}
    except Exception as exc:
        return {"success": False, "error": f"Fill PDF failed: {exc}"}
