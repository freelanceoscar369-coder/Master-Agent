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

    def required_parameters(self) -> list[str]:
        return ["path"]

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

        path = (parameters.get("path") or "").strip()
        if not path:
            errors.append("missing required parameter: path")
        elif is_unsafe_relative_path(path):
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")
        else:
            suffix = Path(path).suffix.lstrip(".").lower()
            if suffix not in _EXTRACTORS:
                errors.append(
                    f"unsupported document format '{suffix or 'none'}' "
                    f"(supported: {', '.join(SUPPORTED)})"
                )

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = parameters["path"].strip()
        location_key = (parameters.get("location") or "desktop").strip().lower()
        target = self._locations[location_key] / path
        suffix = target.suffix.lstrip(".").lower()

        if not target.exists():
            return ExecutionResult(success=False, errors=[f"file not found: {target}"])
        if target.is_dir():
            return ExecutionResult(
                success=False, errors=[f"{target} is a directory, not a document"]
            )

        try:
            size = target.stat().st_size
            if size > MAX_SOURCE_BYTES:
                return ExecutionResult(
                    success=False,
                    errors=[
                        f"{target} is {size} bytes, over the "
                        f"{MAX_SOURCE_BYTES}-byte limit"
                    ],
                )
            text = _EXTRACTORS[suffix](target)
        except ImportError as exc:
            # Named plainly rather than reported as a corrupt document:
            # a missing extractor is an installation fact, and telling a
            # founder their file is unreadable would be false.
            return ExecutionResult(
                success=False,
                errors=[f"no extractor available for .{suffix} documents: {exc}"],
            )
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])
        except Exception as exc:  # noqa: BLE001 - a damaged document is data, not a crash
            return ExecutionResult(
                success=False,
                errors=[f"could not extract text from {target.name}: {exc}"],
            )

        truncated = len(text) > MAX_TEXT_CHARS
        if truncated:
            text = text[:MAX_TEXT_CHARS]

        return ExecutionResult(
            success=True,
            output={
                "path": str(target),
                "filename": target.name,
                "format": suffix,
                "text": text,
                # Stated, never silent. A later step reasoning over a
                # partial document should be able to know that it is.
                "truncated": truncated,
            },
        )
