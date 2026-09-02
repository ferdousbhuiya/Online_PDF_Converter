import app as original_app
from compare_patch import handle_compare_pdf

# Replace only the Compare PDF handler. process_tool resolves this global
# on each request, so the rest of the application remains unchanged.
original_app.handle_compare_pdf = handle_compare_pdf

app = original_app.app
