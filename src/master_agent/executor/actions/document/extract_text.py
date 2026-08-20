"""Turn a document that already exists into trustworthy observed text.

`Filesystem.ReadFile` says what it is -- *"Read a **text** file's
content"* -- and answers `not a text file` for anything else. That is
honest and it is also a wall: the objectives a founder actually has
involve PDFs and Word files, and a mission that cannot open one cannot
reason about it.

This is the smallest capability that removes the wall. Its entire job is
turning a supported document into text somebody can observe. It knows
nothing about what documents are *for*: no CV, contract, invoice or
report semantics live here, and none may. A capability that understood
what it was reading would have to be rewritten for the next kind of
document, and every caller would inherit its opinions.

Extraction is deterministic and native -- `pypdf` for PDF, `python-docx`
for DOCX, a decode for text. No OCR: a scanned page is reported as
yielding no text rather than guessed at, because a guess presented as an
observation is worse than an absence.

READ_ONLY. The source document is opened and never written.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from master_agent.executor.action import (
    Action,
    ExecutionResult,
    default_locations,
    described_with_locations,
    is_unsafe_relative_path,
)
from master_agent.plugins.base import PermissionCategory, RiskTier

EXTRACT_TEXT = "extract_text"

#: Same reasoning as `ReadFileAction.MAX_READ_BYTES`: not a security
#: boundary -- paths are still sandboxed to named roots -- but a mission
#: that pulls an unbounded document into its persisted result is a
#: resource footgun. A 25 MB source comfortably covers real documents.
MAX_SOURCE_BYTES = 25_000_000

#: The extracted text a later step may reason over. Capped because this
#: value flows into a prompt: an unbounded document would silently blow a
#: provider's context window, and a truncated-but-declared result is
#: better than a request that fails for reasons nobody can see.
MAX_TEXT_CHARS = 200_000

#: What this capability can actually open. Membership is a promise, so a
#: format is added here only when it is genuinely extracted -- never to
#: make a caller's path succeed.
SUPPORTED = ("txt", "md", "pdf", "docx")


def _plain(target: Path) -> str:
    """A decode, tried as UTF-8 first and then permissively.

    `errors="replace"` rather than a failure: a document that is *mostly*
    readable is a real observation, and refusing the whole file over one
    bad byte would be a worse answer than a marked one.
    """
    raw = target.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _pdf(target: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(target))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def _docx(target: Path) -> str:
    """Paragraphs and table cells, in document order.

    Tables are included because real documents put load-bearing content in
    them -- a skills matrix, a schedule, a price list -- and a reader that
    silently dropped them would hand the next step a confident, incomplete
    observation.
    """
    from docx import Document as _Docx

    document = _Docx(str(target))
    blocks = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                blocks.append("\t".join(cells))
    return "\n".join(blocks)


_EXTRACTORS = {"txt": _plain, "md": _plain, "pdf": _pdf, "docx": _docx}


class ExtractTextAction(Action):
    name = EXTRACT_TEXT
    description = (
        "Extract the text of an existing document (txt, md, pdf, docx) so a "
        "later step can read or reason over it. The document is not modified."
    )
    risk_tier = RiskTier.READ_ONLY
    permission_category = PermissionCategory.READ
    expected_result = (
        "The document's text content is returned; nothing on disk changes."
    )

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()
        self.description = described_with_locations(
            type(self).description, self._locations
        )

    def required_parameters(self) -> list[str]:
        return ["path"]

    def _paths(self, raw: Any) -> list[str]:
        """One path, or several.

        A discovery step returns however many files it found, and a plan
        written before it ran cannot know how many. Nothing here fans a
        step out into N steps, so the alternative to accepting a list is
        that "read the documents you just found" cannot be planned at all
        -- which is the shape of objective this capability exists for.
        """
        if isinstance(raw, (list, tuple)):
            return [str(item).strip() for item in raw if str(item).strip()]
        return [str(raw).strip()] if str(raw).strip() else []

    def optional_parameters(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "location",
                "type": "string",
                "description": (
                    "Which named root `path` is relative to: "
                    + ", ".join(sorted(self._locations))
                    + "."
                ),
                "default": "desktop",
            },
        ]

    def output_parameters(self) -> list[dict[str, Any]]:
        """What a later step may bind to.

        Deliberately four stable facts rather than everything that could
        be reported. Publishing a field is a promise a plan may depend on,
        so page counts and metadata stay out until something needs them.
        """
        return [
            {"name": "path", "type": "string",
             "description": "The full path of the document that was read."},
            {"name": "filename", "type": "string",
             "description": "The document's file name."},
            {"name": "format", "type": "string",
             "description": "The format it was extracted as: txt, md, pdf or docx."},
            {"name": "text", "type": "string",
             "description": "The document's extracted text content."},
        ]

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        paths = self._paths(parameters.get("path"))
        if not paths:
            errors.append("missing required parameter: path")
        for path in paths:
            if is_unsafe_relative_path(path):
                errors.append(
                    f"unsafe path '{path}': must be relative, no '..' segments"
                )
                continue
            suffix = Path(path).suffix.lstrip(".").lower()
            if suffix not in _EXTRACTORS:
                errors.append(
                    f"unsupported document format '{suffix or 'none'}' in "
                    f"'{path}' (supported: {', '.join(SUPPORTED)})"
                )

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def _one(self, path: str, location_key: str):
        """Extract a single document, or say why not. Returns (output, error)."""
        target = self._locations[location_key] / path
        suffix = target.suffix.lstrip(".").lower()

        if not target.exists():
            return None, f"file not found: {target}"
        if target.is_dir():
            return None, f"{target} is a directory, not a document"

        try:
            size = target.stat().st_size
            if size > MAX_SOURCE_BYTES:
                return None, (
                    f"{target} is {size} bytes, over the "
                    f"{MAX_SOURCE_BYTES}-byte limit"
                )
            text = _EXTRACTORS[suffix](target)
        except ImportError as exc:
            # Named plainly rather than reported as a corrupt document: a
            # missing extractor is an installation fact, and telling a
            # founder their file is unreadable would be false.
            return None, f"no extractor available for .{suffix} documents: {exc}"
        except OSError as exc:
            return None, str(exc)
        except Exception as exc:  # noqa: BLE001 - a damaged document is data
            return None, f"could not extract text from {target.name}: {exc}"

        return {
            "path": str(target),
            "filename": target.name,
            "format": suffix,
            "text": text,
        }, None

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        paths = self._paths(parameters.get("path"))
        location_key = (parameters.get("location") or "desktop").strip().lower()

        extracted = []
        errors = []
        for path in paths:
            output, error = self._one(path, location_key)
            if error is not None:
                errors.append(error)
            else:
                extracted.append(output)

        if not extracted:
            return ExecutionResult(
                success=False, errors=errors or ["no document could be read"]
            )

        if len(extracted) == 1 and len(paths) == 1:
            # The single-document shape, unchanged: one document in, the
            # same four fields out, so every existing caller and binding
            # keeps working exactly as it did.
            single = extracted[0]
            text = single["text"]
            truncated = len(text) > MAX_TEXT_CHARS
            single = dict(single, text=text[:MAX_TEXT_CHARS] if truncated else text)
            single["truncated"] = truncated
            single["documents"] = 1
            return ExecutionResult(success=True, output=single)

        # Several documents: one text, with each document's name above its
        # own content. A later step reasoning over the whole set has to be
        # able to tell which document said what -- an undivided blob would
        # let it attribute one document's claim to another.
        blocks = [
            "--- {} ---\n{}".format(item["filename"], item["text"])
            for item in extracted
        ]
        text = "\n\n".join(blocks)
        truncated = len(text) > MAX_TEXT_CHARS
        if truncated:
            text = text[:MAX_TEXT_CHARS]

        return ExecutionResult(
            success=True,
            output={
                "path": "; ".join(item["path"] for item in extracted),
                "filename": "; ".join(item["filename"] for item in extracted),
                "format": ", ".join(sorted({item["format"] for item in extracted})),
                "text": text,
                "truncated": truncated,
                "documents": len(extracted),
                # Files that were asked for and could not be read are
                # reported, never dropped: a comparison made over three of
                # four documents while claiming four is a wrong answer.
                "unreadable": errors,
            },
        )
