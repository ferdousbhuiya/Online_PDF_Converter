import app as original_app
from compare_patch import handle_compare_pdf
from converter_patch import handle_compress_pdf, handle_pdf_to_ppt
from frontend_pages import make_home_view, make_tools_view, about_page, contact_page
from production_hardening import (
    make_convert_view,
    make_download_view,
    make_health_view,
    handle_watermark_pdf,
    handle_page_numbers,
    handle_sign_pdf,
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
original_app.handle_watermark_pdf = handle_watermark_pdf
original_app.handle_page_numbers = handle_page_numbers
original_app.handle_sign_pdf = handle_sign_pdf
original_app.handle_remove_pages = handle_remove_pages
original_app.handle_organize_pdf = handle_organize_pdf
original_app.handle_crop_pdf = handle_crop_pdf
original_app.handle_ocr_pdf = handle_ocr_pdf
original_app.handle_html_to_pdf = handle_html_to_pdf

# Route-level hardening. Flask registered the original view functions during
# import, so replace the registered views explicitly.
original_app.app.view_functions['convert'] = make_convert_view(original_app)
original_app.app.view_functions['download'] = make_download_view(original_app)
original_app.app.view_functions['health_check'] = make_health_view(original_app)

# UI routes: keep the landing page focused and give each navigation item its own page.
original_app.app.view_functions['index'] = make_home_view(original_app)
original_app.app.add_url_rule('/tools', endpoint='tools_page', view_func=make_tools_view(original_app))
original_app.app.add_url_rule('/about', endpoint='about_page', view_func=about_page)
original_app.app.add_url_rule('/contact', endpoint='contact_page', view_func=contact_page)

app = original_app.app
