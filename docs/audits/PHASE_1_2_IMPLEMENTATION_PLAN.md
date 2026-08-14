# Phase 1 + Phase 2 — Implementation Plan
**Recorded before any file was changed.**

---

## Scope boundary — what I can and cannot touch

The shipped Kalpavriksha app (its HTML/CSS/JS, tree renderer, WebView bridge,
dashboard code) is **not in this workspace**. Verified by scan, as in the review.

However — and this is why the mission is actionable — **both named Phase 2
defects live in packages I own and built:**

| Named defect | Actual location | Owned |
|---|---|---|
| Row of four disabled buttons | `surface/src/components/FounderActions.tsx` + `surface/src/config/founderActions.ts` | ✅ C21 |
| Two permanent "Awaiting runtime" panels | `founder-edition/src/components/{EnvironmentPanel,FounderRuntimePanel}.tsx` via `AwaitingRuntime.tsx` | ✅ C24 |
| Repeated state surfaces | `surface/src/components/{PresenceHeader,MissionStrip}.tsx` | ✅ C21 |
| Tree prominence | nowhere — **`prominence` returns 0 matches across the tree** | ✅ new |

So Phase 1 + 2 are implemented **here**, in the Founder Edition packages.

**Portability requirement.** If the app the founder is looking at is a separate
Claude-built implementation, these changes must be ported. To make that a
near-zero-cost port, prominence is expressed as **a data attribute plus four CSS
custom properties** — not as React internals. Any tree renderer, mine or
Claude's, can consume the contract without importing a line of my code.

---

## Phase 1 — Dynamic tree prominence

### The contract (portable, framework-free)

```
<root data-prominence="ambient" | "reduced" | "minimum">
  --tree-scale          1.00 | 0.55 | 0.30    canopy scale factor
  --tree-alpha          1.00 | 0.55 | 0.32    particle + filament opacity
  --tree-bloom-opacity  0.60 | 0.00 | 0.00    canopy bloom
  --tree-breathe-amp    1.00 | 0.42 | 0.20    breathing amplitude multiplier
  --veil-strength       0.82 | 0.92 | 0.96    text-protection veil
```

The existing renderer keeps its geometry, its particle language and its state
machine. It reads four numbers. **Nothing about the tree's identity changes.**

### Derivation — from backend state only

A pure function, `deriveProminence()`, consuming the existing semantic execution
state. **No UI state is added to the backend and no backend field is
reinterpreted.**

| Backend condition | Level | Why |
|---|---|---|
| `requires_founder_completion` true | `minimum` | A human is required — the decision is the protagonist |
| `status` = `awaiting_approval` / `blocked` | `minimum` | Same |
| `status` = `failed` (unacknowledged) | `minimum` | The founder must see what broke |
| `status` = executing · planning · understanding · observing · verifying · recovering | `reduced` | Work in flight — work is the protagonist |
| `status` = `completed`, result unacknowledged | `reduced` | The result is the protagonist |
| `status` = `completed`, result acknowledged | `ambient` | Nothing needs anyone |
| `status` = `idle` / no active work | `ambient` | Identity fills the silence |

`resultAcknowledged` is **client-side view state**, held in the UI layer. It is
not written to the backend and no backend field is added.

### Transition rule

> **The tree yields quickly and returns slowly.**

- Receding (`ambient → reduced → minimum`): `--d-6` (600ms), `--e-settle`
- Returning (`minimum → reduced → ambient`): `--d-8` (1400ms), `--e-settle`

Asymmetric on purpose. When work appears, the founder's attention should be
released to it immediately. When work ends, the tree should not snap back and
yank attention away from a result still being read.

### Reduced-motion

`prefers-reduced-motion` keeps prominence (it is information, not decoration)
and removes the transition — levels change instantly, breathing stays off.

---

## Phase 2 — Pure subtraction

Removal and collapsing only. **No new card, panel or surface is introduced.**

| # | Action | Target | Net effect |
|---|---|---|---|
| 1 | **Remove** the four disabled buttons from the surface composition | `ConversationSurface` no longer renders `FounderActions` | −1 band, −4 dead controls |
| 2 | **Collapse** the two "Awaiting runtime" panels into one system line row each | `EnvironmentPanel` / `FounderRuntimePanel` gain a `compact` presentation used by the rail | −2 bordered panels, −2 titles, −2 bodies |
| 3 | **Debord** the rail | Panels → hairline-separated rows, no panel borders | ≈40% less visual weight, zero content lost |
| 4 | **Fold** the mission strip into the system line | `MissionStrip` no longer occupies its own band on the home screen | −1 band |
| 5 | **Retire** the standalone presence band during work | `PresenceHeader` yields its prominence when a work line exists | −1 competing surface |

`FounderActions` and `MissionStrip` are **not deleted from the codebase** —
they remain exported components with their tests intact. They are removed from
the *default composition*. That keeps the ~80% preservation constraint honest
and makes the change reversible in one line.

**Target:** six bands → three regions (identity · work · input) plus one system
line at the bottom edge.

---

## What is explicitly NOT in this mission

No Work Region build-out (that is Phase 3). No state translation table. No
timing rules. No approval redesign. No fire-and-forget, no new dashboard
features, no mission controls, no provider management, no voice changes, no
backend changes, no animations unrelated to hierarchy.

---

## Validation approach

React cannot be installed in this environment, so component rendering cannot be
exercised directly. Instead:

1. **Unit tests** on `deriveProminence()` — every backend state, every
   transition, purity, and the asymmetric duration rule.
2. **A real rendered harness.** A dependency-free HTML page using the *actual*
   tokens and the *actual* prominence CSS, rendering all six required states
   side by side, published and then loaded in a real browser for screenshots.
   This satisfies "inspect the real running UI, not only source" as far as this
   environment permits, and produces before/after evidence.
3. **A static guard** confirming the removed elements are absent from the
   default composition and that no backend field was invented.
