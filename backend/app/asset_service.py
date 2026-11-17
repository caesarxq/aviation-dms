"""
Notification asset service for Aviation DMS.

Generates graphical resources (memos, posters, notices) as PNG images
from Jinja2 HTML/CSS templates and Pillow canvas rendering. Assets are
returned as base64-encoded data URLs suitable for embedding as CID
attachments in SMTP emails.

All rendering is server-side — no client-side PII exposure.
"""
import base64
import io
import os
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw, ImageFont

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates", "notifications")

# KFL Aviation DMS logo — inline SVG (no external file dependency).
# Embedded as base64 data URI for use in email HTML and PNG rendering.
KFL_LOGO_SVG = (
    "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"150\" height=\"48\" viewBox=\"0 0 150 48\">"
    "<defs><linearGradient id=\"kfl-wing-gradient\" x1=\"0%\" y1=\"0%\" x2=\"100%\" y2=\"0%\">"
    "<stop offset=\"0%\" style=\"stop-color:#1b7abf;stop-opacity:1\" />"
    "<stop offset=\"100%\" style=\"stop-color:#166aa8;stop-opacity:1\" /></linearGradient></defs>"
    "<path d=\"M 12 6 L 12 38 L 46 38 L 46 14 L 80 14 L 80 6 Z\" fill=\"#0d2235\" />"
    "<path d=\"M 12 38 L 46 38 L 46 14 L 12 14 Z\" fill=\"#1b7abf\" />"
    "<path d=\"M 46 14 L 80 14 L 80 6 L 46 6 Z\" fill=\"#166aa8\" />"
    "<circle cx=\"29\" cy=\"22\" r=\"3\" fill=\"#ffffff\" />"
    "<circle cx=\"35\" cy=\"22\" r=\"3\" fill=\"#ffffff\" />"
    "<circle cx=\"41\" cy=\"22\" r=\"3\" fill=\"#ffffff\" />"
    "<text x=\"90\" y=\"31\" font-family=\"'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif\" font-size=\"14\" font-weight=\"700\" fill=\"#0d2235\" letter-spacing=\"0.5\">KFL</text>"
    "<text x=\"90\" y=\"44\" font-family=\"'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif\" font-size=\"7\" font-weight=\"600\" fill=\"#46677f\" letter-spacing=\"0.3\">AVIATION DMS</text>"
    "</svg>"
)
KFL_LOGO_DATA_URI = "data:image/svg+xml;base64," + base64.b64encode(KFL_LOGO_SVG.encode("utf-8")).decode("ascii")

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    keep_trailing_newline=True,
)


def get_logo_context() -> Dict[str, str]:
    """Return the KFL logo as a base64 data URI for template injection.

    Use this in route handlers to add ``kfl_logo`` to template context:
        context = get_logo_context()
        context.update({...})
        html = render_html_template("invitation_memo.html", context)
    """
    return {"kfl_logo": KFL_LOGO_DATA_URI}


def render_html_template(template_name: str, context: Dict[str, Any]) -> str:
    """Render a Jinja2 HTML template to a string.

    Used for rich HTML email bodies. The returned HTML is safe to embed
    directly in an email's text/html part.
    """
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a DejaVu font at the given size, falling back to default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Wrap text to fit within max_width pixels using the given font."""
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_header(draw: ImageDraw.Draw, y: int, width: int, title: str, subtitle: str,
                 accent_color: str, kicker: str) -> int:
    """Draw a header band and return the next y position."""
    band_height = 120
    draw.rectangle([0, y, width, y + band_height], fill="#0f172a")

    # Accent stripe
    draw.rectangle([0, y, 8, y + band_height], fill=accent_color)

    # Kicker
    kicker_font = _load_font(11, bold=True)
    draw.text((30, y + 14), kicker, font=kicker_font, fill="#93c5fd")

    # Title
    title_font = _load_font(26, bold=True)
    title_lines = _wrap_text(draw, title, title_font, width - 100)
    ty = y + 42
    for line in title_lines[:2]:
        draw.text((30, ty), line, font=title_font, fill="#ffffff")
        ty += 36

    # Subtitle
    sub_font = _load_font(13)
    draw.text((30, ty + 6), subtitle, font=sub_font, fill="#cbd5e1")

    return y + band_height + 20


def _draw_meta_grid(draw: ImageDraw.Draw, y: int, width: int, fields: List[tuple]) -> int:
    """Draw a two-column metadata grid. Returns next y position."""
    col_w = (width - 80) / 2
    row_h = 44
    label_font = _load_font(9, bold=True)
    value_font = _load_font(12)
    col_x = [40, 40 + col_w + 20]

    rows = (len(fields) + 1) // 2
    for r in range(rows):
        ry = y + r * row_h
        for c in range(2):
            idx = r * 2 + c
            if idx >= len(fields):
                continue
            label, value = fields[idx]
            x = col_x[c]
            draw.rectangle([x, ry, x + col_w, ry + row_h], fill="#f9fafb", outline="#e5e7eb")
            draw.text((x + 10, ry + 8), label, font=label_font, fill="#64748b")
            draw.text((x + 10, ry + 24), str(value), font=value_font, fill="#1f2937")

    return y + rows * row_h + 20


def _draw_section_box(draw: ImageDraw.Draw, y: int, width: int, title: str,
                      body: str, accent: str) -> int:
    """Draw a bordered section box with wrapped body text. Returns next y position."""
    box_pad = 16
    inner_w = width - 80 - 2 * box_pad
    title_font = _load_font(12, bold=True)
    body_font = _load_font(11)
    label_font = _load_font(9, bold=True)

    # Title
    draw.text((40, y), title.upper(), font=label_font, fill=accent)
    ty = y + 20

    # Body wrapping
    lines = _wrap_text(draw, body, body_font, inner_w)
    line_h = 16
    draw.text((40, ty), "\n".join(lines), font=body_font, fill="#374151", spacing=4)
    ty += len(lines) * line_h + box_pad

    return ty + 16


def _draw_footer(draw: ImageDraw.Draw, y: int, width: int, org_name: str) -> int:
    """Draw a footer band. Returns next y position."""
    band_height = 60
    draw.rectangle([0, y, width, y + band_height], fill="#0f172a")
    logo_font = _load_font(11, bold=True)
    small_font = _load_font(8)
    draw.text((30, y + 12), org_name.upper(), font=logo_font, fill="#ffffff")
    draw.text((30, y + 30), "Nairobi, Kenya  •  Document Management System  •  Confidential",
              font=small_font, fill="#94a3b8")
    return y + band_height


def render_asset_png(template_name: str, context: Dict[str, Any],
                     width: int = 900, height: int = 1200) -> str:
    """Render a notification template to a base64-encoded PNG image.

    Args:
        template_name: One of 'invitation_memo', 'notice_poster', 'document_proposal_summary'.
        context: Template context data (recipient_name, title, body, etc.).
        width: Canvas width in pixels.
        height: Canvas height in pixels.

    Returns:
        A base64-encoded data URL: 'data:image/png;base64,<base64>'.
    """
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    y = 20
    accent_color = context.get("accent_color", "#1e40af")
    org_name = context.get("org_name", "KFL Aviation")

    if template_name == "invitation_memo":
        y = _draw_header(draw, y, width,
                         context.get("title", "Account Invitation Memo"),
                         context.get("subtitle", "Secure access to the KFL Aviation Document Management System"),
                         accent_color, "KFL AVIATION DMS • USER ONBOARDING")

        fields = [
            ("Recipient", context.get("recipient_name", "—")),
            ("Email", context.get("recipient_email", "—")),
            ("Role", context.get("role", "—")),
            ("Department", context.get("department", "—")),
            ("Issued By", context.get("issued_by", "System Administrator")),
            ("Date Issued", context.get("issued_at", "—")),
        ]
        y = _draw_meta_grid(draw, y, width, fields)

        # Invite box
        box_pad = 16
        box_h = 120
        draw.rectangle([40, y, width - 40, y + box_h], fill="#eff6ff", outline="#bfdbfe")
        draw.text((40 + box_pad, y + 12), "COMPLETE YOUR ONBOARDING",
                  font=_load_font(9, bold=True), fill="#1e40af")
        code_font = _load_font(20, bold=True)
        code = context.get("invite_code", "—")
        draw.text((40 + box_pad, y + 36), code, font=code_font, fill="#1e3a8a")
        draw.text((40 + box_pad, y + 80),
                  "Login: " + context.get("login_url", "https://stage.kfl.ke/auth/setup"),
                  font=_load_font(10), fill="#1e40af")
        y += box_h + 20

        y = _draw_section_box(draw, y, width, "Purpose",
                              "You have been invited to join the KFL Aviation DMS as a "
                              f"{context.get('role', 'User')}. This memo confirms your account details "
                              "and provides instructions to complete onboarding.",
                              "#1e40af")

    elif template_name == "notice_poster":
        severity = context.get("severity", "medium")
        sev_colors = {
            "critical": "#dc2626",
            "high": "#ea580c",
            "medium": "#ca8a04",
            "low": "#2563eb",
        }
        accent = sev_colors.get(severity, "#ca8a04")
        y = _draw_header(draw, y, width,
                         context.get("title", "Operational Notice"),
                         context.get("subtitle", "KFL Aviation DMS"),
                         accent,
                         f"OPERATIONAL NOTICE  •  SEVERITY: {severity.upper()}  •  ID: {context.get('poster_id', 'NTF-')}")

        fields = [
            ("Issued By", context.get("issued_by", "System")),
            ("Date Issued", context.get("issued_at", "—")),
            ("Severity", severity.title()),
            ("Audience", context.get("audience", "All staff")),
        ]
        y = _draw_meta_grid(draw, y, width, fields)

        y = _draw_section_box(draw, y, width, "Notice Details",
                              context.get("body", "No details provided."), accent)

        action_items = context.get("action_items", [])
        if action_items:
            # Actions section
            draw.text((40, y), "REQUIRED ACTIONS", font=_load_font(9, bold=True), fill=accent)
            y += 20
            body_font = _load_font(11)
            for item in action_items:
                wrapped = _wrap_text(draw, f"•  {item}", body_font, width - 80 - 40)
                for line in wrapped:
                    draw.text((40 + 20, y), line, font=body_font, fill="#374151")
                    y += 16
                y += 6
            y += 10

    elif template_name == "document_proposal_summary":
        severity = context.get("severity", "minor")
        sev_colors = {
            "minor": "#16a34a",
            "major": "#ca8a04",
            "critical": "#dc2626",
        }
        accent = sev_colors.get(severity, "#16a34a")
        y = _draw_header(draw, y, width,
                         context.get("title", "Document Proposal Summary"),
                         context.get("subtitle", "KFL Aviation DMS • Change Proposal"),
                         accent,
                         f"DOCUMENT PROPOSAL  •  {context.get('document_id', 'DOC-')}")

        fields = [
            ("Document", context.get("document_title", "—")),
            ("Proposal ID", context.get("proposal_id", "—")),
            ("Proposed By", context.get("proposed_by", "—")),
            ("Date Submitted", context.get("submitted_at", "—")),
            ("Severity", severity.title()),
            ("Status", context.get("status", "pending_review")),
        ]
        y = _draw_meta_grid(draw, y, width, fields)

        # Original vs Proposed
        draw.text((40, y), "PROPOSED CHANGE", font=_load_font(9, bold=True), fill=accent)
        y += 20

        # Original
        draw.text((40, y), "ORIGINAL", font=_load_font(8, bold=True), fill="#dc2626")
        y += 14
        orig_lines = _wrap_text(draw, context.get("original_text", "—"), _load_font(10), width - 80 - 40)
        draw.text((40, y), "\n".join(orig_lines), font=_load_font(10), fill="#374151", spacing=4)
        y += len(orig_lines) * 14 + 16

        # Proposed
        draw.text((40, y), "PROPOSED", font=_load_font(8, bold=True), fill="#16a34a")
        y += 14
        prop_lines = _wrap_text(draw, context.get("proposed_text", "—"), _load_font(10), width - 80 - 40)
        draw.text((40, y), "\n".join(prop_lines), font=_load_font(10), fill="#374151", spacing=4)
        y += len(prop_lines) * 14 + 20

        # Rationale
        y = _draw_section_box(draw, y, width, "Rationale",
                              context.get("rationale", "No rationale provided."), "#92400e")

    else:
        # Fallback: generic rendering
        y = _draw_header(draw, y, width,
                         context.get("title", "Notification"),
                         context.get("subtitle", "KFL Aviation DMS"),
                         accent_color, "KFL AVIATION DMS")
        y = _draw_section_box(draw, y, width, "Content",
                              context.get("body", "No content provided."), accent_color)

    y = _draw_footer(draw, y, width, org_name)

    # Crop to content
    img = img.crop((0, 0, width, min(y + 20, height)))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


SUPPORTED_TEMPLATES = {
    "invitation_memo": {
        "description": "User onboarding invitation memo",
        "required_fields": ["recipient_name", "recipient_email", "role", "invite_code"],
        "optional_fields": ["title", "subtitle", "department", "issued_by", "issued_at",
                           "expires_at", "login_url", "org_name"],
    },
    "notice_poster": {
        "description": "Safety / operational notice poster",
        "required_fields": ["title", "body"],
        "optional_fields": ["subtitle", "issued_by", "issued_at", "severity", "audience",
                           "poster_id", "badge_text", "action_items", "org_name"],
    },
    "document_proposal_summary": {
        "description": "Document change proposal summary",
        "required_fields": ["document_id", "original_text", "proposed_text"],
        "optional_fields": ["title", "subtitle", "document_title", "proposal_id",
                           "proposed_by", "submitted_at", "severity", "status",
                           "rationale", "org_name"],
    },
}


def get_template_info(template_name: str) -> Optional[Dict[str, Any]]:
    """Return metadata for a supported template, or None if not found."""
    return SUPPORTED_TEMPLATES.get(template_name)


def list_templates() -> List[str]:
    """Return the list of supported template names."""
    return sorted(SUPPORTED_TEMPLATES.keys())
