"""Word (.docx) handling: extract candidate answers, write values back into the
original template (preserving its formatting), and diff against the template.

Two capture mechanisms are supported for Word:

* **Named placeholders** like ``{{full_name}}`` — used as the write target for the
  in-browser editor and as an "unfilled" sentinel (if the token is still present,
  the field was not filled).
* **Content controls** (Word structured document tags) whose *tag* equals the
  field id — the robust way to extract answers from an uploaded, edited document,
  because the control survives editing.

Design note / tradeoff: rich-text answers entered in the browser are stored in
full (HTML) on the submission record and shown in the review UI. When injected
into the .docx we map a safe subset (bold / italic / underline / line breaks)
into runs that inherit the template's existing formatting. Full HTML->DOCX
styling (nested lists, tables, colours) is an intentional non-goal so the output
file is always valid and macro-free.
"""
from __future__ import annotations

import copy
import io
import re
from dataclasses import dataclass, field
from html import escape as _html_escape
from html.parser import HTMLParser

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.schemas.field_spec import FieldDefinition

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")


@dataclass
class TextSegment:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False


@dataclass
class ExtractionResult:
    values: dict[str, str | None]
    # Fields whose placeholder was edited away but whose value could not be
    # isolated programmatically (free-form upload without a content control).
    uncaptured: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Loading & iteration helpers
# --------------------------------------------------------------------------- #
def load_document(data: bytes) -> Document:
    return Document(io.BytesIO(data))


def _iter_paragraphs(doc: Document):
    """Yield every paragraph in the body, tables, headers and footers."""
    def _walk(container):
        for para in getattr(container, "paragraphs", []):
            yield para
        for table in getattr(container, "tables", []):
            for row in table.rows:
                for cell in row.cells:
                    yield from _walk(cell)

    yield from _walk(doc)
    for section in doc.sections:
        yield from _walk(section.header)
        yield from _walk(section.footer)


def get_full_text(doc: Document) -> str:
    return "\n".join(p.text for p in _iter_paragraphs(doc))


# --------------------------------------------------------------------------- #
# Placeholder + content-control discovery
# --------------------------------------------------------------------------- #
def find_placeholder_tokens(doc: Document) -> set[str]:
    """Return the set of placeholder names still present, e.g. {'full_name'}."""
    tokens: set[str] = set()
    for para in _iter_paragraphs(doc):
        for match in _PLACEHOLDER_RE.finditer(para.text):
            tokens.add(match.group(1))
    return tokens


def extract_content_controls(doc: Document) -> dict[str, str]:
    """Map content-control tag -> concatenated inner text."""
    result: dict[str, str] = {}
    for sdt in doc.element.body.iter(qn("w:sdt")):
        sdt_pr = sdt.find(qn("w:sdtPr"))
        if sdt_pr is None:
            continue
        tag_el = sdt_pr.find(qn("w:tag"))
        if tag_el is None:
            continue
        tag = tag_el.get(qn("w:val"))
        if not tag:
            continue
        content = sdt.find(qn("w:sdtContent"))
        texts = content.iter(qn("w:t")) if content is not None else []
        result[tag] = "".join(t.text or "" for t in texts)
    return result


def _placeholder_name(fd: FieldDefinition) -> str:
    raw = fd.placeholder or fd.id
    return raw.strip().strip("{}").strip()


def _body_paragraphs(doc: Document):
    """Body paragraphs + table-cell paragraphs (excludes headers/footers)."""
    def _walk(container):
        for para in getattr(container, "paragraphs", []):
            yield para
        for table in getattr(container, "tables", []):
            for row in table.rows:
                for cell in row.cells:
                    yield from _walk(cell)

    yield from _walk(doc)


def build_document_view(data: bytes, fields: list[FieldDefinition]) -> list[dict]:
    """Return an ordered list of paragraph blocks for the inline candidate editor.

    Each block has ``runs``; a run is either ``{"text": "..."}`` or
    ``{"field": "<field_id>"}`` where a recognised placeholder was found. The
    frontend renders text runs as-is and field runs as inline editors.
    """
    token_to_field = {_placeholder_name(fd): fd.id for fd in fields}
    doc = load_document(data)
    blocks: list[dict] = []
    for para in _body_paragraphs(doc):
        text = para.text
        runs: list[dict] = []
        last = 0
        for match in _PLACEHOLDER_RE.finditer(text):
            if match.start() > last:
                runs.append({"text": text[last:match.start()]})
            token = match.group(1)
            if token in token_to_field:
                runs.append({"field": token_to_field[token]})
            else:
                runs.append({"text": match.group(0)})
            last = match.end()
        if last < len(text):
            runs.append({"text": text[last:]})
        style = para.style.name if para.style is not None else None
        blocks.append({"type": "paragraph", "style": style, "runs": runs})
    return blocks


# --------------------------------------------------------------------------- #
# Extraction (upload path)
# --------------------------------------------------------------------------- #
def extract_field_values(data: bytes, fields: list[FieldDefinition]) -> ExtractionResult:
    doc = load_document(data)
    controls = extract_content_controls(doc)
    present_tokens = find_placeholder_tokens(doc)

    values: dict[str, str | None] = {}
    uncaptured: list[str] = []

    for fd in fields:
        if fd.id in controls:
            values[fd.id] = controls[fd.id]
            continue
        name = _placeholder_name(fd)
        if name in present_tokens:
            values[fd.id] = None  # still unfilled
        else:
            # The placeholder was replaced with free text we cannot isolate.
            values[fd.id] = None
            uncaptured.append(fd.id)
    return ExtractionResult(values=values, uncaptured=uncaptured)


# --------------------------------------------------------------------------- #
# HTML -> segments (for rich-text write-back)
# --------------------------------------------------------------------------- #
class _RichTextParser(HTMLParser):
    _BLOCK = {"p", "div", "li", "br", "ul", "ol"}

    def __init__(self):
        super().__init__()
        self.segments: list[TextSegment] = []
        self._bold = 0
        self._italic = 0
        self._underline = 0
        self._need_break = False

    def handle_starttag(self, tag, attrs):
        if tag in ("b", "strong"):
            self._bold += 1
        elif tag in ("i", "em"):
            self._italic += 1
        elif tag in ("u",):
            self._underline += 1
        elif tag == "br":
            self._push("\n")

    def handle_endtag(self, tag):
        if tag in ("b", "strong"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("i", "em"):
            self._italic = max(0, self._italic - 1)
        elif tag in ("u",):
            self._underline = max(0, self._underline - 1)
        elif tag in self._BLOCK:
            self._need_break = True

    def handle_data(self, data):
        if not data:
            return
        if self._need_break:
            self._push("\n")
            self._need_break = False
        self._push(data)

    def _push(self, text: str):
        self.segments.append(
            TextSegment(
                text=text,
                bold=self._bold > 0,
                italic=self._italic > 0,
                underline=self._underline > 0,
            )
        )


def _to_segments(value: str, rich: bool) -> list[TextSegment]:
    if value is None:
        value = ""
    if not rich:
        return [TextSegment(text=str(value))]
    parser = _RichTextParser()
    parser.feed(str(value))
    segments = [s for s in parser.segments if s.text != ""]
    return segments or [TextSegment(text="")]


def _plain_text(segments: list[TextSegment]) -> str:
    return "".join(s.text for s in segments)


# --------------------------------------------------------------------------- #
# Write-back (in-browser save path)
# --------------------------------------------------------------------------- #
def _run_index_at(runs, pos: int) -> tuple[int, int]:
    acc = 0
    for i, r in enumerate(runs):
        n = len(r.text)
        if pos < acc + n:
            return i, pos - acc
        acc += n
    last = len(runs) - 1
    return last, len(runs[last].text)


def _clone_rpr(run):
    rpr = run._element.find(qn("w:rPr"))
    return copy.deepcopy(rpr) if rpr is not None else None


def _make_run_element(segment: TextSegment, base_rpr):
    r = OxmlElement("w:r")
    rpr = copy.deepcopy(base_rpr) if base_rpr is not None else OxmlElement("w:rPr")
    for flag, tag in (
        (segment.bold, "w:b"),
        (segment.italic, "w:i"),
        (segment.underline, "w:u"),
    ):
        if flag and rpr.find(qn(tag)) is None:
            el = OxmlElement(tag)
            if tag == "w:u":
                el.set(qn("w:val"), "single")
            rpr.append(el)
    r.append(rpr)
    parts = segment.text.split("\n")
    for j, part in enumerate(parts):
        if j > 0:
            r.append(OxmlElement("w:br"))
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = part
        r.append(t)
    return r


def _replace_placeholder_in_paragraph(paragraph, token: str, segments: list[TextSegment]) -> bool:
    """Replace ``{{token}}`` in a paragraph, preserving surrounding formatting."""
    marker = "{{" + token + "}}"
    replaced = False
    for _ in range(50):  # bound iterations; guards against pathological input
        runs = paragraph.runs
        text = "".join(r.text for r in runs)
        idx = text.find(marker)
        if idx == -1:
            break
        start_i, start_off = _run_index_at(runs, idx)
        end_i, end_off = _run_index_at(runs, idx + len(marker) - 1)
        anchor = runs[start_i]
        base_rpr = _clone_rpr(anchor)
        prefix = anchor.text[:start_off]
        suffix = runs[end_i].text[end_off + 1:]

        if start_i == end_i:
            anchor.text = prefix
            runs[start_i]._element  # keep reference
        else:
            anchor.text = prefix
            for k in range(start_i + 1, end_i):
                runs[k].text = ""
            runs[end_i].text = suffix

        # Insert the replacement runs immediately after the anchor.
        prev = anchor._element
        for seg in segments:
            new_r = _make_run_element(seg, base_rpr)
            prev.addnext(new_r)
            prev = new_r
        # Re-attach the suffix (only needed when single-run split).
        if start_i == end_i and suffix:
            tail = _make_run_element(TextSegment(text=suffix), base_rpr)
            prev.addnext(tail)
        replaced = True
    return replaced


def _set_content_control(doc: Document, tag: str, value: str) -> bool:
    for sdt in doc.element.body.iter(qn("w:sdt")):
        sdt_pr = sdt.find(qn("w:sdtPr"))
        if sdt_pr is None:
            continue
        tag_el = sdt_pr.find(qn("w:tag"))
        if tag_el is None or tag_el.get(qn("w:val")) != tag:
            continue
        content = sdt.find(qn("w:sdtContent"))
        if content is None:
            continue
        texts = list(content.iter(qn("w:t")))
        if texts:
            texts[0].text = value
            for extra in texts[1:]:
                extra.text = ""
            return True
    return False


def write_field_values(
    data: bytes, fields: list[FieldDefinition], values: dict[str, object]
) -> bytes:
    """Write candidate ``values`` into the original template, returning new bytes."""
    doc = load_document(data)
    control_tags = set(extract_content_controls(doc).keys())

    for fd in fields:
        if fd.id not in values or values[fd.id] is None:
            continue
        raw = values[fd.id]
        segments = _to_segments(str(raw), fd.rich_text)
        if fd.id in control_tags:
            _set_content_control(doc, fd.id, _plain_text(segments))
            continue
        token = _placeholder_name(fd)
        for para in _iter_paragraphs(doc):
            if "{{" + token + "}}" in para.text:
                _replace_placeholder_in_paragraph(para, token, segments)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


# --------------------------------------------------------------------------- #
# Full-document HTML <-> docx (Google Docs-style free editing)
# --------------------------------------------------------------------------- #
def _runs_to_html(paragraph) -> str:
    out: list[str] = []
    for run in paragraph.runs:
        text = _html_escape(run.text or "")
        if text == "":
            continue
        if run.bold:
            text = f"<strong>{text}</strong>"
        if run.italic:
            text = f"<em>{text}</em>"
        if run.underline:
            text = f"<u>{text}</u>"
        out.append(text)
    return "".join(out)


def _is_list_paragraph(paragraph, style_name: str) -> bool:
    if "list" in (style_name or "").lower():
        return True
    p_pr = paragraph._p.find(qn("w:pPr"))
    return p_pr is not None and p_pr.find(qn("w:numPr")) is not None


def document_to_html(data: bytes) -> str:
    """Render the document body as editable HTML for the in-browser doc editor."""
    doc = load_document(data)
    parts: list[str] = []
    list_open = False

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            parts.append("</ul>")
            list_open = False

    for para in _body_paragraphs(doc):
        style = (para.style.name if para.style is not None else "") or ""
        inner = _runs_to_html(para)
        if _is_list_paragraph(para, style):
            if not list_open:
                parts.append("<ul>")
                list_open = True
            parts.append(f"<li>{inner or '<br>'}</li>")
            continue
        close_list()
        low = style.lower()
        if low == "title" or low.startswith("heading 1"):
            parts.append(f"<h1>{inner or '<br>'}</h1>")
        elif low.startswith("heading 2"):
            parts.append(f"<h2>{inner or '<br>'}</h2>")
        elif low.startswith("heading 3"):
            parts.append(f"<h3>{inner or '<br>'}</h3>")
        else:
            parts.append(f"<p>{inner or '<br>'}</p>")
    close_list()
    return "".join(parts) or "<p><br></p>"


class _DocxBuilder(HTMLParser):
    """Builds a clean .docx from a safe subset of HTML produced by the editor."""

    def __init__(self):
        super().__init__()
        self.doc = Document()
        self.para = None
        self._bold = 0
        self._italic = 0
        self._underline = 0
        self._list: list[str] = []

    def _new_para(self, style: str | None = None):
        try:
            self.para = self.doc.add_paragraph(style=style) if style else self.doc.add_paragraph()
        except KeyError:
            self.para = self.doc.add_paragraph()

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "div"):
            self._new_para()
        elif tag == "h1":
            self._new_para("Heading 1")
        elif tag == "h2":
            self._new_para("Heading 2")
        elif tag == "h3":
            self._new_para("Heading 3")
        elif tag == "ul":
            self._list.append("List Bullet")
        elif tag == "ol":
            self._list.append("List Number")
        elif tag == "li":
            self._new_para(self._list[-1] if self._list else "List Bullet")
        elif tag == "br":
            if self.para is None:
                self._new_para()
            self.para.add_run().add_break()
        elif tag in ("strong", "b"):
            self._bold += 1
        elif tag in ("em", "i"):
            self._italic += 1
        elif tag == "u":
            self._underline += 1

    def handle_endtag(self, tag):
        if tag in ("strong", "b"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("em", "i"):
            self._italic = max(0, self._italic - 1)
        elif tag == "u":
            self._underline = max(0, self._underline - 1)
        elif tag in ("ul", "ol") and self._list:
            self._list.pop()

    def handle_data(self, data):
        if not data:
            return
        if self.para is None:
            if data.strip() == "":
                return
            self._new_para()
        run = self.para.add_run(data)
        if self._bold:
            run.bold = True
        if self._italic:
            run.italic = True
        if self._underline:
            run.underline = True


def html_to_docx(html: str) -> bytes:
    """Convert editor HTML back into a valid, macro-free .docx."""
    builder = _DocxBuilder()
    builder.feed(html or "")
    if not builder.doc.paragraphs:
        builder.doc.add_paragraph("")
    out = io.BytesIO()
    builder.doc.save(out)
    return out.getvalue()
