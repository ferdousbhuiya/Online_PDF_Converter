"""Final production hardening for PDFMaster Pro.

Adds per-file size enforcement, lightweight content-signature validation,
rate limiting for expensive public endpoints, safer error responses, and
common security headers without changing tool behavior or UI.
"""

import os
import time
import zipfile
from collections import defaultdict, deque

from flask import jsonify, request
from PIL import Image
from werkzeug.utils import secure_filename

from production_hardening import _unique_saved_name

PER_FILE_LIMIT = int(os.environ.get("MAX_FILE_BYTES", str(100 * 1024 * 1024)))
CONVERT_LIMIT = int(os.environ.get("CONVERT_RATE_LIMIT", "30"))
AI_LIMIT = int(os.environ.get("AI_RATE_LIMIT", "30"))
RATE_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "600"))

_RATE_BUCKETS = defaultdict(deque)


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:64]
    return (request.remote_addr or "unknown")[:64]


def _rate_limited(bucket, limit):
    key = (bucket, _client_ip())
    now = time.time()
    q = _RATE_BUCKETS[key]
    cutoff = now - RATE_WINDOW
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def _looks_like_html(path):
    try:
        with open(path, "rb") as fh:
            sample = fh.read(8192)
        if b"\x00" in sample:
            return False
        text = sample.decode("utf-8", errors="ignore").lstrip().lower()
        return text.startswith(("<!doctype html", "<html", "<head", "<body")) or "<html" in text[:2000]
    except Exception:
        return False


def _validate_ooxml(path, ext):
    expected = {
        ".docx": "word/",
        ".xlsx": "xl/",
        ".pptx": "ppt/",
    }[ext]
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            return "[Content_Types].xml" in names and any(name.startswith(expected) for name in names)
    except Exception:
        return False


def _validate_saved_file(path, original_name):
    ext = os.path.splitext(original_name or path)[1].lower()
    try:
        size = os.path.getsize(path)
    except OSError:
        return False, "Uploaded file could not be read."
    if size <= 0:
        return False, "Uploaded file is empty."
    if size > PER_FILE_LIMIT:
        return False, "Each uploaded file must be 100MB or smaller."

    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return False, "Uploaded file could not be read."

    if ext == ".pdf":
        return (head.startswith(b"%PDF-"), "The uploaded file is not a valid PDF.")
    if ext in (".docx", ".xlsx", ".pptx"):
        ok = head.startswith(b"PK") and _validate_ooxml(path, ext)
        return ok, "The uploaded Office file does not match its file extension."
    if ext in (".doc", ".xls", ".ppt"):
        ok = head.startswith(bytes.fromhex("D0CF11E0A1B11AE1"))
        return ok, "The uploaded legacy Office file does not match its file extension."
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
        try:
            with Image.open(path) as image:
                image.verify()
            return True, ""
        except Exception:
            return False, "The uploaded image is invalid or does not match its extension."
    if ext in (".html", ".htm"):
        return (_looks_like_html(path), "The uploaded file does not appear to be HTML.")
    return True, ""


def make_secure_convert_view(original_app):
    def convert_secure():
        if _rate_limited("convert", CONVERT_LIMIT):
            return jsonify({"success": False, "error": "Too many conversion requests. Please wait a few minutes and try again."}), 429

        upload_dir = None
        output_dir = None
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

            for upload in uploads:
                if not original_app.allowed_file(upload.filename, tool.get("input")):
                    return jsonify({"success": False, "error": f"Unsupported file type for {tool['name']}: {secure_filename(upload.filename)}"}), 400
                try:
                    upload.stream.seek(0, os.SEEK_END)
                    size = upload.stream.tell()
                    upload.stream.seek(0)
                except Exception:
                    size = 0
                if size > PER_FILE_LIMIT:
                    return jsonify({"success": False, "error": f"{secure_filename(upload.filename)} exceeds the 100MB per-file limit."}), 413

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
                valid, message = _validate_saved_file(path, upload.filename)
                if not valid:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    return jsonify({"success": False, "error": message}), 400
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
            print(f"Conversion error: {type(exc).__name__}: {exc}", flush=True)
            return jsonify({"success": False, "error": "The conversion could not be completed. Please verify the file and try again."}), 500

    return convert_secure


def wrap_ai_view(view_func):
    def limited_ai():
        if _rate_limited("ai", AI_LIMIT):
            return jsonify({"success": False, "error": "AI request limit reached. Please wait a few minutes and try again."}), 429
        return view_func()
    limited_ai.__name__ = "limited_ai"
    return limited_ai


def install_global_hardening(app):
    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({"success": False, "error": "The combined upload is too large. Each file must be 100MB or smaller."}), 413

    @app.errorhandler(500)
    def internal_error(error):
        print(f"Unhandled server error: {type(error).__name__}", flush=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred. Please try again."}), 500

    return app
