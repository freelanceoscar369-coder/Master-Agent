# Desktop Application Discovery 1.0 — Universal Windows Environment Discovery

Corrective mission response: the Desktop Executive's catalog was being
treated as the source of truth for what is installed, and it was wrong —
Claude Desktop, genuinely installed and running, was reported "missing"
because its hardcoded catalog path didn't match its real MSIX install
location. This work replaces that assumption: **the Windows machine is
the source of truth; the catalog enriches what Windows itself reports,
and can never override it.**

## 1. Discovery sources

| Source | Mechanism | Cost | Covers |
|---|---|---|---|
| Running processes | `tasklist /FO CSV /NH` (existing) | cheap, always run | any process, regardless of install method |
| Start Menu | `Get-StartApps` (**new**) | ~2-5s | traditional installers, MSIX/UWP, and PWAs alike, in one call — Windows' own "how would you actually launch this" answer |
| MSIX/AppX | `Get-AppxPackage` (existing, now gated correctly) | ~1-2s | packaged apps, including ones with no Start Menu tile |
| Registry uninstall keys | `Get-ItemProperty` over HKLM, HKLM\Wow6432Node, HKCU (existing, was silently broken — see §7) | ~2-4s per hive | traditional installers, including ones that never registered a Start Menu tile |
| Catalog PATH/known-path | `probe.which()` / `probe.exists()` (existing, unchanged) | cheap | developer tools, browsers — anything with a stable install location worth hand-declaring |

Every PowerShell-based source runs with `-NoProfile` (fixed this
session — the default shell was loading the user's interactive profile,
adding ~2s of pure overhead per call for nothing this needed).

## 2. Evidence precedence

Implemented in `inventory.py::_resolve_one()`, in this order:

1. **Start Menu** (`START_MENU`) — outranks bare MSIX enumeration
   deliberately: `Get-StartApps` is Windows' own vetted "this is
   launchable" answer, while `Get-AppxPackage` lists every installed
   *package*, including framework/runtime packages with no user-facing
   launch surface at all. This is a documented deviation from a literal
   reading of "MSIX above Start Menu" — it is stronger evidence, not
   weaker.
2. **MSIX/AppX** (`MSIX`)
3. **Catalog PATH/known-path** (`CATALOG_PATH`) — a verified, resolved
   executable is stronger evidence than a registry entry whose
   `UninstallString` exists to remove software, not launch it.
4. **Registry uninstall entry** (`REGISTRY`)
5. **Running process alone** (`RUNNING_PROCESS`) — when nothing static
   matches at all, a real running process is still enough to say
   "installed" (honestly, with no launch target) — this is the exact
   Claude Desktop case in the previous mission's testing, generalized.

A real running process is folded into `discovery_sources` at every tier
as corroborating evidence (`running=True`), never displacing a stronger
source's `launch_target`.

**Known, disclosed limitation:** the spec's own precedence list places
"running process *with a real path*" above MSIX. `tasklist`-based process
enumeration does not carry per-process executable paths — only `Get-
Process | Select Path` or a WMI/`Get-CimInstance Win32_Process` query
would, and both are materially more expensive to run on every scan.
`RUNNING_PROCESS` here therefore proves "installed and running," never a
launch path — the static sources above are what supply an actual launch
mechanism. This was a deliberate cost/correctness tradeoff, not an
oversight.

## 3. Normalized model

`InstalledApplication` (extended, not replaced — every existing field
keeps its meaning) gained: `aliases`, `executable_name`, `package_name`,
`package_family`, `app_user_model_id`, `publisher`, `install_source`,
`launch_target`, `discovery_sources`, `confidence`, `catalog_metadata_
present`, `running`. Every new field defaults to whatever a catalog-only,
pre-discovery caller already produced, so nothing reading `.status`/
`.version`/`.path`/`.launchable`/`.healthy`/`.detail`/`.version_args`
needed to change.

`launch_target` supersedes the previous session's ad-hoc convention of
smuggling a `shell:AppsFolder\...` command inside `version_args[0]` — a
dedicated field, generically resolved for every source, not a special
case for Store apps alone.

## 4. Merge and unknown-application discovery

For every `catalog.py` spec, `_resolve_one()` claims (and marks used) at
most one entry from each source list, trying them in precedence order.

For Section 6's core universality requirement — an application no
developer anticipated must still be discoverable — every Start Menu/
MSIX/registry entry left unclaimed by any catalog spec becomes an
`InstalledApplication` with `catalog_metadata_present=False`, key-prefixed
by its source (`start_menu:perplexity`, `msix:...`, `registry:...`), and
a real `launch_target` where one exists. These are **not** merged into
`MachineInventory.applications` — they live in a new, separate
`unknown_applications` list (queryable via `MachineInventory.get_unknown
(name)`), so every existing caller that iterates `.applications`
expecting catalog-known software (the Dashboard, `ai_applications()`,
`missing_recommended()`) is unaffected by however many unrelated Start
Menu tiles (MMC snap-ins, control panel items, help files — a real
machine's Start Menu has ~160 entries, most of them not "applications" in
any useful sense) a real machine happens to expose. A duplicate across
sources (the same real application appearing in both Start Menu and the
registry) is deduplicated by display name, keeping the strongest source's
launch target and merging `discovery_sources`.

## 5. Launch resolution

`DesktopExecutor.execute()` (`execution/executor.py`) resolves generically
from `installed_app.launch_target`: a `shell:AppsFolder\...` target is
launched as `["explorer.exe", launch_target]` (the one shape the existing,
frozen `LaunchApplicationAction` in `desktop/actions.py` cannot express —
it starts `[path]` as a single command). Every other case — a verified
exe path, or a raw path Start Menu itself reported for a legacy shortcut
— already *is* `installed_app.path`, so the existing, unmodified
profile-based fallback (`self.process.launch()`) already launches it
correctly.

**Disclosed gap:** `DesktopExecutor.execute()` still requires an
`ApplicationOperationProfile` (the pre-existing C25 gate — deliberately
preserved, never bypassed). Discovery alone makes an unknown application
*visible*; launching it through the real, permission-gated Desktop
Executive/Planner pipeline still needs an operation profile, which is
catalog knowledge this mission did not add for Perplexity/Kimi/Canva/
Obsidian (adding one per app would itself be the "per-app special case"
this mission's own instructions forbid building without being asked).
This session verified the discovery→launch *mechanism* directly (§8
below) rather than bypass or weaken that gate.

## 6. Cache strategy — fast path / deep path

`DesktopContext` (`desktop/actions.py`) tracks whether its cached
`MachineInventory` came from a deep scan (`_inventory_is_deep`).

- `inventory(deep=True)` (the default) is cache-first: the multi-source
  scan's real cost (~15-25s on a real developer machine) is paid once per
  process lifetime; every subsequent call is free until something asks
  for a scan the cache can't satisfy.
- `refresh(deep=False)` is the FAST PATH every verified interaction
  action's own "confirm the window/process still exists" check uses.
  **Found live, mid-session:** when a deep scan was already cached, a
  fast refresh was *discarding* it — `execute("chrome")` (deep scan,
  cached) → `focus()`'s own fast refresh → `execute("notepad")` re-paid
  the full ~25s scan, because the fast refresh had silently downgraded
  the cache. Fixed with `inventory.refresh_processes_only()`: when a deep
  cache exists, a fast refresh re-reads only the running-process
  snapshot (the one fact that genuinely changes between calls) and
  reapplies it to the *existing* Start Menu/MSIX/registry-derived
  records, instead of discarding them. Measured live: Chrome then
  Notepad launched back-to-back went from ~25s + ~25s to ~18s + ~4s.

## 7. Real bugs found and fixed this session

1. **`get_uninstall_apps()` was silently broken since it was written** —
   two independent bugs in its own PowerShell command: a missing opening
   quote (`-Path {path}*'`, unbalanced) that made the whole registry
   query a parser error every single call, and — after fixing that — a
   missing path separator (`Uninstall*'` instead of `Uninstall\*'`,
   matching zero child keys instead of every one). Both were masked by
   a blanket `except: pass` and the fact that the method's result was
   never read anywhere (see #2). Found live: querying the registry
   directly outside this codebase returned real results (Obsidian,
   Docker Desktop, ...); the codebase's own call returned nothing.
2. **`get_uninstall_apps()`'s result was computed and never used** — three
   real registry-query subprocesses spent on every inventory scan for a
   value nothing read. Removed the dead call in the prior session's perf
   fix; this session gives the method a real purpose (`REGISTRY` source).
3. **PowerShell profile loading cost ~2s per call for nothing** — none of
   `get_store_apps()`/`get_uninstall_apps()`/`get_start_apps()` need the
   user's interactive `$PROFILE`; added `-NoProfile` to all three.
4. **`_VERSION_PATTERN` was missing its middle group** — `\d+\.\d+(?:[-+]
   [\w.]+)?` truncated every three-component version ("2.43.0" → "2.43").
   Confirmed via `git log -p` that the committed baseline had `(?:\.\d+)?`
   and the working tree had silently lost it (unrelated to this
   mission — an accumulated regression from earlier uncommitted session
   work). Restored.
5. **`catalog.READINESS_KEYS` was missing entirely** — `dashboard/
   sources.py` imports it; the working tree's `catalog.py` no longer
   defined it (same class of accumulated regression as #4, confirmed via
   `git log -p`). Restored from the last known-good definition.
6. **The cache-downgrade bug described in §6.**

None of #4/#5 were introduced by this mission — both were discovered only
because this mission's own new tests exercise `discover()`/the Dashboard
path broadly enough to surface them. Fixed because they sat directly in
the file this mission was already responsible for and the correct fix was
git-verifiable, not because the mission's scope was expanded to chase
them.

## 8. Real-machine findings (this Windows machine, live)

Deep scan cost: ~15-25s (first call per process; free thereafter via the
cache).

| App | Installed | Running | Launchable | Source | Confidence | Path/Package |
|---|---|---|---|---|---|---|
| ChatGPT | **True** (was `missing`) | False | True | `start_menu` | high | `shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App` |
| Claude Desktop | **True** (was `missing`) | True | True | `start_menu` | high | `shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude` |
| Ollama | True | True | True | `start_menu` | high | `C:\Users\...\Programs\Ollama\ollama app.exe` (raw path, not shell:AppsFolder — see §9) |
| LM Studio | False | — | — | `none` | none | genuinely not installed on this machine |
| Cursor | False | — | — | `none` | none | genuinely not installed on this machine |
| Chrome | True | — | True | `start_menu` | high | `shell:AppsFolder\Chrome` |
| Edge | True | — | True | `start_menu` | high | `shell:AppsFolder\MSEdge` |
| Notepad | True | — | True | `start_menu` | high | `shell:AppsFolder\Microsoft.WindowsNotepad_...!App` |
| Perplexity *(unknown)* | True | — | True | `start_menu` + `msix` (two real installs) | high | `shell:AppsFolder\com.todesktop.25020447d4kq915` |
| Kimi *(unknown)* | True | — | True | `start_menu` | high | `shell:AppsFolder\com.moonshot.kimichat` |
| Canva *(unknown)* | True | — | True | `start_menu` | high | `shell:AppsFolder\com.canva.CanvaDesktop` |
| Obsidian *(unknown)* | True | — | True | `start_menu` | high | `shell:AppsFolder\md.obsidian` |

Perplexity, Kimi, Canva, and Obsidian have **zero `catalog.py` entries** —
every field above came from live discovery alone.

## 9. Real launch verification (this session, live)

- **Open Chrome** — PASS. Real window, foreground confirmed.
- **Open Notepad** — PASS. Real window, foreground confirmed.
- **Open ChatGPT** (through the real, profile-gated `DesktopExecutor`
  pipeline) — PASS after a real fix: the first attempt failed because
  `_LAUNCH_WAIT_TIMEOUT_SECONDS` (15s) was shorter than this app's actual
  cold-start time on this machine — confirmed live (the process was
  running and its window appeared, just after the action gave up).
  Raised to 30s; re-verified PASS with a real visible "ChatGPT" window,
  foreground confirmed.
- **Open Claude** (already running) — PASS. Real window, foreground
  confirmed.
- **Open Obsidian** (an unknown application — no catalog entry, no
  operation profile, tested via its resolved `launch_target` directly
  since the profile gate correctly refuses to dispatch through
  `DesktopExecutor` for an application it has no profile for) — PASS.
  Real process, real visible "Obsidian" window found within 5s.
- **Ollama** — not launched, per the explicit constraint; only its
  installed/running status was read.

Every window opened during this verification that was not already
running before it (ChatGPT, Obsidian) was closed afterward.

## 10. Ollama's raw-path AppID

`Get-StartApps` reported Ollama's `AppID` as a raw absolute path
(`C:\Users\...\ollama app.exe`), not an AppUserModelID — a real, observed
case of the exact ambiguity Section 7 anticipated. `_is_raw_path()`/
`_start_app_launch_target()` detect this (a leading drive letter) and
launch the path directly rather than attempting `shell:AppsFolder\<path>`,
which would not resolve.

## 11. Tests

22 new deterministic tests added to `tests/test_desktop_executive.py`
(the existing home for `discover()`/`FakeProbe`-based coverage), covering
every item in the corrective mission's own test list: running-process
discovery, Start Menu discovery (including the raw-path case), MSIX
discovery, registry discovery (merge-level and, separately, at the probe
level — asserting the actual HKLM/HKLM·Wow6432Node/HKCU query strings,
regression coverage for §7's bugs), evidence precedence and catalog-path-
conflict resolution, unknown-application discovery, a running process
with no catalog entry at all, launch-target resolution, both halves of
the cache behavior (fast-path skips every expensive source; a cached deep
scan is never re-run), and installed/running/visible state
distinguishability.

Seven other test files had their own independent `FakeProbe`/`Installed
Probe` fixtures that predate this mission and did not implement the
Protocol's newer `get_store_apps`/`get_uninstall_apps` methods (added in
the prior session) or the new `get_start_apps` (added this session); all
were updated to implement the full `SystemProbe` Protocol, which is what
they were always meant to mirror.

**Full desktop suite: 670 passed, 7 failed.** Every one of the 7 failures
was verified pre-existing and unrelated to this mission — three from an
earlier session's incomplete reconciliation between the Desktop
Interaction layer (real `click`/`type_text`/`bring_to_front`) and tests
still asserting MB030's original "no automation capability exists"/"12
capabilities" premises, two from Notepad's catalog entry (also added
earlier) never getting a matching recovery-plan entry, and two from a
real `GEMINI_API_KEY` present in this machine's actual environment
tripping tests that assume a clean one. None are within this mission's
scope (discovery, not interaction/recovery-plan/provider-wiring) to fix.

## 12. Remaining, disclosed limitations

- Full Planner integration for a *discovered-but-not-cataloged*
  application (Perplexity/Kimi/Canva/Obsidian) requires an operation
  profile per app, which this mission did not add (see §5).
- "Running process with a real path" (the spec's literal top precedence
  tier) is approximated as "running process, no path" — see §2's own
  disclosure.
- Unknown-application `running` status is a snapshot from the deep scan
  moment; the fast-path cache-refresh (§6) only re-derives `running` for
  catalog-known applications, since `attribute_processes()` itself only
  attributes by catalog `process_names`.
- A pre-existing, unrelated circular import (`master_agent.communication`
  ↔ `founder_edition.boot`, via a `founder_runtime/wiring.py` edge added
  in earlier, uncommitted session work) still blocks a few unrelated test
  files from collecting standalone — documented in the prior Desktop
  Executive Foundation audit, unchanged by this mission, out of scope per
  this mission's own DO-NOT-CHANGE list.
