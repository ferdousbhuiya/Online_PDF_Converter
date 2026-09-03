import os
import re
import shutil
import subprocess
import tempfile
import zipfile

from lxml import etree
from PIL import Image


MATH_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
DOC_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
CONTENT_TYPE_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
WP_NS = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
DRAW_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
PIC_NS = 'http://schemas.openxmlformats.org/drawingml/2006/picture'

NS = {'m': MATH_NS, 'w': WORD_NS}
MATH_NS_MARKERS = (b'<m:oMath', b'<m:oMathPara')


def _q(ns, tag):
    return f'{{{ns}}}{tag}'


def _child(node, name):
    return node.find(_q(MATH_NS, name)) if node is not None else None


def _mval(node, default=''):
    if node is None:
        return default
    value = node.get(_q(MATH_NS, 'val'))
    return default if value is None else value


def _docx_has_professional_math(path):
    if not path.lower().endswith('.docx'):
        return False
    try:
        with zipfile.ZipFile(path, 'r') as archive:
            if 'word/document.xml' not in archive.namelist():
                return False
            data = archive.read('word/document.xml')
            return any(marker in data for marker in MATH_NS_MARKERS)
    except Exception:
        return False


def _tex_text(value):
    """Convert common Office Math unicode characters to LaTeX-safe text."""
    value = (value or '').replace('\u2008', ' ').replace('\u2061', '').replace('\u00a0', ' ')
    replacements = {
        '−': '-', '–': '-', '—': '-', '×': r'\times ', '·': r'\cdot ',
        '±': r'\pm ', '∞': r'\infty ', '∑': r'\sum ', '∫': r'\int ',
        '≤': r'\le ', '≥': r'\ge ', '≠': r'\ne ', '→': r'\to ',
        '←': r'\leftarrow ', '↔': r'\leftrightarrow ', 'Ω': r'\Omega ',
        'ω': r'\omega ', 'Θ': r'\Theta ', 'θ': r'\theta ', 'δ': r'\delta ',
        'Δ': r'\Delta ', 'α': r'\alpha ', 'β': r'\beta ', 'γ': r'\gamma ',
        'λ': r'\lambda ', 'π': r'\pi ', 'σ': r'\sigma ', 'τ': r'\tau ',
        'φ': r'\phi ', 'ϕ': r'\varphi ', 'μ': r'\mu ', 'ρ': r'\rho ',
        '∂': r'\partial ', 'ẋ': r'\dot{x}', 'ẍ': r'\ddot{x}',
    }
    out = []
    for char in value:
        if char in replacements:
            out.append(replacements[char])
        elif char in '#$%&_{}':
            out.append('\\' + char)
        elif char == '\\':
            out.append(r'\backslash ')
        else:
            out.append(char)
    return ''.join(out)


def _omml_to_tex(node):
    """Convert the OMML constructs used by engineering Word documents to LaTeX."""
    if node is None:
        return ''
    name = etree.QName(node).localname

    if name in ('oMath', 'oMathPara', 'e', 'num', 'den', 'sub', 'sup', 'deg', 'fName'):
        return ''.join(_omml_to_tex(c) for c in node if etree.QName(c).namespace == MATH_NS)
    if name == 'r':
        text = ''.join((c.text or '') for c in node if etree.QName(c).namespace == MATH_NS and etree.QName(c).localname == 't')
        return _tex_text(text)
    if name == 't':
        return _tex_text(node.text or '')
    if name == 'f':
        return r'\frac{%s}{%s}' % (_omml_to_tex(_child(node, 'num')), _omml_to_tex(_child(node, 'den')))
    if name == 'sSup':
        return r'{%s}^{%s}' % (_omml_to_tex(_child(node, 'e')), _omml_to_tex(_child(node, 'sup')))
    if name == 'sSub':
        return r'{%s}_{%s}' % (_omml_to_tex(_child(node, 'e')), _omml_to_tex(_child(node, 'sub')))
    if name == 'sSubSup':
        return r'{%s}_{%s}^{%s}' % (
            _omml_to_tex(_child(node, 'e')),
            _omml_to_tex(_child(node, 'sub')),
            _omml_to_tex(_child(node, 'sup')),
        )
    if name == 'd':
        props = _child(node, 'dPr')
        begin = _mval(_child(props, 'begChr'), '(')
        end = _mval(_child(props, 'endChr'), ')')
        delimiters = {
            '(': '(', ')': ')', '[': '[', ']': ']', '{': r'\{', '}': r'\}',
            '|': '|', '⟨': r'\langle', '⟩': r'\rangle', '': '.',
        }
        left = delimiters.get(begin, _tex_text(begin))
        right = delimiters.get(end, _tex_text(end))
        body = ' , '.join(_omml_to_tex(x) for x in node.findall(_q(MATH_NS, 'e')))
        return r'\left%s %s \right%s' % (left, body, right)
    if name == 'm':
        rows = []
        for row in node.findall(_q(MATH_NS, 'mr')):
            cells = [_omml_to_tex(cell) for cell in row.findall(_q(MATH_NS, 'e'))]
            rows.append(' & '.join(cells))
        return r'\begin{matrix}%s\end{matrix}' % (' \\\\ '.join(rows))
    if name == 'acc':
        props = _child(node, 'accPr')
        accent = _mval(_child(props, 'chr'), '̂')
        body = _omml_to_tex(_child(node, 'e'))
        command = {
            '̂': 'hat', '̄': 'bar', '̅': 'bar', '̇': 'dot', '̈': 'ddot',
            '⃗': 'vec', '˜': 'tilde', '~': 'tilde', '˙': 'dot',
        }.get(accent)
        return (r'\%s{%s}' % (command, body)) if command else body
    if name == 'borderBox':
        return r'\boxed{%s}' % _omml_to_tex(_child(node, 'e'))
    if name == 'func':
        function_name = _omml_to_tex(_child(node, 'fName')).strip()
        argument = _omml_to_tex(_child(node, 'e'))
        clean_name = re.sub(r'[^A-Za-z]', '', function_name)
        if clean_name in ('sin', 'cos', 'tan', 'log', 'ln', 'exp', 'lim', 'max', 'min'):
            function_name = '\\' + clean_name
        else:
            function_name = r'\operatorname{%s}' % function_name
        return function_name + ' ' + argument
    if name == 'nary':
        props = _child(node, 'naryPr')
        char = _mval(_child(props, 'chr'), '∑')
        command = {'∑': r'\sum', '∫': r'\int', '∏': r'\prod', '∪': r'\bigcup', '∩': r'\bigcap'}.get(char, r'\sum')
        sub = _omml_to_tex(_child(node, 'sub'))
        sup = _omml_to_tex(_child(node, 'sup'))
        body = _omml_to_tex(_child(node, 'e'))
        if sub:
            command += r'_{%s}' % sub
        if sup:
            command += r'^{%s}' % sup
        return command + ' ' + body
    if name == 'rad':
        degree = _omml_to_tex(_child(node, 'deg'))
        body = _omml_to_tex(_child(node, 'e'))
        return (r'\sqrt[%s]{%s}' % (degree, body)) if degree else (r'\sqrt{%s}' % body)

    # OMML formatting/property nodes do not contribute visible content.
    if name.endswith('Pr') or name in {
        'ctrlPr', 'sty', 'scr', 'chr', 'begChr', 'endChr', 'count', 'mcJc',
        'subHide', 'supHide', 'degHide', 'mcs', 'mc', 'mcPr', 'mr',
    }:
        return ''
    return ''.join(_omml_to_tex(c) for c in node if etree.QName(c).namespace == MATH_NS)


def _render_equation_png(tex, output_path, display=False):
    """Render one LaTeX equation to a tightly cropped transparent PNG."""
    if not shutil.which('latex') or not shutil.which('dvipng'):
        raise RuntimeError('Professional equation renderer is not installed')

    work_dir = tempfile.mkdtemp(prefix='pdfmaster-equation-')
    try:
        equation = r'\[%s\]' % tex if display else r'$%s$' % tex
        document = r'''\documentclass{article}
\usepackage{amsmath,amssymb}
\usepackage[T1]{fontenc}
\pagestyle{empty}
\begin{document}
%s
\end{document}
''' % equation
        tex_path = os.path.join(work_dir, 'equation.tex')
        with open(tex_path, 'w', encoding='utf-8') as handle:
            handle.write(document)

        latex_result = subprocess.run(
            ['latex', '-interaction=nonstopmode', '-halt-on-error', 'equation.tex'],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if latex_result.returncode != 0:
            # Unexpected unicode should not make the whole document fail.
            ascii_tex = tex.encode('ascii', errors='ignore').decode('ascii').strip() or '?'
            document = document.replace(tex, ascii_tex)
            with open(tex_path, 'w', encoding='utf-8') as handle:
                handle.write(document)
            latex_result = subprocess.run(
                ['latex', '-interaction=nonstopmode', '-halt-on-error', 'equation.tex'],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        if latex_result.returncode != 0:
            raise RuntimeError('Unable to render one of the Word equations')

        png_result = subprocess.run(
            ['dvipng', '-q', '-D', '240', '-T', 'tight', '-bg', 'Transparent', '-o', output_path, 'equation.dvi'],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if png_result.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError('Unable to create equation image')
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _drawing_run(relationship_id, image_name, width_emu, height_emu, doc_id):
    xml = f'''<w:r xmlns:w="{WORD_NS}" xmlns:r="{DOC_REL_NS}" xmlns:wp="{WP_NS}" xmlns:a="{DRAW_NS}" xmlns:pic="{PIC_NS}">
<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{width_emu}" cy="{height_emu}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>
<wp:docPr id="{doc_id}" name="{image_name}"/><wp:cNvGraphicFramePr/>
<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>
<pic:nvPicPr><pic:cNvPr id="0" name="{image_name}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{relationship_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{width_emu}" cy="{height_emu}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></pic:spPr>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>'''
    return etree.fromstring(xml.encode('utf-8'))


def _render_omml_equations_to_images(input_path, output_path):
    """Replace OMML equations with high-resolution visual equivalents.

    LibreOffice can drop Word's professional OMML equations during DOCX->PDF.
    Rendering the equations before LibreOffice preserves fractions, matrices,
    subscripts/superscripts, radicals, accents and engineering notation.
    """
    temp_dir = tempfile.mkdtemp(prefix='pdfmaster-docx-')
    try:
        with zipfile.ZipFile(input_path, 'r') as archive:
            archive.extractall(temp_dir)

        document_path = os.path.join(temp_dir, 'word', 'document.xml')
        relationships_path = os.path.join(temp_dir, 'word', '_rels', 'document.xml.rels')
        media_dir = os.path.join(temp_dir, 'word', 'media')
        os.makedirs(media_dir, exist_ok=True)

        document_tree = etree.parse(document_path)
        relationships_tree = etree.parse(relationships_path)

        existing_ids = []
        for rel in relationships_tree.getroot():
            rid = rel.get('Id', '')
            if rid.startswith('rId') and rid[3:].isdigit():
                existing_ids.append(int(rid[3:]))
        next_relationship_id = max(existing_ids or [0]) + 1

        equations = list(document_tree.xpath(
            './/m:oMathPara | .//m:oMath[not(parent::m:oMathPara)]',
            namespaces=NS,
        ))
        rendered_count = 0

        for index, equation in enumerate(equations, start=1):
            tex = _omml_to_tex(equation).strip()
            if not tex:
                continue

            display = etree.QName(equation).localname == 'oMathPara'
            image_name = f'pdfmaster_equation_{index}.png'
            image_path = os.path.join(media_dir, image_name)
            _render_equation_png(tex, image_path, display=display)

            with Image.open(image_path) as image:
                width_px, height_px = image.size

            # Rendered at 240 DPI. Cap very wide display equations to the page body.
            width_emu = max(1, int(width_px / 240 * 914400 * 1.08))
            height_emu = max(1, int(height_px / 240 * 914400 * 1.08))
            max_width_emu = int(6.8 * 914400)
            if width_emu > max_width_emu:
                ratio = max_width_emu / width_emu
                width_emu = max_width_emu
                height_emu = max(1, int(height_emu * ratio))

            relationship_id = f'rId{next_relationship_id}'
            next_relationship_id += 1
            relationship = etree.Element(_q(PKG_REL_NS, 'Relationship'))
            relationship.set('Id', relationship_id)
            relationship.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image')
            relationship.set('Target', f'media/{image_name}')
            relationships_tree.getroot().append(relationship)

            run = _drawing_run(relationship_id, image_name, width_emu, height_emu, 20000 + index)
            equation.getparent().replace(equation, run)
            rendered_count += 1

        document_tree.write(document_path, xml_declaration=True, encoding='UTF-8', standalone='yes')
        relationships_tree.write(relationships_path, xml_declaration=True, encoding='UTF-8', standalone='yes')

        content_types_path = os.path.join(temp_dir, '[Content_Types].xml')
        content_types_tree = etree.parse(content_types_path)
        has_png = bool(content_types_tree.xpath(
            '/*[local-name()="Types"]/*[local-name()="Default" and @Extension="png"]'
        ))
        if not has_png:
            default = etree.Element(_q(CONTENT_TYPE_NS, 'Default'))
            default.set('Extension', 'png')
            default.set('ContentType', 'image/png')
            content_types_tree.getroot().append(default)
            content_types_tree.write(content_types_path, xml_declaration=True, encoding='UTF-8', standalone='yes')

        with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for root, _, filenames in os.walk(temp_dir):
                for filename in filenames:
                    absolute = os.path.join(root, filename)
                    archive.write(absolute, os.path.relpath(absolute, temp_dir))

        return rendered_count
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _prepare_word_input(path, output_dir):
    if not _docx_has_professional_math(path):
        return path, None, 0

    prepared_path = os.path.join(output_dir, f'.equation-safe-{os.path.basename(path)}')
    rendered_count = _render_omml_equations_to_images(path, prepared_path)
    return prepared_path, prepared_path, rendered_count


def make_word_to_pdf_handler(original_app):
    """Build a Word->PDF handler with a dedicated professional-equation path."""
    def handle_word_to_pdf(files, output_dir, form_data):
        cleanup_paths = []
        prepared_files = []
        rendered_equations = 0

        try:
            for path in files:
                prepared, cleanup_path, count = _prepare_word_input(path, output_dir)
                prepared_files.append(prepared)
                rendered_equations += count
                if cleanup_path:
                    cleanup_paths.append(cleanup_path)

            if original_app.LO_AVAILABLE:
                out = original_app.libreoffice_convert_batch(prepared_files, output_dir)
            else:
                out = original_app._fallback_word_to_pdf(prepared_files, output_dir)

            final_out = os.path.join(output_dir, 'converted.pdf')
            if os.path.abspath(out) != os.path.abspath(final_out):
                if os.path.exists(final_out):
                    os.remove(final_out)
                shutil.move(out, final_out)
                out = final_out

            message = 'Word document converted to PDF.'
            if rendered_equations:
                message += f' Preserved {rendered_equations} professional Word equation(s), including fractions and matrices.'

            return {
                'success': True,
                'download_url': f'/download/{os.path.basename(output_dir)}/{os.path.basename(out)}',
                'filename': 'converted.pdf',
                'message': message,
            }
        except Exception as exc:
            print(f'Professional equation conversion failed: {type(exc).__name__}: {exc}')
            try:
                out = original_app._best_office_convert(
                    files,
                    output_dir,
                    original_app._fallback_word_to_pdf,
                    'Word->PDF',
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
                return {'success': False, 'error': f'Word to PDF failed: {fallback_exc}'}
        finally:
            for path in cleanup_paths:
                try:
                    os.remove(path)
                except OSError:
                    pass

    return handle_word_to_pdf
