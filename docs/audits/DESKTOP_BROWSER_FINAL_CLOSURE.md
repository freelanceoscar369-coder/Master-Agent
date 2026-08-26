# Desktop + Browser: what is closed, what is not, and what may be built on top

**Read this before proposing more Desktop or Browser architecture.** Its
purpose is to stop the next mission rediscovering what this one paid for,
and to be honest about the parts that are *not* closed so nobody plans
against a promise that was never made.

Nothing here is a TODO list. Every remaining item is classified.

---

## 1. Canonical state

| | |
|---|---|
| Feature branch | `claude/founder-browser-identity` |
| Baseline it diverged from | `60dbaa0` (`origin/main`) |
| Full suite at baseline | 100 failed, 7972 passed |
| Full suite at closure | **91 failed, 8056 passed, 0 new regressions** |
| Isolation patch | `01306bb` semantics integrated (see §7) |

---

## 2. The decision boundary, which is the thing most worth preserving

Two different decisions, made by two different owners, in this order:

```
reasoning required
      ↓
AI Capability Broker          ← decides WHICH PROVIDER, from generic facts only
      ↓
TrustedWebAiProvider
      ↓
TrustedBrowserPort            ← decides WHICH BROWSER WINDOW executes it
      ↓
Chrome or Comet
```

The Broker knows nothing of Chrome, Comet, window handles, UIA controls,
site selectors or foreground state. Browser availability never selects a
provider. A provider never selects another provider — if the trusted lane
cannot execute, it returns a truthful failure and any second attempt is a
new Broker decision with its own record.

This is enforced, not merely intended:
`tests/test_trusted_web_ai.py` refuses a provider that defines any
function whose name contains `select`/`rank`/`choose`/`prefer`/`fallback`,
and refuses any import of `broker`, `mission_control`, `runtime` or
`planner`. The Desktop Executive guard independently refuses the word
`ranked` and any product name inside `desktop/` — it caught both during
this tranche.

---

## 3. Desktop Executive

**Closed.** Nothing new was built here; one generic primitive was added
and one word was removed.

`find()` gained an optional `control_type` filter, threaded through
`find_target` and `desktop_type_text` as declared optional arguments so
the closed-schema contract stays honest. It exists because a name alone is
not always an identity: a modal dialog, its heading and its edit box can
all carry the same accessible name, and the first match wins.

**Two traps paid for. Do not rediscover them.**

1. **A read-back failure can mean the wrong element, not a failed write.**
   Four rename attempts reported "wrote to UIA element but the read-back
   value did not match". The write mechanism was correct throughout; it was
   writing to a `Window` (50032) that has no value to set and no
   TextPattern to read. The real field was an `Edit` (50004) of the same
   name sitting beside it.

2. **Focus is perishable.** After `bring_to_front` succeeded, the browser
   held the foreground for roughly four seconds before another application
   took it. Anything that observes expensively *between* taking focus and
   acting will lose the focus it took. Prepare first; focus and act back to
   back. The Desktop Executive already refuses to type into a window it
   cannot confirm is in front, and that refusal is correct behaviour, not a
   bug to route around.

A third, smaller: a popup menu is dismissed when focus moves, so polling
briefly beats sleeping. A modal is not a popup and does survive, so it is
worth waiting for properly.

---

## 4. Browser: two lanes, deliberately separate

**Ordinary web automation** — open a page, search, read, fill a form —
remains the Browser Executive over Playwright (MB022). Unchanged.

**An AI website used as a reasoning provider** runs in the founder's own
ordinary browser through the Desktop Executive. This is not a preference:
Google refuses to sign in inside an automation-controlled browser
(*"this browser or app may not be secure"*), so the automated lane cannot
authenticate a Google account at all. No amount of profile persistence
changes that, and stealth flags are not on the table.

`browser.free-ai` and the persistent Playwright browser identity are
**kept and remain valid for other deployments**. Founder Edition simply
does not register an executable implementation for it, so it is `known=yes
executable=no available=no` — known is not configured, and the Broker can
say "unavailable" honestly rather than never having heard of it.

**Browser resolution is observed, never preferred.** A browser already
showing the target page beats one that is not, whichever browser it
happens to be; the foreground breaks a tie between two that both show it;
genuine ambiguity goes to the founder. There is no Chrome-first or
Comet-first rule anywhere.

**Recognisable is not drivable.** Comet was showing the target page in its
title and threw `COMError` on every accessibility read. A window title is
cheap evidence and not sufficient evidence, so candidates are ordered and
each is proven by observation before anything is typed into it.

---

## 5. Web AI

One provider class, one port, site knowledge as data. A second web AI
service is a second `WebAiSite` value — proven by a test that drives a
fake service through the same provider, port and Broker with no new class,
no new executor, and no Broker or Planner branch.

Gemini's facts, all read from the live page rather than guessed:

| | |
|---|---|
| composer | `Enter a prompt for Gemini` (Edit) — **present while signed out**, so its existence is not proof of authentication |
| conversation menu | `Open menu for conversation actions` |
| rename item | `Rename` (MenuItem) |
| rename field | `Rename this chat` (**Edit, 50004**) — the dialog and its heading share this name |
| dedicated chat | `Kalpavriksha` |
| response noise | `Gemini replied`, A/B comparison scaffolding, disclaimers, loading states |

**Turn ownership**: pre-submit observation + prompt anchor + post-submit
delta, excluding the prompt echo, the previous turn and known noise. The
first "new" text after submitting is a disclaimer; a rule that takes the
first new text returns it instead of the answer.

Live, twice: `Bloom / Leaflet / Seedling`, then `Twig`, same conversation
reused, no duplicate created, both `Verdict.MATCHED` through the existing
TextVerifier.

---

## 6. Safety properties that must not regress

- Never type without confirming the target window is foreground **at the
  moment of the act**.
- Never close a tab this task did not open.
- Never choose between accounts or profiles. The founder's own machine
  offered three Chrome profiles, **two carrying the same person's name** —
  first, order and name-similarity would each have picked wrong with full
  confidence.
- Never request, type, read, store or log a password, OTP, recovery code,
  passkey or security-key material. Surface that the founder must act, and
  go back to watching.
- A port that cannot ask must not be reported as the founder declining.

---

## 7. Test isolation

The approved isolation work is **two** commits. Cherry-picking only the
second auto-merged cleanly and silently dropped half of it: the import
survived and the line that used it did not. Four tests kept inheriting the
founder's real `~/.master_agent`, invisibly, and only in combination —
each passed alone.

Now: launcher tests state their own config, `app_dir` is per-test, and
under a poisoned `GEMINI_API_KEY` with an egress guard nothing leaves the
machine. The founder's state hash is unchanged across full runs.

---

## 8. Known limitations — every one classified

**DELIBERATELY FUTURE-DEFERRED** (the current contracts support these;
none requires reopening Desktop or Browser architecture):

- General demonstration capture and procedure compiler (OpenAdapt-style).
  The assimilation matrix in
  `DESKTOP_EXPERTISE_OPEN_SOURCE_ASSIMILATION.md` is the evidence base.
- General self-experience retrieval (UFO-style), vector/semantic
  retrieval, autonomous knowledge promotion. Promotion Review governs;
  nothing here promotes itself.
- Additional web-AI sites (ChatGPT, Claude, Perplexity, Kimi, DeepSeek) —
  each is a `WebAiSite` value.
- Vision/OCR, which would consume the existing observation and action
  ports.
- MCP / universal tool integration.

**EXTERNAL LIMITATION:**

- Google refuses automated-browser sign-in. This is their security
  judgement and is why the trusted lane exists.
- Comet's accessibility tree currently raises `COMError` on deep
  enumeration on this machine and version. Recorded narrowly — *this*
  mechanism, *this* version — not as "Comet is unusable". Fresh
  observation always overrides it.

**FOUNDER DECISION REQUIRED — escalated, not silently patched:**

- openadapt-flow's fault-model study reports **5 of 7 transactional fault
  classes are silently mishandled by screen verification**: partial save,
  phantom optimistic-UI success, duplicate submission, lost update,
  double-delivered click. Our verification reads a screen text region. For
  "did the AI answer", the screen genuinely *is* the system of record. The
  moment this lane points at anything that **writes** a record, it stops
  being sufficient. Revisit before that happens.

**NOT CLOSED — stated plainly so nobody plans against it:**

- **App Knowledge identity is still `provider_id`.** `resolve_app_knowledge`
  walks `PROVIDER_CATALOG` matching `inventory_key`, so an ordinary
  application cannot own a knowledge profile without pretending to be an
  AI provider. Chrome and Comet therefore have **operations** knowledge
  (`desktop/operations/knowledge.py`) but no `AppKnowledgeProfile`. The fix
  is specified — `application_key` canonical, `provider_id` optional, one
  profile set with two derived indices — and unbuilt.
- **No Windows/UIA/Chromium reference corpus exists.** Interaction
  technique is currently chosen from control type and live observation,
  which worked for the rename, but there is no curated local baseline.
- Everything above depends on the identity fix landing first.

---

## 9. Attribution

`microsoft/UFO` `cd9bfdd`, `OpenAdaptAI/OpenAdapt` `753f3d2`,
`OpenAdaptAI/openadapt-flow` `80dc49b` — all MIT, inspected only. No code
was copied and no dependency was added. Neither project's name appears in
product control flow.
