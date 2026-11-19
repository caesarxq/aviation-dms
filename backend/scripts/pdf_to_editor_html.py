"""Convert source PDFs to layout-preserving HTML for the editor/proposal workflow.

Uses pdftohtml -c -s (complex mode) which preserves absolute positioning,
embedded CSS, and page structure. Images are embedded as base64 data URIs
so the HTML is fully self-contained.

This is a FORMAT CONVERSION only — no summarizing, truncating, or rewriting.
All text, images, tables, and layout are preserved exactly as in the source PDF.
"""
import base64
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def pdf_to_selfcontained_html(pdf_path: str) -> str:
    """Convert PDF to self-contained HTML with embedded images."""
    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        out_base = Path(tmpdir) / "output"
        # -c: complex mode (absolute positioning, embedded CSS)
        # -s: single document (all pages in one file)
        # -noframes: no frame layout
        # -zoom 1.0: native scale
        result = subprocess.run(
            ["pdftohtml", "-c", "-s", "-noframes", "-zoom", "1.0",
             str(pdf_path), str(out_base)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pdftohtml failed: {result.stderr}")

        html_file = out_base.with_suffix(".html")
        if not html_file.exists():
            # pdftohtml may name it differently
            candidates = list(Path(tmpdir).glob("*.html"))
            if not candidates:
                raise RuntimeError("No HTML output produced")
            html_file = candidates[0]

        html = html_file.read_text(encoding="utf-8", errors="replace")

        # Embed all referenced images as base64 data URIs
        def embed_image(match):
            src = match.group(1)
            img_path = Path(tmpdir) / src
            if img_path.exists():
                data = img_path.read_bytes()
                ext = img_path.suffix.lower().lstrip(".")
                mime = {"png": "image/png", "jpg": "image/jpeg",
                        "jpeg": "image/jpeg", "gif": "image/gif"}.get(ext, "image/png")
                b64 = base64.b64encode(data).decode("ascii")
                return f'src="data:{mime};base64,{b64}"'
            return match.group(0)

        html = re.sub(r'src="([^"]+\.(?:png|jpg|jpeg|gif))"', embed_image, html, flags=re.I)

        return html


def main():
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_editor_html.py <pdf_path> [output_html_path]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    html = pdf_to_selfcontained_html(pdf_path)

    if len(sys.argv) >= 3:
        out_path = sys.argv[2]
        Path(out_path).write_text(html, encoding="utf-8")
        print(f"Written {len(html)} chars to {out_path}")
    else:
        print(html)


if __name__ == "__main__":
    main()