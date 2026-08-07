"""Kalpavriksha Founder Edition — single launcher (C33 Desktop Alpha).

    python app.py
    python app.py --founder-name Onkar

Everything this script does is `master_agent.founder_edition.console.main`
— boot Founder Edition (C24/C30), wire it to the Conversation Engine
(C31) and the Communication Layer (C32), and hand the terminal to a REPL.
This file exists only so the brief's own literal instruction ("python
app.py... should produce a working Founder Edition") has something to
run; every actual behaviour lives in the package.
"""
from __future__ import annotations

from master_agent.founder_edition.console import main

if __name__ == "__main__":
    raise SystemExit(main())
