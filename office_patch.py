import os
import shutil
import subprocess
import tempfile
import zipfile


MATH_NS_MARKERS = (b'<m:oMath', b'<m:oMathPara')
MATH_FONT_CANDIDATES = (
    'STIX Two Math',
    'STIXGeneral',
    'TeX Gyre Termes Math',
    'Latin Modern Math',
    'DejaVu Serif',
)


def _installed_font_families():
    """Return installed Fontconfig family names, normalized for exact matching."""
    try:
        result = subprocess.run(
            ['fc-list', ':', 'family'],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        families = set()
        for line in result.stdout.splitlines():
            for family in line.split(','):
                family = family.strip()
                if family:
                    families.add(family)
        return families
    except Exception:
        return set()


def _preferred_math_font():
    families = _installed_font_families()
    for candidate in MATH_FONT_CANDIDATES:
        if candidate in families:
            return candidate
    return None


def _docx_has_professional_math(path):
    if not path.lower().endswith('.docx'):
        return False
    try:
        with zipfile.ZipFile(path, 'r') as archive:
            for name in ('word/document.xml', 'word/styles.xml', 'word/numbering.xml'):
                if name in archive.namelist():
                    data = archive.read(name)
                    if any(marker in data for marker in MATH_NS_MARKERS):
                        return True
    except Exception:
        return False
    return False


def _normalize_math_fonts(input_path, output_path, replacement_font):
    """Create a DOCX copy whose Office Math runs use an installed math-capable font.

    Microsoft Word normally stores professional equations as OMML and commonly
    references Cambria Math. Linux containers usually do not ship Cambria Math.
    LibreOffice can import OMML, but missing math fonts can leave equation areas
    blank. Replacing only the font references keeps the OMML structure intact.
    """
    replacements = (
        b'Cambria Math',
        b'CambriaMath',
    )
    replacement = replacement_font.encode('utf-8')

    with zipfile.ZipFile(input_path, 'r') as source, zipfile.ZipFile(
        output_path, 'w', compression=zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.endswith('.xml') or item.filename.endswith('.rels'):
                for old in replacements:
                    data = data.replace(old, replacement)
            target.writestr(item, data)


def _prepare_word_input(path, output_dir):
    """Return (path_for_conversion, cleanup_path, note)."""
    if not _docx_has_professional_math(path):
        return path, None, None

    math_font = _preferred_math_font()
    if not math_font:
        return path, None, 'Professional equations detected; no dedicated math font was found.'

    normalized_path = os.path.join(
        output_dir,
        f'.equation-safe-{os.path.basename(path)}',
    )
    _normalize_math_fonts(path, normalized_path, math_font)
    return normalized_path, normalized_path, f'Professional equations preserved with {math_font}.'


def make_word_to_pdf_handler(original_app):
    """Build a Word→PDF handler that preserves OMML equations before LibreOffice."""
    def handle_word_to_pdf(files, output_dir, form_data):
        cleanup_paths = []
        prepared_files = []
        equation_notes = []

        try:
            for path in files:
                prepared, cleanup_path, note = _prepare_word_input(path, output_dir)
                prepared_files.append(prepared)
                if cleanup_path:
                    cleanup_paths.append(cleanup_path)
                if note:
                    equation_notes.append(note)

            if original_app.LO_AVAILABLE:
                out = original_app.libreoffice_convert_batch(prepared_files, output_dir)
            else:
                out = original_app._fallback_word_to_pdf(prepared_files, output_dir)

            # The normalized temporary filename must never leak to the user.
            final_out = os.path.join(output_dir, 'converted.pdf')
            if os.path.abspath(out) != os.path.abspath(final_out):
                if os.path.exists(final_out):
                    os.remove(final_out)
                shutil.move(out, final_out)
                out = final_out

            message = 'Word document converted to PDF.'
            if equation_notes:
                message += ' Professional equations were detected and preserved using a Linux-compatible math font.'

            return {
                'success': True,
                'download_url': f'/download/{os.path.basename(output_dir)}/{os.path.basename(out)}',
                'filename': 'converted.pdf',
                'message': message,
            }
        except Exception as exc:
            # Fall back to the existing path only if our equation-safe conversion fails.
            try:
                out = original_app._best_office_convert(
                    files,
                    output_dir,
                    original_app._fallback_word_to_pdf,
                    'Word→PDF',
                )
                final_out = os.path.join(output_dir, 'converted.pdf')
                if os.path.abspath(out) != os.path.abspath(final_out):
                    if os.path.exists(final_out):
                        os.remove(final_out)
                    shutil.move(out, final_out)
                    out = final_out
                return {
                    'success': True,
                    'download_url': f'/download/{os.path.basename(output_dir)}/{os.path.basename(out)}',
                    'filename': 'converted.pdf',
                    'message': 'Word document converted to PDF using the compatibility fallback.',
                }
            except Exception as fallback_exc:
                return {
                    'success': False,
                    'error': f'Word to PDF failed: {fallback_exc}',
                }
        finally:
            for path in cleanup_paths:
                try:
                    os.remove(path)
                except OSError:
                    pass

    return handle_word_to_pdf
