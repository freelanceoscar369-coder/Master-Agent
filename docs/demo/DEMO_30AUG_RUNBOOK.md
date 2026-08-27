# Demo runbook — 30 August 2026

Short on purpose. Everything here is a thing to do or a thing not to do.

## Pre-demo

1. Close every running Kalpavriksha instance. Exactly one runs during the
   demo.
2. Confirm `KALPAVRIKSHA_FMEA_REASONING_TIER` is **unset**. It is a
   validation scope, not a product setting, and it narrows the reasoning
   ladder.
   ```
   Get-ChildItem Env: | Where-Object { $_.Name -like 'KALPAVRIKSHA*' }
   ```
   Nothing should print.
3. Run the self-check on the binary you are about to demo:
   ```
   .\dist\Kalpavriksha\Kalpavriksha.exe --self-check
   ```
   Look for `RESULT: OK`, the capability count, and `no-ollama:
   constructed=no, candidate=no`.
4. Start the loopback fixture **only if** you are demonstrating the
   ordinary Browser path. It is disposable and local:
   ```
   python scripts/live_acceptance/demo_30aug_battery.py browser
   ```
   That runs the path end to end and reports PASS/FAIL. For a live demo
   you want the fixture served on its own — see *Golden objective 2*.
5. Leave the founder's own Chrome and Comet windows alone. Sign-in state
   there is the Trusted Web lane's environment.

## Start

```
.\dist\Kalpavriksha\Kalpavriksha.exe
```

One window. Wait for the greeting before typing.

## Golden objectives

Type them verbatim. Each one is chosen to show a different thing.

### 1 — LOCAL · nothing is asked of a model

> Create a folder called KalpavrikshaDemo on the Desktop. Then write it
> into proof.txt inside that folder. The text should be: Kalpavriksha
> demo ready

**Expect:** the folder and file appear on the Desktop; the reply says the
work finished and that both steps were independently verified.

**The point:** two steps, fully dictated, and **zero AI planning calls**.
No provider was asked which capability creates a folder.

### 2 — ORDINARY BROWSER · Playwright, and a fresh observation

Serve the fixture first (any free port), then use its URL:

> Open a browser session and navigate to
> http://127.0.0.1:PORT/acceptance.html. Type the text acceptance into
> the element matching #acceptance-box, click the element matching
> #apply, observe the page and tell me the current text shown by #state,
> then close the browser session.

**Expect:** a browser opens visibly, the form is filled, Apply is
clicked, the browser closes, and the reply **begins with the word
`accepted`** followed by the verification summary.

**The point:** six dictated steps, zero AI planning calls, and the answer
comes from a *fresh* observation of `#state` rather than from what the
click reported about itself.

### 3 — REASONING + REAL ACTION · AI where thinking is needed

> Think of exactly three short names for a gardening notes app and write
> them one per line into demo_names.txt on the Desktop.

**Expect:** the file appears on the Desktop with exactly three names; the
reply says both steps were verified.

**The point:** still **zero AI planning calls**. A model is used, once,
*inside* `Reasoning.Transform` — and the file holds exactly the text that
TextVerifier passed, bound from Evidence rather than predicted.

### 4 — A QUESTION · thinking without doing

> what is required to make Kalpavriksha self-improving?

**Expect:** a reasoned answer. Not "Nothing has run yet".

**The point:** a question with nothing behind it is a question, not a
report request. It plans to one `Reasoning.Transform` step with zero AI
planning calls.

## The two browser lanes — do not swap them

This matters more than it looks, and it is the easiest thing to get wrong
while preparing.

| Lane | What it is for | Mechanism |
|---|---|---|
| **Ordinary web automation** | public pages, forms, fixtures, scraping, testing | **Playwright**, via `BrowserSessionManager` |
| **Trusted web AI** | an AI *website* used as a reasoning Provider (Gemini) | the founder's **real, already-signed-in Chrome or Comet**, driven through the Desktop Executive |

Playwright in lane 1 is correct and deliberate. It is not a limitation to
be "fixed" by pointing lane 1 at the founder's browser — doing that would
move ordinary automation into a signed-in session and let a Worker decide
something only the Brain may decide. Architectural guards in
`tests/test_browser_lane_separation.py` will fail if anyone tries.

## Recovery

| Symptom | Do this |
|---|---|
| A mission reports a failure | Read the reply. It names what was expected and what was observed. That is the product working, not a bug to hide. |
| A public website blocks automation | Expected. Verification reports the mismatch. **Do not** switch to the founder's browser, add stealth flags, or retry through the trusted lane. Use the loopback fixture for the demo instead. |
| A browser is left open after a failed mission | Known, recorded, post-demo. Close it by hand; it does not affect a later mission, which uses its own session id. |
| The app seems stuck | Check for a pending approval or clarification in the window. Waiting on the founder is not slowness. |
| Reasoning is slow or refuses | The ladder walks providers in order. Let it. Pinning a tier for a demo hides the behaviour the ladder exists for. |

## Do not touch

- Do **not** set `KALPAVRIKSHA_FMEA_REASONING_TIER` for the demo.
- Do **not** close the founder's own Chrome or Comet windows.
- Do **not** delete the Gemini conversation named **Kalpavriksha** — the
  trusted lane's continuity depends on it.
- Do **not** run a second Kalpavriksha instance.
- Do **not** use Google Search as a demo objective. It serves an anti-bot
  interstitial to automation, and that is outside our control.

---

## Final semantic acceptance — how to run it

The point of this run is **not** whether a folder appears. It is whether
what appeared corresponds to what you meant, and whether what you are
told about it is true.

### Ground rules

1. **Use a name you have not used before.** Not `Rudra`. That name is on
   two earlier runs, and `CreateFolder` is idempotent by design — a
   folder that already exists verifies perfectly and proves nothing about
   this run. A fresh name is the only way the machine can be caught.

2. **Say the destination however you would naturally say it.** Nobody
   will tell you a phrasing to use. If a suggested wording were needed to
   make it work, the wording would be the feature and the understanding
   would not exist. Say it the way you would say it to a person.

3. **If it asks you something, answer it however you like** — including
   correcting yourself, or naming a folder inside a place. Being asked is
   not a failure. Being asked something you already answered is.

### What to watch, in order

| Question | Where the answer is | What wrong looks like |
|---|---|---|
| Did it understand? | the clarification it asks, or does not ask | it asks for something you already said |
| Did it act on what you meant? | the path it reports | a folder in a place you did not name |
| Did it check reality? | the verification line | a claim with no observation behind it |
| Did it tell you the truth? | the closing summary | "this did what you asked for" about the wrong place |

The last row is the one that failed twice. A folder really existed, it
really was verified, and the answer was still false — because the thing
being checked and the thing being checked against had both come from the
same misreading.

### If it gets it wrong

Say so plainly and stop. Do **not** rephrase to help it along: a system
that only works when the founder phrases things carefully has not
understood anything, and a second attempt with better wording would hide
exactly the defect this run exists to expose.

### Afterwards

Nothing is deleted to tidy up. `D:\Rudra` from the first failed run stays
where it is unless you ask for it to go — it is yours, not test scaffolding.
