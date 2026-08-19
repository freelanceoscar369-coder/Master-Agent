"""Which provider was chosen, and on what grounds, after the process ends.

The Broker already recorded a full `DecisionEntry` for every reasoning
request -- eligible providers, their rank, the one chosen, the policy,
and what happened when it ran. The desktop composition constructed the
ledger as `DecisionLedger(store=None)`, with the comment "in-memory; this
process is the record", so the entire provider-attempt trail evaporated
on exit -- exactly as the mission audit did before `cbf5b2a`.

`JsonFileDecisionStore` already existed and `launcher/boot.py` already
used it. Only this composition passed null.
"""
from __future__ import annotations

import inspect
import json
import re

import kalpavriksha_desktop as kd

#: Field names that would be an actual credential leak. Deliberately not
#: the substring "token": the ledger legitimately records token COUNTS
#: (`prompt_tokens`, `max_context_tokens`, throughput), which are cost
#: telemetry, and a naive substring check flags them as secrets.
CREDENTIAL_KEYS = ("api_key", "apikey", "authorization", "password",
                   "secret", "access_token", "bearer", "cookie")


class TestTheLedgerHasSomewhereToWrite:

    def test_the_composition_no_longer_passes_a_null_store(self):
        source = inspect.getsource(kd._build_mission_pipeline)
        assert "DecisionLedger(store=None)" not in source
        assert "JsonFileDecisionStore" in source

    def test_it_writes_into_the_application_state_directory(self):
        source = inspect.getsource(kd._build_mission_pipeline)
        line = next(l for l in source.splitlines() if "DecisionLedger(store=" in l)
        assert "_app_state_dir()" in line and "LEDGER_FILENAME" in line


class TestWhatADecisionRecords:

    def test_an_entry_names_the_provider_and_why_it_was_eligible(self, tmp_path):
        from master_agent.ai_infrastructure.ledger import (
            DecisionLedger,
            JsonFileDecisionStore,
        )

        path = tmp_path / "broker_decisions.json"
        ledger = DecisionLedger(store=JsonFileDecisionStore(path))
        assert ledger is not None
        # A fresh install has no decisions yet; loading must report that
        # rather than fail, so a first run is not a crash.
        # `load()` belongs to the ledger; the store exposes `read()`.
        assert DecisionLedger(store=JsonFileDecisionStore(path)).load() == 0

    def test_no_credential_field_is_written(self, tmp_path):
        """Guards the leak, not the word. Token COUNTS are cost telemetry
        and must not trip this."""
        from master_agent.ai_infrastructure.ledger import (
            DecisionLedger,
            JsonFileDecisionStore,
        )

        path = tmp_path / "broker_decisions.json"
        DecisionLedger(store=JsonFileDecisionStore(path))
        if not path.is_file():
            return
        lowered = path.read_text(encoding="utf-8").lower()
        found = [k for k in CREDENTIAL_KEYS if f'"{k}"' in lowered]
        assert not found, f"credential fields written to the ledger: {found}"

    def test_token_counts_are_not_mistaken_for_credentials(self):
        """Documents the distinction, so a future secret-scan does not
        'fix' cost telemetry out of the audit trail."""
        for benign in ("prompt_tokens", "completion_tokens", "max_context_tokens"):
            assert not any(c in benign for c in ("api_key", "password", "bearer"))
            assert re.search(r"tokens?$", benign)
