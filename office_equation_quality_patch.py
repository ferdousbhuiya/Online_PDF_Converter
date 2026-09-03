"""Second-stage quality improvements for Word professional equations.

The primary office_patch converts Word OMML equations to LaTeX-backed images so
LibreOffice cannot drop them.  This layer keeps that working path, but improves
matrix/aligned-equation spacing and renders the equation images at much higher
resolution with stronger black antialiasing so they visually match document text.
"""

import os
import shutil
import subprocess
import tempfile
import zipfile

from lxml import etree
from PIL import Image

import office_patch as base


RENDER_DPI = 480
DISPLAY_SCALE = 1.05
MAX_DISPLAY_WIDTH_IN = 6.8

_BASE_OMML_TO_TEX = base._omml_to_tex


def _math_children(node):
    return [c for c in node if etree.QName(c).namespace == base.MATH_NS]


def _join_math_children(node):
    """Join OMML children without visually crushing adjacent matrix structures."""
    children = _math_children(node)
    parts = []
    previous_name = None
    structural = {'m', 'd', 'borderBox'}
    for child in children:
        name = etree.QName(child).localname
        text = _enhanced_omml_to_tex(child)
        if not text:
            continue
        if parts:
            if name == 'm' and previous_name == 'm':
                parts.append(r'\quad ')
            elif name in structural or previous_name in structural:
                parts.append(r'\; ')
        parts.append(text)
        previous_name = name
    return ''.join(parts)


def _enhanced_omml_to_tex(node):
    """Use the proven converter, adding spacing only where OMML structures need it."""
    if node is None:
        return ''
    name = etree.QName(node).localname

    if name in ('oMath', 'oMathPara', 'e', 'num', 'den', 'sub', 'sup', 'deg', 'fName'):
        return _join_math_children(node)

    if name == 'm':
        rows = []
        for row in node.findall(base._q(base.MATH_NS, 'mr')):
            cells = [_enhanced_omml_to_tex(cell) for cell in row.findall(base._q(base.MATH_NS, 'e'))]
            rows.append(r' & '.join(cells))
        # matrix adds deliberate row/column spacing and avoids the compressed look
        # seen in the state-space pages of Assignment 1.
        return r'\begin{matrix}' + r' \\ '.join(rows) + r'\end{matrix}'

    return _BASE_OMML_TO_TEX(node)


def _strengthen_antialiasing(path):
    """Darken only antialiased equation edges while preserving transparency."""
    with Image.open(path) as image:
        rgba = image.convert('RGBA')
        pixels = list(rgba.getdata())
        strengthened = []
        for r, g, b, a in pixels:
            if a:
                # LaTeX equations should be true black.  Increasing alpha on edge
                # pixels removes the pale/dim appearance after LibreOffice embeds
                # the PNG into a PDF.
                a = min(255, int(a * 1.28 + 10))
                strengthened.append((0, 0, 0, a))
            else:
                strengthened.append((0, 0, 0, 0))
        rgba.putdata(strengthened)
        rgba.save(path, 'PNG', optimize=True)


def _render_equation_png(tex, output_path, display=False):
    """Render equations at 480 DPI for print-like sharpness."""
    if not shutil.which('latex') or not shutil.which('dvipng'):
        raise RuntimeError('Professional equation renderer is not installed')

    work_dir = tempfile.mkdtemp(prefix='pdfmaster-equation-hq-')
    try:
        equation = r'\[\displaystyle %s\]' % tex if display else r'$\displaystyle %s$' % tex
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

        result = subprocess.run(
            ['latex', '-interaction=nonstopmode', '-halt-on-error', 'equation.tex'],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            ascii_tex = tex.encode('ascii', errors='ignore').decode('ascii').strip() or '?'
            document = document.replace(tex, ascii_tex)
            with open(tex_path, 'w', encoding='utf-8') as handle:
                handle.write(document)
            result = subprocess.run(
                ['latex', '-interaction=nonstopmode', '-halt-on-error', 'equation.tex'],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        if result.returncode != 0:
            raise RuntimeError('Unable to render one of the Word equations')

        png = subprocess.run(
            [
                'dvipng', '-q', '-D', str(RENDER_DPI), '-T', 'tight',
                '-fg', 'Black', '-bg', 'Transparent', '-o', output_path, 'equation.dvi',
            ],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if png.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError('Unable to create equation image')
        _strengthen_antialiasing(output_path)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _render_omml_equations_to_images(input_path, output_path):
    """HQ variant of the existing OMML replacement pipeline."""
    temp_dir = tempfile.mkdtemp(prefix='pdfmaster-docx-hq-')
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
            namespaces=base.NS,
        ))
        rendered_count = 0

        for index, equation in enumerate(equations, start=1):
            tex = _enhanced_omml_to_tex(equation).strip()
            if not tex:
                continue

            display = etree.QName(equation).localname == 'oMathPara'
            image_name = f'pdfmaster_equation_{index}.png'
            image_path = os.path.join(media_dir, image_name)
            _render_equation_png(tex, image_path, display=display)

            with Image.open(image_path) as image:
                width_px, height_px = image.size

            # Preserve the original physical equation size while embedding twice
            # as many pixels as the previous 240-DPI renderer.
            width_emu = max(1, int(width_px / RENDER_DPI * 914400 * DISPLAY_SCALE))
            height_emu = max(1, int(height_px / RENDER_DPI * 914400 * DISPLAY_SCALE))
            max_width_emu = int(MAX_DISPLAY_WIDTH_IN * 914400)
            if width_emu > max_width_emu:
                ratio = max_width_emu / width_emu
                width_emu = max_width_emu
                height_emu = max(1, int(height_emu * ratio))

            relationship_id = f'rId{next_relationship_id}'
            next_relationship_id += 1
            relationship = etree.Element(base._q(base.PKG_REL_NS, 'Relationship'))
            relationship.set('Id', relationship_id)
            relationship.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image')
            relationship.set('Target', f'media/{image_name}')
            relationships_tree.getroot().append(relationship)

            run = base._drawing_run(
                relationship_id,
                image_name,
                width_emu,
                height_emu,
                30000 + index,
            )
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
            default = etree.Element(base._q(base.CONTENT_TYPE_NS, 'Default'))
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


def make_word_to_pdf_handler(original_app):
    # office_patch resolves these helpers from module globals at runtime, so
    # replacing them here upgrades the established handler without duplicating
    # its fallback/error behavior.
    base._omml_to_tex = _enhanced_omml_to_tex
    base._render_equation_png = _render_equation_png
    base._render_omml_equations_to_images = _render_omml_equations_to_images
    return base.make_word_to_pdf_handler(original_app)
