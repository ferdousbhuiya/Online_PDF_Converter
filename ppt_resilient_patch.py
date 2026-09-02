"""Resilient PDF-to-PowerPoint routing.

AI is used only for the AI Presentation mode. If Groq is unavailable because of
network/API configuration or a temporary service failure, the conversion still
works by falling back to the existing local Preserve Layout converter.
"""

from ai_ppt_patch import handle_pdf_to_ppt as handle_ai_pdf_to_ppt
from converter_patch import handle_pdf_to_ppt as handle_preserve_layout_ppt


def handle_pdf_to_ppt(files, output_dir, form_data):
    mode = (form_data.get("ppt_mode") or "ai").lower()

    # Preserve Layout is always local and never calls Groq.
    if mode == "preserve":
        return handle_preserve_layout_ppt(files, output_dir, form_data)

    result = handle_ai_pdf_to_ppt(files, output_dir, form_data)
    if result.get("success"):
        return result

    error = str(result.get("error") or "")
    lower = error.lower()

    # Only fall back automatically for failures where AI is unavailable. Do not
    # hide genuine PDF/file problems that the user should correct.
    ai_unavailable_markers = (
        "groq_api_key",
        "groq api request failed",
        "could not reach groq",
        "groq returned",
        "timed out",
        "timeout",
        "temporary",
        "network",
        "connection",
        "service unavailable",
        "rate limit",
        "429",
        "502",
        "503",
        "504",
    )
    if not any(marker in lower for marker in ai_unavailable_markers):
        return result

    fallback = handle_preserve_layout_ppt(files, output_dir, form_data)
    if fallback.get("success"):
        fallback["message"] = (
            "Groq AI was temporarily unavailable, so PDFMaster Pro completed the conversion "
            "locally using Preserve Layout mode. No AI was used for this fallback. "
            + str(fallback.get("message") or "")
        ).strip()
        fallback["ai_fallback"] = True
        return fallback

    return {
        "success": False,
        "error": (
            f"AI presentation could not be created ({error}). "
            f"The local Preserve Layout fallback also failed: {fallback.get('error', 'unknown error')}"
        ),
    }
