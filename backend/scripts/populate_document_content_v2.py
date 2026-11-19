"""Populate document_versions.content with properly formatted HTML.

Uses mammoth for DOCX (preserves tables, images, styles).
Converts markdown stubs to HTML.
For image-based PDFs, stores a reference message (use inline PDF viewer).
"""
import sqlite3
import sys
import re
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def docx_to_html_mammoth(docx_path: str) -> str:
    """Convert DOCX to HTML preserving tables, images, styles via mammoth."""
    import mammoth
    with open(docx_path, "rb") as f:
        result = mammoth.convert_to_html(f)
    return result.value


def markdown_to_html(md: str) -> str:
    """Convert markdown text to simple HTML."""
    lines = md.split("\n")
    html_parts = []
    in_list = False
    list_type = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
                list_type = None
            continue

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f"<h{level}>{text}</h{level}>")
            continue

        # Unordered list
        ul_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if ul_match:
            if not in_list or list_type != "ul":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ul>")
                in_list = True
                list_type = "ul"
            text = ul_match.group(1).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f"<li>{text}</li>")
            continue

        # Ordered list
        ol_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ol_match:
            if not in_list or list_type != "ol":
                if in_list:
                    html_parts.append(f"</{list_type}>")
                html_parts.append("<ol>")
                in_list = True
                list_type = "ol"
            text = ol_match.group(1).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f"<li>{text}</li>")
            continue

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            if in_list:
                html_parts.append(f"</{list_type}>")
                in_list = False
            html_parts.append("<hr>")
            continue

        # Regular paragraph
        if in_list:
            html_parts.append(f"</{list_type}>")
            in_list = False
            list_type = None
        text = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_parts.append(f"<p>{text}</p>")

    if in_list:
        html_parts.append(f"</{list_type}>")

    return "\n".join(html_parts)


def pdf_to_html(pdf_path: str) -> str:
    """Extract text from PDF. Returns empty string for image-based PDFs."""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if line.isupper() and len(line) > 3:
                parts.append(f"<h2>{line}</h2>")
            else:
                parts.append(f"<p>{line}</p>")
    return "\n".join(parts)


def main():
    db_path = "/app/data/dms.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    now = datetime.now().isoformat()

    # Get all documents
    cur.execute("""
        SELECT d.document_id, d.title, d.current_version_id,
               df.file_path, df.content_type, df.original_filename
        FROM documents d
        LEFT JOIN document_files df ON df.document_id = d.document_id
        ORDER BY d.document_id
    """)
    rows = cur.fetchall()
    print(f"Processing {len(rows)} documents")

    for doc_id, title, cur_ver_id, file_path, content_type, filename in rows:
        print(f"\n{doc_id} ({title})")

        html_content = ""

        if file_path and Path(file_path).exists():
            ext = Path(file_path).suffix.lower()
            if ext == ".docx":
                try:
                    html_content = docx_to_html_mammoth(file_path)
                    print(f"  DOCX via mammoth: {len(html_content)} chars")
                except Exception as e:
                    print(f"  DOCX error: {e}")
                    html_content = f"<p>Source document: {filename}</p>"
            elif ext == ".pdf":
                try:
                    html_content = pdf_to_html(file_path)
                    if not html_content.strip():
                        html_content = f"<p>Source document: {filename}</p><p>This is an image-based PDF. Use the Source PDF viewer to view the full document with all formatting and illustrations.</p>"
                        print(f"  Image-based PDF: stored reference message")
                    else:
                        print(f"  PDF text extracted: {len(html_content)} chars")
                except Exception as e:
                    print(f"  PDF error: {e}")
                    html_content = f"<p>Source document: {filename}</p>"
        else:
            # No source file - check if content is markdown stub
            if cur_ver_id:
                cur.execute("SELECT content FROM document_versions WHERE version_id = ?", (cur_ver_id,))
                row = cur.fetchone()
                if row and row[0]:
                    existing = row[0]
                    # Check if it's markdown (has # headers)
                    if re.search(r"^#{1,6}\s", existing, re.M):
                        html_content = markdown_to_html(existing)
                        print(f"  Markdown stub converted to HTML: {len(html_content)} chars")
                    else:
                        print(f"  Content already HTML or empty, skipping")
                        continue

        if not html_content:
            print(f"  No content to update, skipping")
            continue

        # Update or create version
        if cur_ver_id:
            cur.execute("""
                UPDATE document_versions SET content = ?, updated_at = ?
                WHERE version_id = ?
            """, (html_content, now, cur_ver_id))
            print(f"  Updated version {cur_ver_id}")
        else:
            ver_id = f"VER-{uuid.uuid4().hex[:8].upper()}"
            cur.execute("""
                INSERT INTO document_versions
                (version_id, document_id, version_number, state, content, change_summary,
                 kcaa_approved, created_at, updated_at, created_by, updated_by)
                VALUES (?, ?, '01.00.00', 'published', ?, 'Content from source document',
                 0, ?, ?, 'u-admin', 'u-admin')
            """, (ver_id, doc_id, html_content, now, now))
            cur.execute("""
                UPDATE documents SET current_version_id = ?, status = 'published', updated_at = ?
                WHERE document_id = ?
            """, (ver_id, now, doc_id))
            print(f"  Created version {ver_id}")

    conn.commit()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()