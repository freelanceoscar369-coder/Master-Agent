# Desktop Reasoning Provider — Dependency Impact & Launch-Sequence Safety Audit

**Architecture impact audit only. Nothing was implemented, modified, or committed.** Every claim below is traced to real source in this repository (`D:\MasterAgent`), file:line cited. Two read-only research passes (boot sequence; provider registry/routing) plus direct reading of `broker/`, `ai_infrastructure/`, and the relevant ADR were used to ground this — no code was written, no test was run, no application was launched, no Gemini/API quota was consumed.

## Headline finding, stated up front

This is not a hypothetical fit. **`ai_infrastructure/catalog.py`'s `PROVIDER_CATALOG` already contains a complete, real `ProviderSpec` for `"claude-desktop"`** (lines 138–157): `locality=DESKTOP`, `inventory_key="claude_desktop"` — the exact key this session's own Desktop Executive discovery layer already resolves live — `declared_quality=0.90`, `cost_per_call=0.0`, `latency_ms=3000.0`. The architecture did not merely permit a desktop reasoning provider; **it already modeled Claude Desktop as one.** The only thing standing between that spec and a working provider is: (1) a `ModelProvider` implementation whose `complete()` calls the Desktop Executive instead of raising, (2) wiring `ProviderSource`'s `inventory_provider` (currently `None`, `kalpavriksha_desktop.py:271`) to the real, already-built Desktop Executive inventory, and (3) registering that provider — the exact same three-step pattern `GeminiProvider` already follows.

---

## 1. Actual launch sequence (traced from the real entry point)

Entry point: `kalpavriksha_desktop.py:513` `main()`. Confirmed this is the real Founder Edition executable path (`master_agent.launcher` is a separate, unused-here composition).

| # | Stage | File:line | What it does | Depends on | Blocking? | Failure mode |
|---|---|---|---|---|---|---|
| 1 | Arg parsing / logging | `kalpavriksha_desktop.py:514-518` | `argparse`, `logging.basicConfig` | — | Trivial, sync | Fatal only on malformed argv (argparse exits) |
| 2 | `_build_mission_pipeline()` | `kalpavriksha_desktop.py:129-314`, called `:523` | Builds the whole mission/reasoning stack **before any window exists** | `GEMINI_API_KEY` env var | Sync, in-process, **zero I/O** | **DEGRADED, not fatal** — see 2a |
| 2a | — no `GEMINI_API_KEY` | `:154-156` | Returns `None` immediately; nothing downstream is built | — | — | App still boots; conversation-only, no mission execution |
| 2b | `PermissionSystem`, `LocalExecutor`, `PluginRegistry` | `:205-207` | Pure object construction | — | Sync | — |
| 2c | `BrowserPlugin` | `:220-224` | `BrowserSessionManager.__init__` only stores config; `_playwright`/`_browser` stay `None` until `_ensure_browser()` on first real capability call (`environment/browser_session.py:131-151`) | — | Sync, **no browser launched** | — |
| 2d | `DesktopPlugin` | `:236` | Builds `DesktopContext(RealSystemProbe())`, registers Action objects (`desktop/plugin.py:79-94`) | — | Sync, **no external process spawned** | — |
| 2e | `MissionControl` + `discover_executives` | `:239-240` | In-process registry wiring | — | Sync | — |
| 2f | `RuntimeEngine` + gateways | `:260-265` | In-process object graph | — | Sync | — |
| 2g | `ProviderSource`, `DecisionLedger(store=None)`, `CapabilityBroker`, `AiCapabilityService` | `:270-277` | Pure construction, no persistence backend touched | — | Sync | — |
| 2h | `GeminiProvider(api_key=api_key)` | `:279`, `providers/gemini.py:104-127` | **Only assigns fields.** No network call, no key validation | — | Sync | — |
| 2i | `PromptExecutor`, `Planner`, `MissionService` | `:280-303` | In-process construction | — | Sync | — |
| 3 | `create_window(...)` | `kalpavriksha_desktop.py:545-556` → `founder_edition/desktop_shell.py:528-600` | Founder Edition GUI shell | Stage 2's three callables (may be `None`) | — | — |
| 3a | `boot_founder_edition(...)` | `desktop_shell.py:559-561` | **Runs the entire named `founder_edition.boot` sequence synchronously, before the window is shown** | — | **Blocking** | See §Boot sub-steps below |
| 3b | `webview.create_window(...)` | `:563-569` | Native window object created (not yet shown) | — | Sync | — |
| 3c | `_build_voice(...)` | `:571-576` | Constructs `VoicePipeline` — construction never fails, never loads models | — | Sync, cheap | — |
| 3d | `window.events.shown += _on_shown` | `:589-596` | Registers voice start on the `shown` event | — | — | — |
| 3e | `webview.start(...)` | `:599` | **The actual blocking call** — shows window, runs native GUI event loop | — | Blocking (this is the "ready" moment) | — |
| 4 | `voice.start()` (fired from `shown`, i.e. **after** the window is already visible) | `voice_pipeline.py:305-307` | `threading.Thread(target=self._load_and_open, daemon=True).start()` | Whisper/Piper model files | **Non-blocking — background thread** | Caught/logged, not fatal; mic reports unavailable-then-armed |

### Boot sub-steps (`founder_edition.boot.boot_founder_edition`, `boot.py`)

Confirmed **used by the real entry point** (`desktop_shell.py:88,559`) — not legacy. `STEP_NAMES` (`boot.py:153-168`): `runtime → presence → environment_intelligence → desktop_executive → desktop_perception → desktop_operator → connect_founder_runtime → conversation → founder_identity → conversation_engine → communication → dashboard → render_founder_surface → ready`.

- **Fatal steps** (abort the whole boot to a bare, functionally-dead app): `runtime` (`:462-467`), `conversation` (`:579-584`), `connect_founder_runtime` (`:588-606`).
- **Degraded-on-failure steps** (caught, `UNAVAILABLE`, boot continues): `presence`, `environment_intelligence`, `desktop_executive`, `desktop_perception`, `desktop_operator`, `founder_identity`, `conversation_engine`, `communication`, `dashboard`.
- All steps are synchronous and in-process. **None imports or touches `broker/`, `planner/`, or any provider module** — confirmed via `test_founder_edition_boot.py::TestNothingExecutesOrCallsAI`, referenced at `desktop_shell.py:305`/`boot.py:86`, and via grep: nothing in `founder_edition/` imports `master_agent.broker`, `master_agent.planner`, or `master_agent.providers`.

**Conclusion: reasoning-provider construction (stage 2) and Founder-layer boot (stage 3a) are two entirely separate, non-overlapping code paths. Neither imports the other.** A reasoning provider's construction cost, however it is implemented, cannot block Founder Surface boot — the two run in different, non-communicating stages of `main()`.

---

## 2. Actual current reasoning-provider architecture

```
Founder input
  → DesktopShellApi.send_message (desktop_shell.py)
  → _submit_objective() (kalpavriksha_desktop.py:317-391)
  → MissionService.start() (missions/service.py)
  → Planner.plan() (planner/planner.py)
  → PromptExecutor.run() (ai_infrastructure/execution.py:298-304)
  → AiCapabilityService.decide() → CapabilityBroker.select() (broker/broker.py:147-198)
  → provider_registry.get(winner.provider_id) (plugins/registry.py)
  → GeminiProvider.complete() (providers/gemini.py:171-257)   ← the ONLY network call in this entire chain
  → PromptOutcome → Planner → MissionService → MissionControl/RuntimeEngine executes the plan
  → result → Founder Surface
```

- **Registration**: eager, once, synchronous, at `kalpavriksha_desktop.py:279` — `provider_registry.register(GeminiProvider(api_key=api_key))`. `PluginRegistry.register()` (`plugins/registry.py:19-25`) is pure dict bookkeeping — no I/O.
- **Availability checking**: two non-overlapping, both network-free concepts. `ProviderSource.profiles()` (`ai_infrastructure/profiles.py:147-175`) is a static config check (is a key configured / is the provider enabled). `CapabilityBroker.select()` (`broker.py:147-230`) is pure in-memory filter→floor→rank over `ProviderProfile` data. **Neither ever calls a provider to check if it's "up."**
- **Credentials**: checked as string-presence only, at pipeline-construction time (`kalpavriksha_desktop.py:154-156`) — never validated over the network.
- **Provider construction network calls**: none. `GeminiProvider.__init__` only stores fields; `UrllibTransport()` opens no socket at construction.
- **Provider construction process launches**: none, for any currently-registered provider.
- **Provider failure preventing boot**: no — construction never contacts the network, so a bad/missing key or an exhausted quota is invisible at boot and only surfaces per-objective.
- **Provider failure preventing normal conversation**: no — `DesktopShellApi.send_message` checks `self._app.communication is None` independently of the mission pipeline; conversation and mission-execution are separate subsystems (confirmed: `founder_edition/` never imports `broker`/`planner`/`providers`).
- **Provider failure preventing Desktop Executive operation**: no — `DesktopPlugin`/`RuntimeEngine`/`MissionControl` are constructed and gateway-registered (`kalpavriksha_desktop.py:236,265`) independently of whether any reasoning provider is registered or working. A Desktop capability invoked directly (bypassing the Planner) is unaffected by Gemini's state — proven live, repeatedly, this session, including the exact window the Gemini quota was exhausted.
- **Failure isolation, traced precisely**: a Gemini 429 is never a Python exception past `GeminiProvider.complete()` itself — it is caught inside `complete()` (`gemini.py:216-250`), converted to `ProviderResult(ok=False, ...)` as **data**, threaded through `PromptExecutor` (`execution.py:298-314`, whose `try/except` explicitly documents that a raise reaching it "is a defect in *our* code") → `Planner._rejected()` (`planner.py:226-243`, `PlanRefusal(code=PROVIDER_FAILED, ...)`) → `MissionService.start()` → `kalpavriksha_desktop.py:411-439` `_founder_refusal_sentence()`, which pattern-matches `"http 429"` against `_BUSY_MARKERS` and returns exactly *"My reasoning service is temporarily busy. Please try again in a moment."* — **confirmed live this session**, verbatim, when the real Gemini quota was actually exhausted mid-mission.

---

## 3. Hypothetical desktop reasoning provider — dependency graph and phase placement

For ChatGPT Desktop / Perplexity / Claude Desktop / Kimi, modeled as a `ModelProvider` (matching `GeminiProvider`'s/the existing stub `ChatGPTProvider`'s shape — `plugins/providers/chatgpt_provider.py:14-42`, whose own comment states: *"Real client construction deferred until this stub is wired up — kept out so importing this module never requires network/credentials"*):

| Operation | A: Boot | B: Registration | C: Selection | D: Execution |
|---|---|---|---|---|
| Application discovery | — | — | ✅ (read-only, from a cached scan) | — |
| Application launch | ❌ | ❌ | ❌ | ✅ only |
| Process/window detection | ❌ | ❌ | — | ✅ only |
| UIA discovery | ❌ | ❌ | ❌ | ✅ only |
| Composer targeting | ❌ | ❌ | ❌ | ✅ only |
| Prompt submission | ❌ | ❌ | ❌ | ✅ only |
| Response observation/verification | ❌ | ❌ | ❌ | ✅ only |
| Termination/cleanup | ❌ | ❌ | ❌ | Optional, at D's end |

This is not an aspiration — it is the **existing, working pattern**, already proven twice this session: `GeminiProvider` does zero work at construction/registration and all work inside `complete()`; `BrowserSessionManager` does zero work at construction and launches Chrome only inside `_ensure_browser()`, called from an actual navigate/session capability. A desktop reasoning provider's `complete()` would call the Desktop Executive's own already-built, already-verified chain (`launch_application → focus_window → find_target/desktop_type_text → desktop_press_key → read_text`) — the exact chain proven live against Claude Desktop and ChatGPT Desktop in this session's prior missions.

**Availability (Column C) is answered by `ProviderSource`'s already-built, already-declared machinery** (`ai_infrastructure/profiles.py:13-45`), which reads a **cached** machine scan, never a live probe: `NOT_SCANNED` / `NOT_INSTALLED` / `NOT_HEALTHY` / `INSTALLED`. This is precisely "is a matching application installed and healthy," derived from data already sitting in `desktop_plugin._context.cached` (built by this session's Universal Windows Environment Discovery work) — **not** a UIA probe, not a launch, not a window search. Discovery in column C is a **read of a cache**, never a scan.

---

## 4. Domino-effect scenarios — traced, not assumed

| # | Scenario | Boots? | Evidence |
|---|---|---|---|
| 1 | ChatGPT Desktop not installed | **Yes** | Availability is a cached-scan read (`NOT_INSTALLED`); nothing about "not installed" touches boot at all — the Broker simply excludes it from ranking (`broker.py:251-305`) |
| 2 | Installed but not running | **Yes** | Same — `ProviderSource` never checks "running," only "installed and healthy" per the last scan; running status is only consulted inside `complete()` at D |
| 3 | Running but inaccessible | **Yes** | Boot doesn't touch it at all; only a selected-and-attempted call at D would discover this, and per §2's failure-isolation trace, that failure becomes structured data, not an exception |
| 4 | ChatGPT Desktop hangs during launch | **Yes, boot is unaffected** | Launch only happens inside a provider's `complete()`, called from `PromptExecutor.run()`, itself only reachable from a founder-submitted objective — architecturally impossible to reach during `main()`'s boot stages (2) or (3), which are traced above and contain zero calls into `PromptExecutor`/`Planner`. A hang here would need its own bounded timeout inside `complete()`, exactly as `GeminiProvider.complete()` already bounds its own network calls (`DEFAULT_MAX_ATTEMPTS`, `gemini.py`) — a requirement for D's implementation, not a boot concern |
| 5 | UIA discovery hangs | **Yes, boot is unaffected** | Same reasoning as #4 — UIA discovery is a D-phase operation only, reachable exclusively through a submitted objective's execution, never boot |
| 6 | Desktop reasoning provider fails during a mission | **Failure stays inside the provider boundary** | `PromptExecutor.run()`'s `try/except BaseException` (`execution.py:305-314`) is the outer catch even for a defect in a provider's `complete()`; a well-behaved provider (following `GeminiProvider`'s contract of "never raise for an operational failure") returns `ProviderResult(ok=False, ...)` as data, which flows the identical path already traced in §2 to a founder-facing sentence |
| 7 | Gemini exhausted/unavailable | **Router can select a desktop provider without touching boot** | `CapabilityBroker.select()` operates over `list[ProviderProfile]` generically (`broker.py:147-198`) — no Gemini-specific code path exists; ranking/selection happens per-request, at C, long after boot has completed |
| 8 | No reasoning provider available at all | **Kalpavriksha stays alive, presents a recoverable state** | `CapabilityBroker._decide()` (`:219-230`) has an explicit `NO_PROVIDER_AVAILABLE` branch; `AiCapabilityService.decide()` never raises (`service.py:241-244`); `PromptExecutor.run()` returns a clean refusal (`:221-226`) before touching any provider. Confirmed identical to the already-shipped, already-proven zero-key path (§1, stage 2a) |
| 9 | Desktop Executive itself fails | **Yes, Founder Surface still starts** | `desktop_executive`/`desktop_perception`/`desktop_operator` are explicitly **degraded-on-failure** boot steps (`boot.py:519-575`) — caught, marked `UNAVAILABLE`, boot continues to `ready` |
| 10 | Voice subsystem fails | **Yes, desktop reasoning is architecturally independent of voice** | Voice construction never fails by design (`desktop_shell.py:571-576` docstring); voice only ever *submits text* through the same `submit_objective` function a founder's typed input already uses (`kalpavriksha_desktop.py:529-531`) — it is a second caller of the same seam, not a dependency of it |

---

## 5. Provider registry assumptions

None of the assumptions the audit asked to check for exist. Traced explicitly: registration is eager-but-conditional (gated only on `GEMINI_API_KEY` presence, `:154-156`), cheap, and network-free — but nothing downstream *requires* this to be true. `AiCapabilityService`, `CapabilityBroker`, and `PromptExecutor` are built around providers being **absent or down as a normal state**:
- `CapabilityBroker._decide()`'s `NO_PROVIDER_AVAILABLE` path (`broker.py:219-230`).
- `PromptExecutor._locate()` (`execution.py:401-416`) handles a Broker decision naming a `provider_id` with no matching registered plugin (`NO_PLUGIN`) — a wiring-vs-decision mismatch that itself returns cleanly, not a crash.
- `ProviderSource._inventory()` (`profiles.py:98-107`) treats a scan-read exception as "no scan," never propagating.

**A desktop provider can be represented as a lazy capability without violating anything frozen** — it would simply be one more entry in this already-provider-count-agnostic machinery, following the exact shape `claude-desktop`'s `ProviderSpec` already declares.

---

## 6. Routing architecture

**Yes — the router can already choose a desktop provider only when required, without probing or starting the application during boot**, and the seam is exact: `ProviderSource`'s cached-scan-only availability model (§3) means "is ChatGPT Desktop available" is answered by reading `desktop_plugin._context.cached` — a value populated once, lazily, by the Desktop Executive's existing discovery (never by the router). No architectural change to the routing/ranking layer itself is required — `CapabilityBroker`/`policy.py` already rank across `DESKTOP`-locality candidates generically (`_LOCALITY_ORDER = {LOCAL: 0, DESKTOP: 1, CLOUD: 2}`, `policy.py:52`; `PREFER_LOCAL`'s own description: *"on this machine first, then installed applications, then cloud"*, `policy.py:154-160`).

**The one real gap**: `ProviderSource(inventory_provider=None, ...)` at `kalpavriksha_desktop.py:271` — the cached-scan callable is never wired to the real Desktop Executive today. This is a **one-line composition-root change** (`inventory_provider=lambda: desktop_plugin._context.cached`), not a routing redesign.

---

## 7. Desktop Executive boundary

**The current ownership boundary is already correct** for discover/launch/focus/find-target/type/submit/observe/verify — this session's prior four missions built and proved exactly this chain, entirely inside `desktop/` and reachable only via `DesktopPlugin`'s registered capabilities, never via any other module reaching directly into `desktop/execution/`.

A desktop reasoning provider would be:

```
Reasoning Provider (new ModelProvider.complete())
        ↓
Desktop Executive (existing: DesktopExecutor / actions_interaction.py)
        ↓
Target Application (ChatGPT/Claude/Perplexity/Kimi)
```

**The circular structure is explicitly ruled out**, and not merely by intent — by absence of the wiring that would create it. `grep` across `desktop/`, `executor/`, `mission_control/`, `runtime/` for `MissionService`, `Planner(`, `mission_service.start`, `planner.plan(` returns **zero matches** outside `missions/service.py` itself and the unrelated `launcher/boot.py`. **No Desktop Executive Action, and nothing reachable during a Task's execution, holds a reference to the Planner or `MissionService`.** A `ModelProvider.complete()` implementation calling into the Desktop Executive would be a strictly one-directional dependency — the same direction `PromptExecutor` already calls `GeminiProvider.complete()` — never the reverse.

---

## 8. Recursive reasoning / planner loops

**No boundary needs to be newly built — one already exists structurally, for two independent reasons:**

1. **No code path exists for anything inside a Task's execution to re-enter the Planner.** As traced in §7, zero references to `MissionService`/`Planner.plan(` exist anywhere in `desktop/`, `executor/`, `mission_control/`, or `runtime/`. The only caller of `MissionService.start()` in the entire codebase is the founder-facing composition root (`kalpavriksha_desktop.py`'s `_submit_objective`, itself only invoked by a human's typed/spoken input or the voice bridge). Even if a desktop AI application's response text contained something that *looked* like a request, nothing in the current architecture reads a provider's response and feeds it back into `mission_service.start()` — `PromptOutcome`/`ProviderResult` flow strictly toward the founder, never back toward the Planner.
2. **ADR-0017 Decision 4 independently, deliberately rules this out at the design level**: *"no model call is made to make a [provider selection] decision... A Broker that asked an AI which AI to use would need an AI to make that choice; this design never starts the recursion."* Provider *selection* is frozen, deterministic policy over data (`broker/policy.py`) — it cannot itself become a reasoning loop, by ADR, not merely by the current absence of wiring.

**Both properties must be preserved by any implementation**: a desktop provider's `complete()` must return the target application's response as inert text to the caller (exactly what `GeminiProvider.complete()` already does) and must never itself construct or submit a new `Objective`.

---

## 9. Lifecycle ownership

**Model A — Kalpavriksha launches the application only when selected — is the only model compatible with the existing architecture**, and it is already the established pattern: `BrowserSessionManager._ensure_browser()` launches Chrome lazily on first real navigation, never at construction (`environment/browser_session.py:131-151`); `VerifiedLaunchApplicationAction` (this session's own work) launches applications only when a capability actually dispatches it.

**Model B** (require it already running) is inconsistent with §4 Scenario 2's traced behavior (installed-but-not-running is a normal, boot-safe state) and would make the provider needlessly fragile — the Desktop Executive's own launch-or-reuse logic (`VerifiedLaunchApplicationAction`, proven live) already handles "launch if needed, reuse if already open" correctly, so Model B would be strictly worse with no compensating benefit.

**Model C (launch during startup) must be treated as unsafe, per the audit's own instruction, and nothing in the frozen architecture requires it.** Confirmed: zero references to any provider, `broker/`, or application-launch code exist inside the entire `founder_edition.boot` sequence (§1). Adopting Model C would be a **new, unjustified** coupling this audit finds no basis for in current code or ratified design.

---

## 10. Shutdown/restart implications

Not directly traced in code (no existing desktop-provider lifecycle to trace), but derivable from the traced architecture with confidence:

- **Kalpavriksha restarts, application remains open**: safe under Model A — the next `complete()` call would launch-or-reuse exactly as `VerifiedLaunchApplicationAction` already does; no persistent handle is held across restarts because nothing is held at all outside of a single `complete()` call's scope.
- **Application crashes**: surfaces at D (execution time) as a structured provider failure, isolated per §2/§4 Scenario 6 — never a Kalpavriksha crash.
- **Application updates**: a version change is transparent to the launch-target mechanism (`shell:AppsFolder\<AppUserModelID>` resolution, already proven to survive real version differences this session) — no coupling.
- **Windows restarts**: no persistent process ownership exists under Model A (nothing is kept running by Kalpavriksha between calls), so there is nothing to reconcile on Windows restart.
- **Multiple Kalpavriksha instances**: each instance's `DesktopExecutor` would independently discover/launch/focus the same real OS-level application — this is an existing, general multi-instance-desktop-automation concern already inherent to the Desktop Executive today (not new to reasoning-provider integration), and out of this audit's scope to resolve.

**No desktop reasoning integration under Model A introduces persistent process ownership or shutdown coupling** — the provider never holds a handle across calls; every `complete()` invocation is self-contained, matching `GeminiProvider`'s own stateless-per-call shape.

---

## 11. Credential/API independence

**Confirmed, by direct trace, that this generalizes cleanly**: `CapabilityBroker.select()` and `PromptExecutor.run()` are provider-identity-agnostic (§2, §6) — "ChatGPT Desktop unavailable" would flow through the identical `NO_PROVIDER_AVAILABLE`/ranking-exclusion machinery already proven this session for "Gemini quota exhausted." The router does not need new code to "try the next one" — ranking across all `available=True` candidates already produces this behavior for free. **Kalpavriksha remaining operational when a desktop provider is unavailable is not an assumption — it is the same, already-exercised code path traced live in §2's failure-isolation walkthrough.**

---

## 12. Dependency graphs

**Actual, current boot:**
```
Kalpavriksha Boot (main())
├── _build_mission_pipeline()          [stage 2 — conditional on GEMINI_API_KEY]
│   ├── PermissionSystem / LocalExecutor / PluginRegistry
│   ├── BrowserPlugin  (no browser launched)
│   ├── DesktopPlugin  (no process launched)
│   ├── MissionControl / RuntimeEngine
│   └── ProviderSource → CapabilityBroker → AiCapabilityService
│       └── provider_registry: [GeminiProvider]   ← only one registered today
└── create_window()                     [stage 3 — always runs, independent of stage 2's outcome]
    └── boot_founder_edition()          [stage 3a — never imports broker/planner/providers]
        ├── environment_intelligence, desktop_executive, desktop_perception, desktop_operator
        ├── conversation, connect_founder_runtime, conversation_engine, communication
        └── dashboard → ready
```

**Proposed safe architecture (additive only, nothing frozen changed):**
```
                    Kalpavriksha Core/Boot
                    (stages 2 and 3 unchanged, unmodified)
                               │
                    Reasoning Router (CapabilityBroker — unmodified)
                            │       │
                       API provider │
                            │       │
                    ┌───────▼──┐    │
                    │ Gemini    │    │
                    └───────────┘    │
                                     │
                          ┌──────────▼──────────┐
                          │  Desktop Reasoning   │   NEW: ModelProvider impl,
                          │      Provider        │   complete() only — same
                          └──────────┬───────────┘   shape as GeminiProvider
                                     │
                          ┌──────────▼──────────┐
                          │  Desktop Executive   │   EXISTING, unmodified —
                          │ (this session's work)│   launch/focus/find_target/
                          └──────────┬───────────┘   type/press_key/read_text
                                     │
                       ┌─────────────┼─────────────┬─────────────┐
                       ▼             ▼             ▼             ▼
                   ChatGPT       Perplexity      Claude          Kimi
```

**The critical property holds, traced not assumed: desktop reasoning is a consumer of the Desktop Executive (via a new `ModelProvider`), and a consumer of the Reasoning Router (via `ProviderSource`/`CapabilityBroker`, both provider-count-agnostic) — never a dependency of Kalpavriksha boot.** Boot stages 2 and 3 (§1) contain zero references to any provider's execution logic.

---

## 13. Frozen architecture compliance

| Rule / ADR | Affected? | Why | Required exception? |
|---|---|---|---|
| ADR-0017 (AI Capability Broker: "decides, never touches the machine") | **No** | A desktop `ModelProvider`'s `complete()` calling the Desktop Executive is the provider touching the machine, not the Broker — the Broker only ever sees `ProviderProfile` data | None |
| ADR-0017 Decision 2 ("creates no new execution path") | **No** | Execution flows through the existing Capability Registry/Operator dispatch (Desktop Executive's own actions), exactly as Browser does today | None |
| ADR-0017 Decision 4 (no AI call to select a provider) | **No** | Desktop provider *selection* stays inside the existing, unmodified, deterministic `CapabilityBroker`/`policy.py` | None |
| MB027's six-rung ladder (local → desktop app → free cloud → ...) | **No — already named** | The ladder already names "desktop app" as its own rung; this integration fills a slot the frozen design reserved, does not invent one | None |
| `broker/profiles.py`'s "handed facts, never goes looking" | **No** | `ProviderSource` reads a **cached** scan; no live probe is added to the Broker/routing layer | None |
| Founder Edition's `TestNothingExecutesOrCallsAI` boundary | **No** | Confirmed no import of `broker`/`planner`/`providers` anywhere in `founder_edition/`; a desktop provider lives entirely in `providers/`/`ai_infrastructure/` wiring, never in `founder_edition/` | None |
| Desktop Executive ownership (this session's own established boundary) | **No** | A `ModelProvider` calling the Desktop Executive's existing capabilities is exactly the consumer relationship already proven for the Planner itself | None |
| ADR-0009 (irreversible-grant rule) / Permission System | **Not modified, but relevant at implementation time** | A desktop provider sending founder data to a third-party application is the same class of event ADR-0017 Decision 7 already covers ("sending data tagged sensitive to any third-party Provider requires approval, including a free one") — `requires_approval` already exists as a `ProviderSpec`/`ProviderProfile` field | None — apply the existing field, don't invent new approval machinery |
| Founder Edition boot ordering | **No** | Traced exhaustively in §1: reasoning-provider construction and Founder-layer boot are non-overlapping code paths | None |

**No frozen rule is violated. No frozen rule requires an exception.**

---

# Final decision gate

## GREEN — SAFE TO IMPLEMENT

1. **Exact integration seam**: (a) a new `ModelProvider` subclass per desktop application (or one parameterized class), whose `__init__` stores only identity/config (matching `GeminiProvider.__init__`, `providers/gemini.py:104-127`) and whose `complete()` invokes the existing, proven Desktop Executive chain (`VerifiedLaunchApplicationAction` → `VerifiedFocusWindowAction`/`_focus_and_confirm` → `FindTargetAction`/`TypeIntoWindowAction` → `PressKeyAction` → `ReadWindowTextAction`) exactly as this session's live golden paths already did, entirely inside `complete()`, never at construction; (b) `kalpavriksha_desktop.py:271` — change `inventory_provider=None` to a real cached-inventory read (e.g. `lambda: desktop_plugin._context.cached`); (c) `kalpavriksha_desktop.py:279` — `provider_registry.register(...)` the new provider(s), following the exact line already there for Gemini.
2. **Lifecycle model**: Model A (launch-or-reuse only when selected and called) — already the Desktop Executive's own established behavior, requires no new lifecycle code.
3. **Failure isolation model**: the provider's `complete()` must never raise for an operational failure (unreachable, hung, target not found, unverifiable) — it must return a structured `ProviderResult(ok=False, ...)`, exactly `GeminiProvider`'s own contract, so the existing `PromptExecutor`/`Planner`/`_founder_refusal_sentence` chain (§2) handles it with zero new code.
4. **Routing model**: unchanged — `CapabilityBroker`/`policy.py` already rank `DESKTOP`-locality candidates generically; a founder policy like `prefer_local` already prefers them over cloud, and `claude-desktop`'s `ProviderSpec` is already declared in `PROVIDER_CATALOG`.
5. **Files/modules expected to change**: `providers/` (new provider implementation(s), additive); `kalpavriksha_desktop.py` (the two lines named in item 1); `ai_infrastructure/catalog.py` (add `ProviderSpec` entries for ChatGPT/Perplexity/Kimi alongside the already-existing `claude-desktop`, following the identical shape); `pyproject.toml`/`enabled_cloud_providers`-equivalent config if these are treated as opt-in. **Nothing in `broker/`, `mission_control/`, `runtime/`, `permissions/`, `desktop/`, or `founder_edition/` needs to change.**
6. **Tests required**: Level 1 — provider `complete()` unit tests against a faked Desktop Executive (mirroring this session's `test_desktop_uia.py` fake-object pattern); a regression test asserting `ProviderSource`/`CapabilityBroker` still return `NO_PROVIDER_AVAILABLE` cleanly when zero desktop apps are installed (extends existing coverage, doesn't replace it); an architecture guard mirroring `TestNothingExecutesOrCallsAI`'s pattern, asserting the new provider module never imports `missions.service`/`planner` (formalizing §8's finding as an enforced test, not just an audit observation). Level 3 — one live test per provider, reusing this session's already-proven golden-path evidence.
7. **Acceptance criteria**: application not installed → clean `NO_PROVIDER_AVAILABLE`/ranking exclusion, no boot impact (traced, §4#1-2); a hung launch/UIA probe cannot block `main()`'s boot stages (structurally impossible per §1's non-overlapping-code-paths finding, but the provider's own `complete()` must still bound its own waits, matching `GeminiProvider`'s `DEFAULT_MAX_ATTEMPTS` discipline); Gemini exhaustion routes to a desktop provider with zero boot-time change (§4#7); zero new frozen-rule exceptions (§13 table, confirmed empty).
