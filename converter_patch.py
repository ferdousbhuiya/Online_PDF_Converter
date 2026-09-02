"""Targeted production fixes for PDF compression and PDF-to-PowerPoint."""

import os
import shutil
import subprocess


def handle_compress_pdf(files, output_dir, form_data):
    """Compress a PDF with Ghostscript image downsampling, with a safe fallback."""
    try:
        if not files:
            return {'success': False, 'error': 'No PDF uploaded'}

        src = files[0]
        output_file = os.path.join(output_dir, 'compressed.pdf')
        original_size = os.path.getsize(src)
        gs = shutil.which('gs')

        candidates = []
        if gs:
            # /ebook keeps a good quality/size balance. /screen is tried only if
            # the source is already highly optimized and /ebook saves almost nothing.
            for preset, name in (('/ebook', 'ebook.pdf'), ('/screen', 'screen.pdf')):
                candidate = os.path.join(output_dir, name)
                cmd = [
                    gs,
                    '-sDEVICE=pdfwrite',
                    '-dCompatibilityLevel=1.4',
                    f'-dPDFSETTINGS={preset}',
                    '-dNOPAUSE',
                    '-dQUIET',
                    '-dBATCH',
                    '-dDetectDuplicateImages=true',
                    '-dCompressFonts=true',
                    '-dSubsetFonts=true',
                    f'-sOutputFile={candidate}',
                    src,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
                if result.returncode == 0 and os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                    candidates.append(candidate)

        # Pick the smallest successful Ghostscript result, but never return a
        # larger file than the original.
        if candidates:
            best = min(candidates, key=os.path.getsize)
            if os.path.getsize(best) < original_size:
                shutil.copy2(best, output_file)
            else:
                shutil.copy2(src, output_file)
        else:
            # Fallback for environments without Ghostscript.
            from pypdf import PdfReader, PdfWriter
            reader = PdfReader(src)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            for page in writer.pages:
                try:
                    page.compress_content_streams()
                except Exception:
                    pass
            writer.add_metadata({})
            with open(output_file, 'wb') as fh:
                writer.write(fh)

            if os.path.getsize(output_file) >= original_size:
                shutil.copy2(src, output_file)

        new_size = os.path.getsize(output_file)
        reduction = max(0.0, ((original_size - new_size) / original_size) * 100) if original_size else 0.0
        if reduction < 0.1:
            message = 'This PDF is already well optimized; no meaningful size reduction was possible.'
        else:
            message = f'Compressed by {reduction:.1f}% ({original_size/1048576:.2f} MB → {new_size/1048576:.2f} MB)'

        return {
            'success': True,
            'download_url': f'/download/{os.path.basename(output_dir)}/compressed.pdf',
            'filename': 'compressed.pdf',
            'message': message,
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Compression timed out. Try a smaller PDF.'}
    except Exception as exc:
        return {'success': False, 'error': f'Compression failed: {exc}'}


def handle_pdf_to_ppt(files, output_dir, form_data):
    """Create a high-fidelity PPTX by placing each rendered PDF page on its own slide."""
    try:
        if not files:
            return {'success': False, 'error': 'No PDF uploaded'}

        from pptx import Presentation
        from pptx.util import Inches
        from pdf2image import convert_from_path

        images = convert_from_path(files[0], dpi=160, fmt='png')
        if not images:
            return {'success': False, 'error': 'The PDF contains no pages'}

        prs = Presentation()
        # Remove the default slide only if a template ever creates one.
        while len(prs.slides):
            rId = prs.slides._sldIdLst[0].rId
            prs.part.drop_rel(rId)
            del prs.slides._sldIdLst[0]

        first_w, first_h = images[0].size
        slide_w = Inches(10)
        slide_h = int(slide_w * first_h / first_w)
        prs.slide_width = slide_w
        prs.slide_height = slide_h

        temp_images = []
        for idx, image in enumerate(images, start=1):
            img_path = os.path.join(output_dir, f'ppt_page_{idx}.png')
            image.save(img_path, 'PNG', optimize=True)
            temp_images.append(img_path)

            slide = prs.slides.add_slide(prs.slide_layouts[6])
            # Fit page without distortion; center if page aspect ratio differs.
            iw, ih = image.size
            image_ratio = iw / ih
            slide_ratio = prs.slide_width / prs.slide_height
            if image_ratio >= slide_ratio:
                width = prs.slide_width
                height = int(width / image_ratio)
                left = 0
                top = int((prs.slide_height - height) / 2)
            else:
                height = prs.slide_height
                width = int(height * image_ratio)
                top = 0
                left = int((prs.slide_width - width) / 2)
            slide.shapes.add_picture(img_path, left, top, width=width, height=height)

        output_file = os.path.join(output_dir, 'converted.pptx')
        prs.save(output_file)

        for img_path in temp_images:
            try:
                os.remove(img_path)
            except OSError:
                pass

        return {
            'success': True,
            'download_url': f'/download/{os.path.basename(output_dir)}/converted.pptx',
            'filename': 'converted.pptx',
            'message': f'Converted {len(images)} PDF page(s) to high-fidelity PowerPoint slides.',
        }
    except Exception as exc:
        return {'success': False, 'error': f'PDF to PowerPoint failed: {exc}'}
