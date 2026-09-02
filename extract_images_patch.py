"""Image extraction that preserves the way images are displayed on PDF pages.

Raw PDF image streams can be stored mirrored, rotated, masked, or with a PDF
transformation matrix. Writing image.data directly ignores those display
transformations. This handler renders each page and crops the image regions so
extracted files match what the user sees in the PDF.
"""

import os
import zipfile

import pdfplumber
from pdf2image import convert_from_path


def handle_extract_images(files, output_dir, form_data):
    try:
        pdf_path = files[0]
        image_paths = []
        image_count = 0
        dpi = 200
        scale = dpi / 72.0

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_images = page.images or []
                if not page_images:
                    continue

                rendered_pages = convert_from_path(
                    pdf_path,
                    dpi=dpi,
                    first_page=page_num,
                    last_page=page_num,
                    fmt='png',
                    single_file=True,
                )
                if not rendered_pages:
                    continue
                rendered = rendered_pages[0].convert('RGB')

                for image_index, image_info in enumerate(page_images, start=1):
                    # pdfplumber exposes x coordinates from the left and top/bottom
                    # coordinates from the top when these keys are available.
                    x0 = float(image_info.get('x0', 0))
                    x1 = float(image_info.get('x1', page.width))
                    top = image_info.get('top')
                    bottom = image_info.get('bottom')

                    if top is None or bottom is None:
                        # Fall back from PDF bottom-origin coordinates.
                        y0 = float(image_info.get('y0', 0))
                        y1 = float(image_info.get('y1', page.height))
                        top = float(page.height) - y1
                        bottom = float(page.height) - y0
                    else:
                        top = float(top)
                        bottom = float(bottom)

                    left_px = max(0, int(round(min(x0, x1) * scale)))
                    right_px = min(rendered.width, int(round(max(x0, x1) * scale)))
                    top_px = max(0, int(round(min(top, bottom) * scale)))
                    bottom_px = min(rendered.height, int(round(max(top, bottom) * scale)))

                    if right_px <= left_px or bottom_px <= top_px:
                        continue

                    crop = rendered.crop((left_px, top_px, right_px, bottom_px))
                    filename = f'img_p{page_num}_{image_index}.png'
                    img_path = os.path.join(output_dir, filename)
                    crop.save(img_path, 'PNG', optimize=True)
                    image_paths.append(img_path)
                    image_count += 1

        if image_count == 0:
            return {'success': False, 'error': 'No images found in this PDF'}

        zip_path = os.path.join(output_dir, 'extracted_images.zip')
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            for img_path in image_paths:
                zipf.write(img_path, os.path.basename(img_path))

        return {
            'success': True,
            'download_url': f'/download/{os.path.basename(output_dir)}/extracted_images.zip',
            'filename': 'extracted_images.zip',
            'message': f'Extracted {image_count} image(s) with displayed orientation preserved',
        }
    except Exception as exc:
        return {'success': False, 'error': f'Image extraction failed: {exc}'}
