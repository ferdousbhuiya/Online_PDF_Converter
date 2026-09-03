import os

# Groq retired llama-3.3-70b-versatile for free/developer usage on 2026-08-16.
# Normalize the legacy value before importing AI modules so both the homepage
# assistant and AI PowerPoint use the supported replacement automatically.
_LEGACY_GROQ_MODELS = {
    'llama-3.3-70b-versatile': 'openai/gpt-oss-120b',
    'llama-3.1-8b-instant': 'openai/gpt-oss-20b',
}
_configured_groq_model = os.environ.get('GROQ_MODEL', '').strip()
if not _configured_groq_model:
    os.environ['GROQ_MODEL'] = 'openai/gpt-oss-120b'
elif _configured_groq_model in _LEGACY_GROQ_MODELS:
    os.environ['GROQ_MODEL'] = _LEGACY_GROQ_MODELS[_configured_groq_model]

import app as original_app
from flask import Response
from ppt_resilient_patch import handle_pdf_to_ppt
from compare_patch import handle_compare_pdf
from converter_patch import handle_compress_pdf
from extract_images_patch import handle_extract_images
from fill_pdf_patch import handle_fill_pdf, make_pdf_fields_view
from metadata_patch import handle_edit_metadata, make_pdf_metadata_view
from ai_assistant_patch import make_ai_ask_view
from frontend_pages import make_home_view, make_tools_view, about_page, contact_page
from office_matrix_fidelity_patch import make_word_to_pdf_handler
from signature_patch import handle_sign_pdf
from production_hardening import (
    make_convert_view,
    make_download_view,
    make_health_view,
    handle_watermark_pdf,
    handle_page_numbers,
    handle_remove_pages,
    handle_organize_pdf,
    handle_crop_pdf,
    handle_ocr_pdf,
    handle_html_to_pdf,
)

# Conversion fixes
original_app.handle_compare_pdf = handle_compare_pdf
original_app.handle_compress_pdf = handle_compress_pdf
original_app.handle_pdf_to_ppt = handle_pdf_to_ppt
original_app.handle_word_to_pdf = make_word_to_pdf_handler(original_app)
original_app.handle_watermark_pdf = handle_watermark_pdf
original_app.handle_page_numbers = handle_page_numbers
original_app.handle_sign_pdf = handle_sign_pdf
original_app.handle_extract_images = handle_extract_images
original_app.handle_edit_metadata = handle_edit_metadata
original_app.handle_remove_pages = handle_remove_pages
original_app.handle_organize_pdf = handle_organize_pdf
original_app.handle_crop_pdf = handle_crop_pdf
original_app.handle_ocr_pdf = handle_ocr_pdf
original_app.handle_html_to_pdf = handle_html_to_pdf

# Add Fill PDF without modifying the large original app module.
if not any(tool.get('id') == 'fill_pdf' for tool in original_app.TOOLS):
    original_app.TOOLS.append({
        'id': 'fill_pdf',
        'name': 'Fill PDF',
        'icon': '🖊️',
        'color': '#2563EB',
        'description': 'Fill existing interactive form fields in a PDF',
        'category': 'edit',
        'input': 'pdf',
        'multiple': False,
    })

_original_process_tool = original_app.process_tool


def process_tool_with_fill(tool_id, files, output_dir, form_data):
    if tool_id == 'fill_pdf':
        return handle_fill_pdf(files, output_dir, form_data)
    if tool_id == 'edit_metadata':
        return handle_edit_metadata(files, output_dir, form_data)
    return _original_process_tool(tool_id, files, output_dir, form_data)


original_app.process_tool = process_tool_with_fill

# Route-level hardening. Flask registered the original view functions during
# import, so replace the registered views explicitly.
original_app.app.view_functions['convert'] = make_convert_view(original_app)
original_app.app.view_functions['download'] = make_download_view(original_app)
original_app.app.view_functions['health_check'] = make_health_view(original_app)
original_app.app.add_url_rule('/pdf-fields', endpoint='pdf_fields', view_func=make_pdf_fields_view(), methods=['POST'])
original_app.app.add_url_rule('/pdf-metadata', endpoint='pdf_metadata', view_func=make_pdf_metadata_view(), methods=['POST'])
original_app.app.add_url_rule('/ai/ask', endpoint='ai_ask', view_func=make_ai_ask_view(), methods=['POST'])

# UI routes: keep the landing page focused and give each navigation item its own page.
original_app.app.view_functions['index'] = make_home_view(original_app)
original_app.app.add_url_rule('/tools', endpoint='tools_page', view_func=make_tools_view(original_app))
original_app.app.add_url_rule('/about', endpoint='about_page', view_func=about_page)
original_app.app.add_url_rule('/contact', endpoint='contact_page', view_func=contact_page)

# Search-engine discovery routes.
def robots_txt():
    body = "User-agent: *\nAllow: /\n\nSitemap: https://bhuiyapdf.ferdous.us/sitemap.xml\n"
    return Response(body, mimetype='text/plain')


def sitemap_xml():
    body = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://bhuiyapdf.ferdous.us/</loc></url>
  <url><loc>https://bhuiyapdf.ferdous.us/tools</loc></url>
  <url><loc>https://bhuiyapdf.ferdous.us/about</loc></url>
  <url><loc>https://bhuiyapdf.ferdous.us/contact</loc></url>
</urlset>
"""
    return Response(body, mimetype='application/xml')


original_app.app.add_url_rule('/robots.txt', endpoint='robots_txt', view_func=robots_txt)
original_app.app.add_url_rule('/sitemap.xml', endpoint='sitemap_xml', view_func=sitemap_xml)

app = original_app.app
