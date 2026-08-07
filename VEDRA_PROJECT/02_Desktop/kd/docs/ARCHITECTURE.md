# Architecture

How this frontend is put together, and the rules that keep it that way.

---

## 1 · The layering

```
        ┌──────────────────────────────────────────────┐
        │  features/    seven screens                  │  knows: components, hooks, types
        ├──────────────────────────────────────────────┤
        │  app/         shell · router · registry      │  knows: components, kernel, features
        ├──────────────────────────────────────────────┤
        │  components/  22 primitives                  │  knows: design tokens, domain types
        ├──────────────────────────────────────────────┤
        │  kernel/      THE BOUNDARY                   │  knows: the backend. Nothing else does.
        ├──────────────────────────────────────────────┤
        │  design/      tokens · themes · grid         │  knows: nothing
        └──────────────────────────────────────────────┘
```

Dependencies point downward only. A `features/` module importing another
`features/` module is a smell; importing `kernel/http` directly is a defect.

### The invariant to defend in review

> **No screen may import `fetch`, a URL, an endpoint name, or any transport
> concept.** Everything the UI knows about the backend is `KernelClient`.

Grep test — this must return nothing:

```bash
grep -rn "fetch(\|localhost\|http://\|/v1/" src/features src/components src/app
```

---

## 2 · The Kernel boundary

`src/kernel/client.ts` declares one interface. Three things implement or
consume it:

| | |
|---|---|
| `mock/mockKernel.ts` | Complete in-memory implementation. Real state, real mutations, a synthetic live event stream, simulated latency. This is what you run today. |
| `http/httpKernel.ts` | Typed placeholder. Every method returns `not-implemented`. The transport plumbing around it — request helper, status→error mapping, SSE reconnect with backoff — is real and finished. |
| `KernelProvider.tsx` | Creates one client for the app lifetime, disposes on unmount. |

### Wiring a real endpoint

When C15.0's contract for, say, the brief is confirmed:

1. Set the real path in `ENDPOINTS` in `httpKernel.ts`.
2. Replace that method's `return notImplemented(...)` with a `request<T>()` call
   plus a mapping function from the wire shape to `Brief`.
3. Nothing else changes. No screen, no component, no type.

Each method carries a `// MAP:` comment describing the shape it needs. Do the
mapping in `httpKernel.ts` — never widen `types.ts` to accommodate a wire
format, because `types.ts` is the vocabulary the UI reasons in, not a DTO.

### Why `Result<T>` instead of throwing

Every method returns `Result<T>` rather than rejecting. Errors are values, so
every call site is forced to decide what the founder sees. Eng. Law IV requires
that failure be designed; a thrown promise produces an undesigned screen.

`KernelError.message` is written to be **read by the founder as a sentence** and
is rendered directly. It is never a stack trace, and `code` is what branching
logic uses.

---

## 3 · Data access

No data-fetching library. Four hooks in `src/kernel/hooks.ts`:

```ts
useAsync(fn, deps)      // { data, error, loading, reload } — race-guarded, unmount-safe
useMutation(fn)         // { run, pending, error }
useKernelEvents(limit)  // backfill + live, capped ring buffer
usePresence()           // idle | thinking | speaking | awaiting
useStreamStatus()       // connection state for the status bar
```

If a future screen needs caching, deduplication or optimistic updates that these
cannot express, add the library then — not before. Right now the whole data
layer is ~250 lines and has no version to keep up with.

Standard screen shape:

```tsx
const { data, error, loading, reload } = useAsync(cb, [kernel]);
if (loading) return <Skeleton lines={6} />;
if (error)   return <ErrorState error={error} onRetry={reload} />;
if (!data?.length) return <EmptyState headline="…" body="…" />;
```

All four branches are mandatory. The empty state must read calm, not broken —
it is the product's destination, not an edge case.

---

## 4 · Routing

`src/app/router.tsx` — a ~90 line hash router. Hash rather than history so the
built bundle works unchanged from `file://` inside a desktop shell.

`src/app/registry.tsx` is the only place a screen is registered. The nav rail,
the command bar and the router all read from it.

Every route declares a `gate`, recording its Bible §12 justification:
`explains` (it explains AI work) · `judgment` (it requests human judgment) ·
`operator` (inspection surface). **A route with no gate cannot be added.**

Deep links: `#/ledger/RCP-1042` — the second segment arrives as
`useLocation().detail`, so any row in any explorer is linkable. Filter state
lives in `location.query`, so a filtered view is shareable.

---

## 5 · The design system

`src/design/tokens.css` is the single source of truth: grid, colour, type
scale, easing, durations, planes. **Every value in the app comes from a token.**
A raw hex or a raw pixel line-height in a feature stylesheet is a defect.

Two enforcement scripts:

```bash
node scripts/verify-wiring.mjs   # imports resolve, named exports exist, no `any`
```

The token check is worth adding to CI too — one pass already caught twelve
invented token names (`--color-surface`, `--color-text-dim`, …) that would have
silently rendered as transparent.

Themes are `[data-theme]` on `<html>`: `midnight` · `depth` · `contrast`, all in
the dark family. Density is separate and changes spacing only, never colour.

---

## 6 · Where the Bible is enforced structurally

Conventions get worked around, so the load-bearing rules live in the type system
or in the kernel refusing.

| Rule | Where |
|---|---|
| Full consequence quartet | `Consequence` — four required fields |
| Silence has a default | `SilenceDefault` required on `JudgmentRequest` |
| Confidence is never a number | `Confidence` is a three-member union |
| The calm claim must be provable | `canClaimCalm()` type guard over `Attestation` |
| Reversibility is declared | `Reversibility` required union; unclassified capabilities render non-executable |
| Irreversible never batches | `submitBatchVerdict` returns `invalid` |
| Append-only ledger | No update/delete on the client surface at all |
| No modals | There is no modal primitive; the command bar is a docked sheet |

If you find yourself needing to weaken one of these to ship something, that is
the signal to re-read Bible §12 — not to widen the type.

---

## 7 · Adding a screen

1. Create `src/features/<name>/<Name>.tsx` + `.css`.
2. Add methods to `KernelClient` if needed; implement in **both** `mockKernel`
   (fully) and `httpKernel` (as `notImplemented`). Never one without the other.
3. Register in `src/app/registry.tsx` with a `gate`.
4. Answer the three questions from Bible §12 in the PR description:
   does it reduce founder thinking · does it explain AI work · does it require
   human judgment. If none, it must not exist.
5. Ship its empty state and its failure sentence in the same commit.

---

## 8 · Desktop packaging

No framework chosen. The app is a plain web bundle with `base: './'`, hash
routing, and `src/kernel/desktop/bridge.ts` feature-detecting Tauri or Electron
at runtime — no-op in the browser, window controls only rendered when a host is
present.

Whichever shell you pick should be purely additive. Nothing in `src/` imports a
desktop API directly; it all goes through the bridge.

---

## 9 · What is deliberately absent

- **A state management library.** Server state lives in hooks; UI state is
  local; preferences are `localStorage`. There is no global store because
  nothing yet needs one.
- **A component library.** Every primitive is ours, because the Design
  Constitution is stricter than any library's defaults.
- **A router library.** Seven flat routes.
- **A CSS framework.** Tokens and plain CSS.
- **Notifications, toasts-for-success, badges, modals.** Forbidden by the
  Bible, and their absence is load-bearing rather than an omission.
