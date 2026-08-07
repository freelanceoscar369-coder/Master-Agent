# Integration Diagram — C33 Desktop Alpha

Deliverable 9. What actually runs when a founder types `python app.py`,
traced against the real boot sequence and the real REPL — not the brief's
own aspirational UX flow, though every arrow below is a real arrow from
that flow, confirmed working end to end (`Engineering/HEALTH_C33.md` §4).

## Process boundary

```
┌──────────────────────────────────────────────────────────────────────┐
│  python app.py  (repo root, six-line shim → console.main)            │
│                                                                        │
│  boot_founder_edition(founder_name, text_output=ConsoleTextOutput())  │
│  ── every step below is one real object, constructed once ──          │
│                                                                        │
│   1  FounderRuntime()            door opens, unwired          [C23]  │
│   2  VigilanceAttestation        presence, honestly incomplete [C19]  │
│   3  discover() + derive_intelligence()   real machine scan    [C22]  │
│   4  ConversationMemory()        one turn history, Layer 1     [L1]   │
│   5  FounderRuntime(...)         connected: 3/3 sources wired  [C23]  │
│   6  FounderIdentity + FounderSession    "Somesh", for Onkar   [C29]  │
│   7  ConversationEngine(...)     answers, never plans          [C31]  │
│   8  CommunicationEngine(...)    channels: text (voice: none)  [C32]  │
│   9  DesktopExecutiveV2 + DesktopExecutor      knowledge+door  [C25/26]│
│  10  DesktopObserver()           read-only perception          [C27]  │
│  11  DesktopOperator(...)        wired and idle, never called  [C28]  │
│  12  founder_dashboard(...)      8 sections, composed          [C30]  │
│  13  render_founder_surface      out_of_scope (see note below)        │
│  14  ready                       True                                 │
│                                                                        │
│  → FounderEditionApp, held by console.run_repl()                     │
└──────────────────────────────────────────────────────────────────────┘
```

**Note on step 13:** the Founder Surface (C21) and the Presence Layer
(C20) it renders through are HyperAgent's TypeScript and are not part of
this Python repository — C24 drew this boundary and C33 does not move it
(`HEALTH_C33.md` §2). The terminal this process runs in is the desktop
window for this alpha; §2 of the health report argues why no other
wired surface exists to use instead.

## One founder turn, traced

```
 You: "Good morning Somesh"
   │
   ▼
 ConsoleTextInput.receive()                                    [console.py, C33]
   real clock read here — the one place in this process ambient time enters
   │  CommunicationRequest(source=TEXT, content=..., timestamp=..., conversation_id=...)
   ▼
 CommunicationEngine.handle(request)                                     [C32]
   │
   ▼
 CommunicationRouter.route(request)                                      [C32]
   │  not a mode-switch phrase → falls through to:
   ▼
 ConversationEngine.reply(text, moment)                                  [C31]
   │
   ├─ IntentClassifier.classify(text)         → Intent.GREETING          [C31]
   ├─ ContextAssembler.assemble(runtime, ...)  → ConversationContext      [C31]
   │     reads runtime.environment() / .conversation() / .presence()     [C23]
   │     — never mutates FounderRuntime; three read-only calls only
   ├─ ResponseComposer.greeting(identity, ctx) → calls C29's greet()      [C31→C29]
   └─ ConversationMemory.record("user", text)                            [L1]
       ConversationMemory.record("somesh", reply)                        [L1]
   │
   ▼  ConversationTurn(intent, reply, context)
 CommunicationRouter wraps it: RoutedResponse(response, mode=TEXT_ONLY,
                                               channels=("text",))
   │
   ▼
 CommunicationEngine._emit(routed)                                       [C32]
   │  "text" ∈ channels → self._text_output.emit(routed.response)
   ▼
 ConsoleTextOutput.emit(response)                               [console.py, C33]
   │  print(f"Somesh: {response.display}")
   ▼
 "Somesh: Good morning. I'm awake. Everything is ready."

 process_line() then calls app.dashboard() again:                        [C33]
   FounderRuntime.environment() / .conversation() / .presence()  — fresh reads
   DesktopLayer.readiness(moment)                                        [C30]
   format_dashboard(...)  → printed                              [console.py, C33]
```

**What is never on this path:** `FounderRuntime.handle()` (C23's one
mutable-shaped door — never called by `console.py`, AST-checked),
`DesktopOperator.execute()` (never called anywhere in this mission,
AST-checked), any `desktop.execution`/`desktop.perception` import inside
`conversation_engine/` or `communication/` (those packages cannot reach
the desktop at all — C31/C32's own boundary, unchanged by C33), any
audio/speech library (none exists in this codebase to import).

## Mode switching, and its one honest gap

```
 You: "switch to voice"
   │
   ▼
 CommunicationRouter.route()
   │  _requested_mode("switch to voice") → OutputMode.VOICE_ONLY
   │  self._mode = VOICE_ONLY   ◄── committed before the return
   ▼
 RoutedResponse(response="Switched to voice.", mode=VOICE_ONLY, channels=("voice",))
   │
   ▼
 CommunicationEngine._emit(routed)
   │  "voice" ∈ channels, but voice_output is None
   ▼
 raise ChannelNotRegistered           ◄── C32's own honest failure

 process_line() catches it:                                      [console.py, C33]
   print("[console] ... switching back to text.")
   app.communication.handle(CommunicationRequest("switch to text", ...))
   │  a REAL recognised phrase, routed the ordinary way — not a
   │  fabricated reply — restores self._mode = TEXT_ONLY
   ▼
 conversation continues normally
```

See `Engineering/HEALTH_C33.md` §5 for the full argument: this is a real
gap in C32 (mode commits before its channel is confirmed available),
worked around at the launcher layer because `communication/` is a
complete, audited-pending component this mission does not reopen.

## Package boundaries, unchanged by this integration

```
        founder_edition/  (composition root — C24, extended by C30, C33)
        ├── boot.py        imports: communication, conversation_engine,
        │                  desktop*, founder_identity, founder_runtime,
        │                  environment_intelligence, vigilance, memory
        ├── console.py      imports: communication, founder_edition.boot
        ├── dashboard.py    imports: communication? no — founder_identity,
        │                             founder_runtime, desktop_layer
        └── desktop_layer.py imports: desktop*, desktop_operator

        conversation_engine/   imports: founder_identity, founder_runtime, memory
                                — never desktop, never founder_edition   [C31, unchanged]

        communication/          imports: conversation_engine, memory
                                — never desktop, never founder_runtime,
                                  never founder_edition                  [C32, unchanged]
```

`conversation_engine/` and `communication/` still cannot reach the
desktop, the Kernel, or any execution surface — C33 adds a caller
(`founder_edition/boot.py`) above them; it adds nothing to what they can
reach. Every AST boundary guard from C31's and C32's own test suites
still passes unedited (`Engineering/HEALTH_C33.md` §6).
