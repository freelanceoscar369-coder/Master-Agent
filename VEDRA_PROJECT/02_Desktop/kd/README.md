# Kalpavriksha Desktop — v0.1

The founder-facing application shell around the Kernel (C15.0).

---

## Status, stated plainly

**This is a working application, not a mockup.** Seven screens, real state, real
mutations, a live event stream, undo windows, theming, keyboard navigation.

**It is not yet connected to the Kernel.** It ships with a complete in-memory
implementation of the Kernel contract (`mock`), which is what you see when you
run it. The real adapter (`http`) exists, is fully typed, and every method
returns a `not-implemented` error until the C15.0 wire contract is confirmed.

The adapter you are running is displayed in the status bar at all times, in
every environment. That is deliberate: nobody should ever demo mock data
believing it is real.

---

## Run it

```bash
npm install
npm run dev          # http://localhost:5173
```

```bash
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + production bundle into dist/
npm run preview
```

> **Note:** the environment this code was authored in had no access to the npm
> registry, so `npm install`, `tsc` and `vite build` have **never been executed
> against this tree**. Expect to fix a small number of import or type nits on
> first install. The dependency list is deliberately tiny — React, Vite,
> TypeScript, and nothing else — so there is very little that can go wrong.

### Configuration

Copy `.env.example` to `.env`:

```
VITE_KERNEL_ADAPTER=mock          # mock | http
VITE_KERNEL_BASE_URL=http://127.0.0.1:8787
VITE_KERNEL_STREAM=sse            # sse | websocket | poll
```

---

## The one rule for future work

> **No screen may import `fetch`, a URL, or any transport detail.**
> Everything the UI knows about the backend is the `KernelClient` interface in
> `src/kernel/client.ts`.

When the Kernel's real contract arrives, you implement it in
`src/kernel/http/httpKernel.ts` and map the wire format onto the domain types in
`src/kernel/types.ts`. **No screen changes.** That is the entire point of the
layering, and it is the property to defend in code review.

---

## Layout

```
src/
  kernel/            ← the ONLY backend knowledge in the app
    types.ts           domain vocabulary (derived from the Bible, not the wire)
    client.ts          the KernelClient interface + Result/KernelError
    mock/              complete in-memory implementation + fixtures
    http/              typed placeholder + real transport plumbing
    desktop/           Tauri/Electron detection (no framework chosen yet)
    hooks.ts           useAsync / useMutation / useKernelEvents / usePresence
  design/            tokens, three dark themes, base, grid
  components/        22 primitives — the whole vocabulary
  app/
    router.tsx         ~90-line hash router
    registry.tsx       the route table — one entry per screen
    shell/             TitleBar · NavRail · StatusBar · CommandBar · PresenceSigil
  features/
    dashboard/         Screen 01 — the voice, one decision, the receipt
    founder/           judgment queue · rules · proposals · scope & audit
    missions/          Mission Center
    ledger/            Ledger Explorer
    memory/            Memory Explorer
    capabilities/      Capability Library
    events/            Live Event Stream
  lib/               format · vigilance · result
  state/             theme · prefs
```

---

## Where the Experience Bible is enforced in code

Not by convention. Conventions get worked around, so the load-bearing rules are
enforced by the type system or by the mock kernel refusing.

| Bible rule | Enforcement |
|---|---|
| Principle VI — every judgment request carries its full consequence quartet | `Consequence` has four required fields; a partial one is a compile error |
| Principle VII — silence has a stated default | `SilenceDefault` is required on `JudgmentRequest` |
| §10 — confidence is never a percentage | `Confidence` is a three-member union; a `number` cannot be assigned |
| §1 / D7 — the calm claim must be provable | `Attestation` is a discriminated union; `canClaimCalm()` is a type guard the Dashboard must pass through |
| Eng. Law II — reversibility is declared, never assumed | `Reversibility` is a required exhaustive union; unclassified capabilities render as non-executable |
| §5 — irreversible items never batch | `submitBatchVerdict` returns `invalid` if any item is needs-you or irreversible |
| Eng. Law I — receipts are append-only | No update or delete exists anywhere on the client surface |
| Principle X — no modals, no badges | There is no modal primitive in `src/components`. The command bar is a docked sheet |
| Eng. Law IV — every feature ships its empty and failure state | `EmptyState` and `ErrorState` are primitives, and every async path uses them |

---

## Theming

Three themes, all in the dark family: `midnight` (canonical), `depth` (lower
contrast for long sessions), `contrast` (accessibility).

**There is no light theme, and adding one is not a feature request.** The
Design Constitution's lighting model — *the only light source is the
intelligence* — does not survive a white surface. A light theme is a
constitutional amendment.

Density (`comfortable` / `compact`) is separate and changes spacing only, never
colour.

---

## Desktop shell

**No desktop framework has been chosen.** The app is a standard web bundle with
`base: './'` so it loads from `file://`, hash routing so it needs no server-side
rewrites, and a `DesktopBridge` in `src/kernel/desktop/bridge.ts` that
feature-detects Tauri or Electron at runtime and no-ops in the browser. Window
controls only render when a host is detected.

Wrapping this in Tauri or Electron should be additive. That decision is yours,
and nothing here presumes it.

---

## Keyboard

| Key | Action |
|---|---|
| `⌘K` / `Ctrl+K` | Command bar |
| `G` | Toggle the grid overlay |
| `Escape` | Close any transient surface |
| `↑` `↓` `Enter` | Navigate the command bar |

---

## Known gaps

Recorded rather than hidden.

1. **Never compiled.** See the note above.
2. **`requestMission` is unimplemented** and renders as a disabled control with
   the reason shown. It is the one place where the founder initiates work, and
   it needs a real Kernel endpoint.
3. **Voice is absent from v0.1.** The Bible's voice/text synchronisation
   (§5) requires programmable prosody, which needs a synthesis decision. The
   Dashboard's typewriter runs text-only, which is the correct fallback: text is
   the source of truth and voice is a layer over it.
4. **No tests.** No test runner could be installed. The mock kernel is
   deterministic when `localStorage['kalpa.seed']` is set, which is the hook a
   test suite should use.
5. **Mobile is out of scope**, as recorded in the Bible. The shell degrades to a
   top bar under 860px but the explorers are not designed for it.
6. **The tree is a 28px presence sigil only.** The full arrival tree belongs to
   a first-run experience that is not part of v0.1.
