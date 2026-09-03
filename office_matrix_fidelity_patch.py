"""Final matrix/layout fidelity layer for Word professional equations.

Builds on the high-resolution equation renderer. Word OMML <m:m> objects are
true matrices, but the earlier LaTeX conversion emitted a bare `matrix`
environment. That preserved rows and columns while losing the visible matrix
brackets expected in state-space/control-system notation. This layer renders
standalone OMML matrices as bracketed matrices and keeps matrices already inside
an explicit Word delimiter unwrapped to avoid double brackets.
"""

from lxml import etree

import office_patch as base
import office_equation_quality_patch as quality


_PREVIOUS_CONVERTER = quality._enhanced_omml_to_tex


def _parent_local_name(node):
    parent = node.getparent() if node is not None else None
    return etree.QName(parent).localname if parent is not None else ''


def _matrix_to_tex(node):
    rows = []
    for row in node.findall(base._q(base.MATH_NS, 'mr')):
        cells = [
            _final_omml_to_tex(cell)
            for cell in row.findall(base._q(base.MATH_NS, 'e'))
        ]
        rows.append(' & '.join(cells))

    body = r' \\ '.join(rows)

    # An OMML matrix does not carry its brackets in the matrix element itself.
    # Word displays state-space/vector matrices as a structured matrix, while
    # the previous bare LaTeX matrix made the converted PDF look flattened.
    # If Word already wrapped the matrix in an explicit delimiter, keep the
    # inner matrix bare so the delimiter converter supplies the outer symbols.
    if _parent_local_name(node) == 'd':
        return r'\begin{matrix}' + body + r'\end{matrix}'
    return r'\begin{bmatrix}' + body + r'\end{bmatrix}'


def _final_omml_to_tex(node):
    if node is None:
        return ''

    name = etree.QName(node).localname
    if name == 'm':
        return _matrix_to_tex(node)

    # Rebuild container nodes here so nested matrices also use this final
    # converter instead of falling back to the previous bare-matrix function.
    if name in ('oMath', 'oMathPara', 'e', 'num', 'den', 'sub', 'sup', 'deg', 'fName'):
        parts = []
        previous_name = None
        structural = {'m', 'd', 'borderBox'}
        for child in node:
            if etree.QName(child).namespace != base.MATH_NS:
                continue
            child_name = etree.QName(child).localname
            text = _final_omml_to_tex(child)
            if not text:
                continue
            if parts:
                if child_name == 'm' and previous_name == 'm':
                    parts.append(r'\quad ')
                elif child_name in structural or previous_name in structural:
                    parts.append(r'\; ')
            parts.append(text)
            previous_name = child_name
        return ''.join(parts)

    # The previous converter is retained for fractions, scripts, radicals,
    # accents, n-ary operators and delimiters that are already working well.
    return _PREVIOUS_CONVERTER(node)


def make_word_to_pdf_handler(original_app):
    """Activate bracketed matrix fidelity without changing normal DOCX flow."""
    quality._enhanced_omml_to_tex = _final_omml_to_tex
    base._omml_to_tex = _final_omml_to_tex
    base._render_equation_png = quality._render_equation_png
    base._render_omml_equations_to_images = quality._render_omml_equations_to_images
    return base.make_word_to_pdf_handler(original_app)
