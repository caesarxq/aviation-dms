import html
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import Any


_BLOCK_RE = re.compile(
    r"<(?P<tag>h[1-6]|p|li|tr|figcaption|caption|blockquote|div)\b[^>]*>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
_HEADING_RE = re.compile(r"^\s*(?P<number>\d+(?:\.\d+)*)?[\s.\-:]*(?P<title>.+?)\s*$")
_TOKEN_RE = re.compile(r"\s+|[^\s]+")


@dataclass
class DocumentBlock:
    index: int
    block_type: str
    text: str
    html: str
    section_number: str | None
    section_heading: str | None
    section_index: int = 0

def text_from_html(fragment: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def sanitize_fragment(fragment: str) -> str:
    """Keep only safe structural markup for proposal excerpts."""
    allowed = {"p", "strong", "em", "u", "b", "i", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "br", "table", "thead", "tbody", "tr", "th", "td", "blockquote", "figcaption"}
    fragment = re.sub(r"<\s*(script|style)\b.*?</\s*\1\s*>", "", fragment, flags=re.IGNORECASE | re.DOTALL)

    class Sanitizer(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            tag = tag.lower()
            if tag in allowed:
                self.parts.append(f"<{tag}>")

        def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() in allowed:
                self.parts.append(f"<{tag.lower()}/>")

        def handle_endtag(self, tag: str) -> None:
            tag = tag.lower()
            if tag in allowed and tag != "br":
                self.parts.append(f"</{tag}>")

        def handle_data(self, data: str) -> None:
            self.parts.append(html.escape(data, quote=False))

    parser = Sanitizer()
    parser.feed(fragment)
    return "".join(parser.parts)


def extract_blocks(content: str) -> list[DocumentBlock]:
    matches = list(_BLOCK_RE.finditer(content or ""))
    if not matches and content.strip():
        return [DocumentBlock(0, "section", text_from_html(content), sanitize_fragment(content), None, None)]

    blocks: list[DocumentBlock] = []
    section_number: str | None = None
    section_heading: str | None = None
    section_index = 0
    for index, match in enumerate(matches):
        tag = match.group("tag").lower()
        fragment = match.group(0)
        text = text_from_html(match.group("body"))
        if not text:
            continue
        if tag.startswith("h"):
            heading_match = _HEADING_RE.match(text)
            section_number = heading_match.group("number") if heading_match else None
            section_heading = heading_match.group("title") if heading_match and heading_match.group("number") else text
            section_index = 0
            blocks.append(DocumentBlock(index, "heading", text, sanitize_fragment(fragment), section_number, section_heading, section_index))
            continue
        section_index += 1
        block_type = "paragraph"
        if tag == "li":
            block_type = "list_item"
        elif tag == "tr":
            block_type = "table_row"
        elif tag in {"figcaption", "caption"}:
            block_type = "illustration"
        blocks.append(DocumentBlock(index, block_type, text, sanitize_fragment(fragment), section_number, section_heading, section_index))
    return blocks


def _proposal_type(block_type: str, old_text: str, new_text: str) -> str:
    if block_type == "table_row":
        return "table"
    if block_type == "illustration":
        return "illustration"
    if block_type in {"paragraph", "list_item"} and max(len(old_text), len(new_text)) < 180:
        return "word"
    return "section"


def _excerpt_html(old_text: str, new_text: str, proposed: bool) -> str:
    value = new_text if proposed else old_text
    return sanitize_fragment(f"<p>{html.escape(value, quote=False)}</p>")


def _context_excerpt(text: str, changed: str, radius: int = 100) -> tuple[str, str]:
    if not changed:
        return text[:radius], text[-radius:]
    position = text.find(changed)
    if position < 0:
        return text[:radius], text[-radius:]
    return text[max(0, position - radius):position], text[position + len(changed):position + len(changed) + radius]


def _grouped_token_changes(old_text: str, new_text: str, block_type: str) -> list[dict[str, Any]]:
    old_tokens = _TOKEN_RE.findall(old_text)
    new_tokens = _TOKEN_RE.findall(new_text)
    matcher = SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    raw: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            raw.append({"i1": i1, "i2": i2, "j1": j1, "j2": j2, "changed": max(i2 - i1, j2 - j1)})
    if not raw:
        return []

    groups: list[dict[str, Any]] = []
    for change in raw:
        if not groups:
            groups.append({**change, "changed": change["changed"]})
            continue
        group = groups[-1]
        old_gap = change["i1"] - group["i2"]
        new_gap = change["j1"] - group["j2"]
        gap = max(old_gap, new_gap)
        merged_changed = group["changed"] + change["changed"]
        span_start = min(group["i1"], group["j1"])
        span_end = max(change["i2"], change["j2"])
        density = merged_changed / max(1, span_end - span_start)
        if gap <= 8 or density >= 0.25 or merged_changed >= 10:
            group["i2"] = change["i2"]
            group["j2"] = change["j2"]
            group["changed"] = merged_changed
        else:
            groups.append({**change, "changed": change["changed"]})

    result: list[dict[str, Any]] = []
    total_tokens = max(len(old_tokens), len(new_tokens), 1)
    for group in groups:
        old_value = "".join(old_tokens[group["i1"]:group["i2"]]).strip()
        new_value = "".join(new_tokens[group["j1"]:group["j2"]]).strip()
        span = max(group["i2"] - group["i1"], group["j2"] - group["j1"], 1)
        density = round(group["changed"] / span, 3)
        if group["changed"] >= 10 or density >= 0.25:
            granularity = "paragraph" if block_type in {"paragraph", "list_item"} else "section"
            reason = "paragraph rewrite" if granularity == "paragraph" else "dense block rewrite"
        elif group["changed"] > 1:
            granularity = "phrase"
            reason = "nearby token changes"
        else:
            granularity = "word"
            reason = "single local token change"
        result.append({
            "original_text": old_value,
            "proposed_text": new_value,
            "changed_token_count": group["changed"],
            "change_density": density,
            "granularity": granularity,
            "grouping_reason": reason,
        })
    return result


def detect_proposals(original_content: str, proposed_content: str, *, base_version_id: str) -> list[dict[str, Any]]:
    original_blocks = extract_blocks(original_content)
    proposed_blocks = extract_blocks(proposed_content)
    old_texts = [block.text for block in original_blocks]
    new_texts = [block.text for block in proposed_blocks]
    matcher = SequenceMatcher(a=old_texts, b=new_texts, autojunk=False)
    proposals: list[dict[str, Any]] = []
    sequence = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        pairs = max(i2 - i1, j2 - j1)
        for offset in range(pairs):
            old_block = original_blocks[i1 + offset] if i1 + offset < i2 else None
            new_block = proposed_blocks[j1 + offset] if j1 + offset < j2 else None
            reference_block = new_block or old_block
            if reference_block is None or reference_block.block_type == "heading":
                continue
            old_text = old_block.text if old_block else ""
            new_text = new_block.text if new_block else ""
            block_type = reference_block.block_type
            section_number = reference_block.section_number
            section_heading = reference_block.section_heading
            for change_detail in _grouped_token_changes(old_text, new_text, block_type):
                sequence += 1
                local_old = change_detail["original_text"]
                local_new = change_detail["proposed_text"]
                context_before, context_after = _context_excerpt(old_text or new_text, local_old or local_new)
                section_label = f"§{section_number} — {section_heading}" if section_number and section_heading else (section_heading or "Unnumbered section")
                target_ref = f"{section_label} · {block_type.replace('_', ' ')} {reference_block.section_index or reference_block.index + 1}"
                proposals.append({
                    "base_version_id": base_version_id,
                    "proposal_type": change_detail["granularity"],
                    "target_ref": target_ref,
                    "section_number": section_number,
                    "section_heading": section_heading,
                    "block_type": block_type,
                    "block_index": reference_block.index,
                    "anchor_id": f"block-{reference_block.index}",
                    "original_text": local_old,
                    "proposed_text": local_new,
                    "changed_token_count": change_detail["changed_token_count"],
                    "change_density": change_detail["change_density"],
                    "grouping_reason": change_detail["grouping_reason"],
                    "context_before": context_before,
                    "context_after": context_after,
                    "original_excerpt_html": _excerpt_html(local_old, local_new, False),
                    "proposed_excerpt_html": _excerpt_html(local_old, local_new, True),
                    "change_sequence": sequence,
                })
    if not proposals:
        original_text = text_from_html(original_content)
        proposed_text = text_from_html(proposed_content)
        if original_text != proposed_text:
            reference_block = proposed_blocks[-1] if proposed_blocks else (original_blocks[-1] if original_blocks else DocumentBlock(0, "section", "", "", None, None))
            section_number = reference_block.section_number
            section_heading = reference_block.section_heading
            section_label = f"§{section_number} — {section_heading}" if section_number and section_heading else (section_heading or "Unnumbered section")
            for change_detail in _grouped_token_changes(original_text, proposed_text, "section"):
                sequence += 1
                local_old = change_detail["original_text"]
                local_new = change_detail["proposed_text"]
                proposals.append({
                    "base_version_id": base_version_id,
                    "proposal_type": change_detail["granularity"],
                    "target_ref": f"{section_label} · document tail",
                    "section_number": section_number,
                    "section_heading": section_heading,
                    "block_type": "section",
                    "block_index": reference_block.index,
                    "anchor_id": f"block-{reference_block.index}",
                    "context_before": original_text[-100:],
                    "context_after": "",
                    "original_text": local_old,
                    "proposed_text": local_new,
                    "changed_token_count": change_detail["changed_token_count"],
                    "change_density": change_detail["change_density"],
                    "grouping_reason": change_detail["grouping_reason"],
                    "original_excerpt_html": _excerpt_html(local_old, local_new, False),
                    "proposed_excerpt_html": _excerpt_html(local_old, local_new, True),
                    "change_sequence": sequence,
                })
    return proposals
