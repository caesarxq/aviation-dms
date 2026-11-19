"""Populate document_versions.content from attached source PDFs/DOCXs.

Extracts text from source files and stores as HTML in the content field.
Run once after uploading source documents to staging.
"""
import sqlite3
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypdf import PdfReader


def pdf_to_html(pdf_path: str) -> str:
    """Extract text from PDF and convert to simple HTML."""
    reader = PdfReader(pdf_path)
    html_parts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        # Convert lines to HTML paragraphs
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Escape HTML
            line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Detect headings (all caps or starts with number.)
            if line.isupper() and len(line) > 3:
                html_parts.append(f"<h2>{line}</h2>")
            elif line[0].isdigit() and ". " in line[:5]:
                html_parts.append(f"<h3>{line}</h3>")
            else:
                html_parts.append(f"<p>{line}</p>")
    return "\n".join(html_parts)


def docx_to_html(docx_path: str) -> str:
    """Extract text from DOCX and convert to simple HTML."""
    import zipfile
    import re
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)
    full_text = " ".join(texts)
    # Split into sentences/paragraphs
    parts = []
    for sentence in full_text.split(". "):
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence = sentence.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f"<p>{sentence}</p>")
    return "\n".join(parts)


def main():
    db_path = "/app/data/dms.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Get documents with attached files
    cur.execute("""
        SELECT d.document_id, d.title, df.file_path, df.content_type, df.original_filename
        FROM documents d
        JOIN document_files df ON d.document_id = df.document_id
        WHERE df.content_type IN ('application/pdf', 'application/octet-stream')
        ORDER BY d.document_id
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} documents with attached source files")

    for doc_id, title, file_path, content_type, filename in rows:
        path = Path(file_path)
        if not path.exists():
            print(f"  SKIP {doc_id}: file not found at {file_path}")
            continue

        ext = path.suffix.lower()
        print(f"  Processing {doc_id} ({title}): {filename}")

        try:
            if ext == ".pdf":
                html_content = pdf_to_html(str(path))
            elif ext == ".docx":
                html_content = docx_to_html(str(path))
            else:
                print(f"    SKIP: unsupported extension {ext}")
                continue

            if not html_content.strip():
                print(f"    SKIP: no text extracted")
                continue

            # Update the current published version's content
            cur.execute("""
                UPDATE document_versions
                SET content = ?, updated_at = datetime('now')
                WHERE version_id = (
                    SELECT current_version_id FROM documents WHERE document_id = ?
                )
            """, (html_content, doc_id))
            print(f"    Updated content: {len(html_content)} chars")
        except Exception as e:
            print(f"    ERROR: {e}")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()