import app as original_app
from compare_patch import handle_compare_pdf
from converter_patch import handle_compress_pdf, handle_pdf_to_ppt

# Targeted production overrides. process_tool resolves these globals at request
# time, so the rest of the application remains unchanged.
original_app.handle_compare_pdf = handle_compare_pdf
original_app.handle_compress_pdf = handle_compress_pdf
original_app.handle_pdf_to_ppt = handle_pdf_to_ppt

app = original_app.app
