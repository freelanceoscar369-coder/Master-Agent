"""Document execution joined to the existing filesystem verifier.

Writing a text document is not complete merely because the Action returned
success.  The production gateway must re-open the resulting file and compare
its exact text with the content the step supplied.
"""
from __future__ import annotations

from master_agent.executor.executor import LocalExecutor
from master_agent.permissions.permission_system import PermissionSystem
from master_agent.plugins.document_gateway import DocumentGateway
from master_agent.plugins.document_plugin import DocumentPlugin
from master_agent.verification.evidence import ExpectedOutcome, ObservationCheck


def _expected() -> ExpectedOutcome:
    return ExpectedOutcome(
        description="the requested document exists with the requested content",
        checks=[ObservationCheck(field="empty", operator="equals", value=False)],
    )


def _gateway(tmp_path):
    permissions = PermissionSystem()
    executor = LocalExecutor(permissions)
    locations = {"desktop": tmp_path}
    plugin = DocumentPlugin(executor, locations)
    return DocumentGateway(plugin, locations=locations)


def test_markdown_write_is_independently_re_read_and_matched(tmp_path):
    gateway = _gateway(tmp_path)
    payload = {
        "path": "report.md",
        "location": "desktop",
        "format": "md",
        "content": "# Evidence-backed report\n\nExact body.",
    }

    assert gateway.invoke("write_document", payload).success is True
    evidence = gateway.verify("write_document", payload, _expected())

    assert evidence is not None
    assert evidence.verdict.value == "matched"
    assert evidence.observation["content_text_sha256"]


def test_tampered_markdown_does_not_match_the_step_content(tmp_path):
    gateway = _gateway(tmp_path)
    payload = {
        "path": "report.md",
        "location": "desktop",
        "format": "md",
        "content": "the intended report",
    }
    assert gateway.invoke("write_document", payload).success is True
    (tmp_path / "report.md").write_text("different content", encoding="utf-8")

    evidence = gateway.verify("write_document", payload, _expected())

    assert evidence is not None
    assert evidence.verdict.value != "matched"


def test_docx_is_not_overclaimed_as_exact_text_verifiable(tmp_path):
    gateway = _gateway(tmp_path)
    payload = {
        "path": "report.docx",
        "location": "desktop",
        "format": "docx",
        "content": "text stored inside a Word package",
    }
    assert gateway.invoke("write_document", payload).success is True

    assert gateway.verify("write_document", payload, _expected()) is None
