# Mission Brief 030 — Desktop Executive (Foundation Layer)

Status: **Shipped** — 2026-07-30

**No ADR.** Rule 5 said stop and produce one if architecture had to
change. Nothing did — see §1.

## Objective

Give Kalpavriksha eyes and hands over the local machine: discover what
software exists, what version, what is running, and launch, open, or close
it. Not the AI Capability Broker. **The Desktop Executive executes; the
Broker decides.**

## 1. Rule 5, verified

Every new file lives in a new `desktop/` package. The Action contract
(MB002), the `Plugin` interface (ADR-0003), the `LocalExecutor`, and
Mission Control's manifest-reading adapter were all used exactly as they
are:

```
$ git diff --name-only v0.11.0-miracle-029 -- \
    src/master_agent/runtime src/master_agent/mission_control \
    src/master_agent/persistence src/master_agent/executor \
    src/master_agent/plugins
(empty)
```

Adding a twelve-capability Executive with **zero architecture change** is
the strongest evidence yet that MB002's contract generalises — the same
claim MB005 made for eleven filesystem actions and MB022 for the browser.

Deliberately *not* placed in `plugins/` or `executor/actions/`: adding a
file there would have tripped the ratified-exceptions guard, and the
Desktop Executive is its own subsystem anyway.

## 2. What it is (Deliverables 1, 3)

`DesktopPlugin`, registered by `discover_executives` like every other
Executive, exposing twelve capabilities:

| Capability | Risk tier | Why |
|---|---|---|
| `Desktop.IsInstalled` | `READ_ONLY` | asking |
| `Desktop.GetVersion` | `READ_ONLY` | asking |
| `Desktop.ListInstalledSoftware` | `READ_ONLY` | asking |
| `Desktop.ListRunningProcesses` | `READ_ONLY` | asking |
| `Desktop.IsRunning` | `READ_ONLY` | asking |
| `Desktop.LaunchApplication` | `REVERSIBLE_WRITE` | closing undoes it |
| `Desktop.OpenFile` / `.OpenFolder` | `REVERSIBLE_WRITE` | as above |
| `Desktop.BringToFront` / `.FocusWindow` | `REVERSIBLE_WRITE` | as above |
| `Desktop.CloseApplication` | **`IRREVERSIBLE`** | unsaved work is gone |
| `Desktop.ExecuteCommand` | **`IRREVERSIBLE`** | it runs anything |

The two irreversible tiers are the judgement calls worth checking. Closing
an editor destroys unsaved work, and no amount of "it usually prompts"
makes that reversible. ADR-0009 then guarantees mechanically that **no
standing grant can ever satisfy either** — every close and every command
is a fresh founder decision, surfaced in the Approval panel MB028.1 built.

`ExecuteCommand` is **argv-only**: a shell string is refused at
validation, so a payload cannot smuggle a pipeline or a redirect.

## 3. The seam that made 228 tests possible

`SystemProbe` is the one place anything touches the real machine —
`which`, `exists`, `run`, `start`, `processes`. Everything else in
`desktop/` is pure logic over what a probe returns.

So the entire suite runs against a `FakeProbe` describing a machine, and
**no test launches Chrome, kills a process, or shells out.** Same shape as
MB024's `ExecutiveGateway`: a small protocol, one real implementation, one
fake.

`NullSystemProbe` is not a test double — it is the real fallback, so an
Executive built without a probe reports an honest empty inventory instead
of crashing.

## 4. Facts, never recommendations (Deliverables 8, 10, 11)

The catalogue records where software installs, what its executable is
called, and what process it runs as. `category="ai"` is a **grouping for
the Dashboard**, not a judgement — nothing in `desktop/` reads it to make
a choice.

Enforced, not promised. `tests/test_desktop_executive.py` parses the whole
package for provider vocabulary (`openrouter`, `gemini`, `gpt-`,
`benchmark`, `model cost`, `quality score`, `ranked`, …) and fails on any
hit. Two near-misses are pinned by their own tests rather than waved
through:

- **"Anthropic" appears once**, as `%LOCALAPPDATA%\AnthropicClaude\...` —
  a fact about where a file lives, not knowledge of an API. A test asserts
  it only ever appears inside an install path.
- **"recommended" exists** for Deliverable 4's *Missing Recommended
  Applications*, and a test asserts **no AI application is ever marked
  recommended.** The moment one were, this Executive would be
  recommending intelligence, which is the Broker's job.

`observations()` returns statements in the present tense — *"Ollama not
installed."* A parameterised test asserts the word "recommend",
"consider", "should", or "better" never appears in one.

## 5. Three real defects, found by running it against a real machine

The fake probe cannot find these. Running a scan on the founder's actual
Windows machine did:

1. **Error text was being presented as a version.** `code --version` fails
   on the VS Code shim and `powershell --version` is a parse error, and
   the first draft fell back to "whatever was printed" — so the inventory
   showed `not found: code` and `At line:1 char:3` **in the version
   column**. `extract_version` now returns `None` when it cannot parse a
   version, because a version it cannot read is not a version.
2. **UTF-16 output rendered as `W S L   v e r s i o n :   2 . 7 . 3 . 0`.**
   `wsl --version` emits UTF-16LE, which text-mode `subprocess` decodes as
   cp1252. `repair_wide_text` detects that exact alternation and undoes
   it; WSL now reads `2.7.3`.
3. **A multi-line parser error filled an inventory row.** Details are now
   one line, bounded.

A fourth judgement came out of the same run: a tool that answers but
unparseably stays `healthy=True`. "We could not parse the version" is a
different fact from "this is broken", and a founder who sees a red mark
beside a working tool learns to ignore red marks.

## 6. The Dashboard (Deliverables 4, 9)

```
MACHINE READINESS  (12 installed)
  + Python       Ready
  + Git          Ready
  + Node.js      Ready
  + Docker       Ready
  + Ollama       Ready
  + VS Code      Ready
  + Chrome       Ready  found at a known install path; not on PATH
  Running        Claude Desktop, Edge, Ollama, PowerShell, Python
  AI software    Ollama
```

Captured from a real run. **The Dashboard never scans.** The inventory is
*handed in* by the launcher — ADR-0016 Decision 5, the same rule that
keeps `recover()` out of the Dashboard. A render that scanned the machine
would mean looking at the screen changes what the screen reports.

And the scan itself goes through Mission Control, as Rule 4 requires: the
launcher **submits a scan objective**, and the Runtime executes it on its
first cycle like any other work. Both scan capabilities are `READ_ONLY`,
so a founder is never asked for permission just to let the system look at
their own machine. `--no-scan` turns it off.

## 7. Deliberately not built (Deliverable 7)

No click, no type, no mouse, no OCR, no vision, no keyboard automation. A
test asserts none of those words appears in any capability name.

`BringToFront` and `FocusWindow` are registered because the brief names
them, and they **report honestly that window focus is not built** rather
than silently doing nothing — a capability that quietly no-ops is worse
than one that says it is not there.

## 8. Verification

**228 new tests, 1367 passing, 1 skipped, zero regressions** (1139
before). The brief asked for 100. Ruff clean across everything touched.

Covering discovery, registration, launch, close, running detection,
dashboard, Mission Control, persistence, restart, and cross-platform
safety — the platform-specific paths (`taskkill` vs `kill`, `cmd /c start`
vs `open` vs `xdg-open`) are each asserted on a fake probe pinned to that
platform, so Windows behaviour is tested on Linux and vice versa.

Live, all of the Definition of Done: `kalpavriksha` shows **Desktop
Ready**, Machine Readiness with 12 installed, running applications, and AI
software found — and "Build the Desktop Executive" has **disappeared from
the recommendations**, because MB029's live-state filter noticed it now
exists.

## 9. Technical Debt and Known Limitations (Rule 10)

1. **The catalogue is hand-maintained.** Nineteen applications, each a
   transcription of where that software installs. Adding one is one entry;
   keeping paths correct as vendors move them is ongoing.
2. **Windows install paths are the best-covered.** POSIX entries exist but
   have had far less real exposure — this was developed and run on
   Windows.
3. **No registry or package-manager reading.** Discovery is PATH plus
   known paths. An application installed somewhere unusual reads as
   missing.
4. **`unavailable` is defined but never produced.** The state exists (a
   thing present but not usable) and the Dashboard renders it; nothing
   currently detects that condition — a Docker daemon that is installed
   but dead still reads as Ready.
5. **Window focus is unimplemented by design**, and reports so.
6. **The scan runs once at launch.** Install something while Kalpavriksha
   is running and the panel is stale until the next launch or a dispatched
   scan.
7. **Process attribution is by executable name**, so two applications
   sharing one (several things run `python.exe`) attribute to whichever
   the catalogue lists.
