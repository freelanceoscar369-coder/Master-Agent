# Mission Brief 027.5 — The Kalpavriksha Launcher

Status: **Shipped** — 2026-07-29

The founder entry point. One command that recovers state, wires every
shipped subsystem, starts the Runtime, and hands the terminal to the
Founder Dashboard.

## Objective

MB023–MB026 built a system that coordinates, runs unattended, survives
restarts, and can be watched — and left it reachable only from pytest.
`ROADMAP.md` has carried the gap since MB026:

> **A shipped launcher.** MB026 proved the Dashboard works when a caller
> wires Mission Control + Runtime + persistence + recovery together, but
> that wiring still lives in tests.

This brief closes it. **No new architecture**: every component is used
through its published contract, unmodified.

## The command

```
kalpavriksha
```

| Flag | Effect |
|---|---|
| `--state-dir PATH` | Where snapshots and the event log live (default `~/.master_agent/state`) |
| `--enable-execution` | Register Executive gateways so dispatched tasks actually run. **Off by default** — see §"The finding" |
| `--demo` | Submit one demonstration objective (create folder, write file — both reversible). Implies `--enable-execution` |
| `--boot-only` | Print the boot report and exit |
| `--poll-interval` / `--refresh-interval` | Runtime and Dashboard cadences |

Ctrl-C stops the Dashboard, stops the Runtime, and writes a final
snapshot, so the next launch resumes from a system at rest rather than
replaying an interrupted one.

## Design: the Launcher is a composition root

`src/master_agent/launcher/` is the one place permitted to know about
every layer at once, because its only job is to construct them and wire
them together. It is not Brain, not Operator, not Shared Infrastructure —
it sits outside all three, exactly as `cli.py` does today.

Two rules keep that true, both enforced by tests rather than intention:

1. **Nothing in `src/` imports the launcher.** A composition root that
   something depends on has stopped being one. Asserted by walking every
   module's AST, so a re-exported or aliased import cannot slip past.
2. **`boot.py` defines only report and container types.** It may
   construct and wire; it must not decide, execute, or verify. Asserted
   by parsing its class definitions.

## Boot sequence, and why each step sits where it does

| # | Step | Why here |
|---|---|---|
| 1 | Shared Infrastructure | Permission System first: it is the gate every layer above consults, so nothing should exist before it |
| 2 | Mission Control | Must exist before persistence, which subscribes to its bus |
| 3 | Persistence | Before recovery, which reads through it |
| 4 | Runtime | Before recovery, so `recover()` can restore the cycle counter into it in the same pass — MB025 found that a restored runtime with a wrong counter silently does nothing |
| 5 | **Recover** | **Before recording starts.** Recovery reads history; recording writes it; overlapping them risks appending recovered state back into the log it came from |
| 6 | Event recording | Everything from this instant forward is durable |
| 7 | Discover Executives | **After** recovery — recovery restores the Executives that existed, and discovery is idempotent, so this adds only what is genuinely new. **After** recording began, so the registration is in the log for the next replay |
| 8 | AI Capability Broker | Reported, not skipped — see below |
| 9 | Execution posture | The single wiring choice that separates watching from acting |
| 10 | Founder Dashboard | Last: it observes everything above, and per ADR-0016 Decision 5 it is *handed* the recovery report rather than discovering one |

Step 7's ordering is load-bearing and has its own test: get it wrong and
the second launch raises `ExecutiveAlreadyRegistered`.

## Every step reports its real status

```
  [OK  ] Shared Infrastructure  (1 plugin(s), permission system armed)
  [OK  ] Mission Control  (event bus, registries, dispatcher)
  [OK  ] Persistence  (state at C:\Users\DELL\.master_agent\state)
  [OK  ] Runtime  (heartbeat constructed, not yet started)
  [OK  ] Recovery  (no previous state; first run)
  [OK  ] Event recording  (subscribed to every event type)
  [OK  ] Executives  (1 newly discovered, 1 registered, 14 capabilities)
  [--  ] AI Capability Broker  (architecture frozen (MB027, ADR-0017) but
                                not implemented; no provider selection is
                                available in this build)
  [--  ] Execution posture  (observation only; no gateways registered, so
                             dispatched tasks will not run)
  [OK  ] Founder Dashboard  (attached to the event bus)
```

A step that could not run reports its status **with a reason** — never
`ok`. This is ADR-0016's discipline applied to boot: `0` and "unknown" are
different facts, and a launcher that claims a subsystem started when it
did not is worse than one that refuses to start.

**The AI Capability Broker step exists and cannot succeed.** MB027 froze
its architecture and the founder ratified it; no implementation exists
(`ROADMAP.md`, Planned item 6). `KalpavrikshaSystem.broker` is `None` — a
reserved seam, not a hole — so the gap is visible at every boot rather
than discovered later by someone wondering why nothing selects a provider.

## The finding: the Runtime path does not consult the Permission System

Building the launcher surfaced a real defect, verified by running it
rather than by reading:

> On the Runtime path, an **`IRREVERSIBLE` `delete_folder` completes with
> no approval anywhere.**

The mechanism: `FilesystemPlugin.invoke()` grants itself a `ONCE`
permission on the Executor's key (the ADR-0005 relay), on the assumption
that the Orchestrator already gated the call at the plugin/capability key.
The Runtime does not go through the Orchestrator — it calls the gateway,
which calls `invoke()` directly. So the outer gate never runs and the
inner one is self-satisfied.

This contradicts **Constitution Rule 5**: *"The Permission System is
consulted before any step above `READ_ONLY`, regardless of which Operator
Instance executes it."*

**It predates this brief.** MB024 built the path; MIT-001 certified it.
MB023.1 came closest to naming it: *"`run()` is not a second boundary."*
What MB027.5 changes is that a founder can now reach it by typing one
command — which turns a latent architectural gap into a live safety issue.

**What this brief did about it, and deliberately did not:**

- **Did not fix it.** The fix belongs in the gateway or the Orchestrator
  boundary, both frozen. That is its own Mission Brief, now on
  `ROADMAP.md`.
- **Did not paper over it.** An earlier draft of this launcher had an
  `--approve-session` flag that relayed grants for everything below
  `IRREVERSIBLE`. Running it proved the relay was decorative — the plugin
  self-grants regardless. It was removed: dead safety code is worse than
  none, because it reads like protection.
- **Made execution opt-in.** Registering a gateway is what makes a
  dispatched task run, so not registering one is a wiring choice fully
  inside the composition root's remit — no new component, no new
  architecture. Default `kalpavriksha` observes and coordinates. Acting
  requires `--enable-execution`, and the boot report says `WARN` with the
  reason when it is on.
- **Characterised it in a test** (`test_the_runtime_path_is_ungated`) that
  is written to **fail when the gap is fixed**, forcing the boot report's
  wording and this section to be corrected at the same time — rather than
  the launcher warning forever about something that is no longer true.

## What was built

| File | Contents |
|---|---|
| `launcher/boot.py` | `BootStep`, `BootReport`, `KalpavrikshaSystem`, `build_system()` |
| `launcher/main.py` | `kalpavriksha` argument parsing, boot report printing, run loop |
| `pyproject.toml` | `kalpavriksha = "master_agent.launcher.main:main"` |
| `tests/test_launcher.py` | 22 tests against real components — no fakes |

`build_system()` constructs but does not start; construction and starting
are separate so a caller (or a test) can inspect a fully-built system
before it moves.

## Verification

- **22 new tests, 993 passing, 1 skipped, zero regressions** (971 before).
- Ruff clean across `launcher/` and `test_launcher.py`. Twenty pre-existing
  ruff findings remain in files this brief did not touch; fixing them
  would be an unrequested refactor (Rule 2) and they are named here rather
  than silently swept in.
- **Run live**, not just tested: `kalpavriksha --boot-only` prints the
  report above, and a five-second live run showed the Runtime dispatching,
  going idle, checkpointing, and the Dashboard rendering all nine panels
  with a 41-event log.

## Two real defects found by building it

1. **The Permission System gap** above — the significant one.
2. **A cp1252 encoding regression, reintroduced.** The launcher's own
   `print()` output used an em dash, which a Windows console cannot
   encode — the exact bug MB026 found and fixed for the Dashboard. The
   Dashboard solves it by asking the stream what it can encode; the
   launcher prints twelve lines, so the proportionate fix is to write
   nothing that needs encoding. Now asserted by a test that also round-
   trips the output through cp1252, because it is invisible on a UTF-8
   terminal.

## Technical Debt and Known Limitations (Rule 10)

1. **The Permission System is not consulted on the Runtime path.** The
   top item; see above. Roadmap item.
2. **The AI Capability Broker is absent.** Reported at every boot.
3. **Only the Filesystem Executive is wired.** The Browser Executive
   registers fine but has no shipped gateway — MB024's `BrowserGateway`
   lives in test support, and moving it is a separate roadmap item that
   belongs beside the Browser Executive, never inside `runtime/`.
4. **There is no way to state an objective in your own words.**
   `Objective` requires an explicit `Task` list naming capabilities and
   payloads; the component that turns a sentence into that list is the
   real Planner (`ROADMAP.md`, Planned item 1). `--demo` exists because it
   is currently the only way to watch the loop actually run.
5. **`--demo` writes to the real Desktop**, via `default_locations()` —
   the same locations the shipped CLI uses. Correct for a real command,
   worth knowing before running it.
6. **No log file.** The boot report goes to stdout and is then overwritten
   by the Dashboard's first frame. `--boot-only` is the workaround.

## The Scalability Question (Rule 1)

- **A new Executive** costs nothing here: discovery reads the Plugin
  Registry, and gateway registration iterates whatever is registered. The
  launcher names no plugin.
- **A new subsystem** costs one step in `build_system()` and one line in
  the boot report — the shape that made adding the Broker's *absence*
  a three-line change.
- **Where it will strain:** `build_system()` is a straight-line function
  whose ordering constraints live in comments and one test. At twice the
  number of steps, that ordering wants to be data (a declared dependency
  graph) rather than statement order. Not yet — six steps with four real
  constraints does not justify a framework.
