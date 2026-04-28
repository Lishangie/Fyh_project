"""Utilities to render highlighted code as images or HTML using Pygments.

Provides a robust Image-based renderer that wraps long lines to avoid clipping
and a simple HTML renderer (for optional screenshotting with Playwright).
"""
import os
import textwrap
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import ImageFormatter, HtmlFormatter


def _wrap_code_lines(code: str, max_len: int) -> str:
    out_lines = []
    for line in code.splitlines() or [""]:
        if len(line) <= max_len:
            out_lines.append(line)
            continue
        # preserve indentation for wrapped parts
        indent = len(line) - len(line.lstrip(" "))
        prefix = " " * indent
        wrapped = textwrap.wrap(line[indent:], width=max_len - indent) or [line[indent:]]
        out_lines.append(prefix + wrapped[0])
        for part in wrapped[1:]:
            out_lines.append(prefix + part)
    return "\n".join(out_lines) + "\n"


def generate_code_image(code: str, output_path: str, language: str = "python", *,
                        max_line_length: int = 120, font_name: str = "DejaVu Sans Mono",
                        font_size: int = 16) -> str:
    """Render `code` to an image file at `output_path` using Pygments ImageFormatter.

    This function wraps long lines to reduce the risk of truncation by ImageFormatter.
    Returns the `output_path` on success.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    wrapped = _wrap_code_lines(code, max_line_length)
    try:
        lexer = get_lexer_by_name(language)
    except Exception:
        lexer = guess_lexer(wrapped)

    formatter = ImageFormatter(font_name=font_name, font_size=font_size, line_numbers=False)
    img_bytes = highlight(wrapped, lexer, formatter)
    # highlight with ImageFormatter returns bytes
    mode = 'wb'
    with open(output_path, mode) as f:
        if isinstance(img_bytes, str):
            f.write(img_bytes.encode('utf-8'))
        else:
            f.write(img_bytes)
    return output_path


def generate_code_html(code: str, output_path: str, language: str = "python") -> str:
    """Render highlighted code to a standalone HTML file (full HTML document).

    Useful when combined with Playwright or other headless browser screenshotting.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    try:
        lexer = get_lexer_by_name(language)
    except Exception:
        lexer = guess_lexer(code)
    formatter = HtmlFormatter(full=True, linenos=False)
    html = highlight(code, lexer, formatter)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


if __name__ == "__main__":
    sample = """import math

def squares(n):
    return [i*i for i in range(n)]

print(squares(10))
"""
    out_img = os.path.join("artifacts", "sample_code.png")
    print("Generating", out_img)
    generate_code_image(sample, out_img)
    print("Wrote", out_img)
