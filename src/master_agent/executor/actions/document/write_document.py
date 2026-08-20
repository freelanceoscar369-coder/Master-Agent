"""Write text into a new document, in a format that is what it claims.

The rule this exists to keep is narrow and absolute: **a `.docx` file must
be a real Word document.** Writing plain text under that extension would
produce a file the founder double-clicks and Word refuses to open, and a
mission that reported success while doing it would be lying in the most
practical possible way.

So `format` is not decoration. `docx` builds an actual Word document
through `python-docx`; `txt` and `md` write text. If a format cannot be
produced honestly, this refuses rather than approximating it.

REVERSIBLE_WRITE, so the Permission System gates it -- which is the whole
reason a mission pauses before its first real change. It knows nothing
about what is being written: no CV, letter or report semantics live here.
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

WRITE_DOCUMENT = "write_document"

#: Formats that can be produced *honestly*. A format is listed only when
#: the file written is genuinely of that type.
WRITABLE = ("txt", "md", "docx")


def _write_docx(target: Path, content: str) -> None:
    """A real Word document: blank lines separate paragraphs, which is how
    the text will actually look when opened."""
    from docx import Document as _Docx

    document = _Docx()
    for block in content.split("\n"):
        document.add_paragraph(block)
    document.save(str(target))


class WriteDocumentAction(Action):
    name = WRITE_DOCUMENT
    description = (
        "Write text into a new document file in a given format (txt, md, docx). "
        "A docx is written as a real Word document, never text under a docx name."
    )
    risk_tier = RiskTier.REVERSIBLE_WRITE
    permission_category = PermissionCategory.MODIFY
    expected_result = "The document exists at the given path with the given content."

    def __init__(self, locations: dict[str, Path] | None = None) -> None:
        self._locations = locations or default_locations()

    def required_parameters(self) -> list[str]:
        return ["path", "content"]

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
            {
                "name": "format",
                "type": "string",
                "description": (
                    "The document format to write: txt, md or docx. Defaults to "
                    "the extension of `path`, which is normally what you want."
                ),
                "default": None,
            },
            {
                "name": "overwrite",
                "type": "boolean",
                "description": (
                    "Whether an existing file at this path may be replaced. "
                    "False by default, so an original is never lost by accident."
                ),
                "default": False,
            },
        ]

    def output_parameters(self) -> list[dict[str, Any]]:
        return [
            {"name": "path", "type": "string",
             "description": "The full path of the document that was written."},
            {"name": "filename", "type": "string",
             "description": "The written document's file name."},
            {"name": "format", "type": "string",
             "description": "The format it was written as."},
        ]

    def _format_of(self, parameters: dict[str, Any]) -> str:
        declared = (parameters.get("format") or "").strip().lower()
        if declared:
            return declared
        return Path((parameters.get("path") or "").strip()).suffix.lstrip(".").lower()

    def validate(self, parameters: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        path = (parameters.get("path") or "").strip()
        if not path:
            errors.append("missing required parameter: path")
        elif is_unsafe_relative_path(path):
            errors.append(f"unsafe path '{path}': must be relative, no '..' segments")

        if parameters.get("content") is None:
            errors.append("missing required parameter: content")

        fmt = self._format_of(parameters)
        if fmt not in WRITABLE:
            errors.append(
                f"unsupported document format '{fmt or 'none'}' "
                f"(supported: {', '.join(WRITABLE)})"
            )
        else:
            suffix = Path(path).suffix.lstrip(".").lower()
            if suffix and suffix != fmt:
                # The file must be what its name says. Allowing these to
                # disagree is precisely how a text file ends up named
                # `.docx` and refuses to open.
                errors.append(
                    f"format '{fmt}' does not match the '.{suffix}' extension in "
                    f"'{path}': a document must be what its name says it is"
                )

        location_key = (parameters.get("location") or "desktop").strip().lower()
        if location_key not in self._locations:
            known = ", ".join(sorted(self._locations)) or "none configured"
            errors.append(f"unknown location '{location_key}' (known: {known})")

        return errors

    def run(self, parameters: dict[str, Any]) -> ExecutionResult:
        path = parameters["path"].strip()
        content = parameters["content"]
        if not isinstance(content, str):
            content = str(content)
        location_key = (parameters.get("location") or "desktop").strip().lower()
        fmt = self._format_of(parameters)
        target = self._locations[location_key] / path

        if target.exists() and not parameters.get("overwrite"):
            return ExecutionResult(
                success=False,
                errors=[
                    f"{target} already exists (set 'overwrite': true to replace it)"
                ],
            )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if fmt == "docx":
                _write_docx(target, content)
            else:
                target.write_text(content, encoding="utf-8")
        except ImportError as exc:
            return ExecutionResult(
                success=False,
                errors=[f"no writer available for .{fmt} documents: {exc}"],
            )
        except OSError as exc:
            return ExecutionResult(success=False, errors=[str(exc)])

        return ExecutionResult(
            success=True,
            output={
                "path": str(target),
                "filename": target.name,
                "format": fmt,
            },
        )
