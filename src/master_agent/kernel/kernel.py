"""Constitutional Kernel — the single point at which the constitution is enforced.

Kernel Specification §3.1:

> *"To be the single point at which the constitution is enforced, so that
> constitutional compliance is a property of the system's **structure**
> rather than of anyone's diligence."*

## What is built

`authorize()` is complete: §7.2's three checks, §7.3's attestations,
§7.2 K3's receipt-intent write, and the mint.

`attempt()` is complete: §3.5's liveness and budget gates, §9.1's
`AttemptRecord`, and §8.6's idempotency key.

`settle()` is complete: §9.1's terminal `OutcomeRecord`, the `Receipt`
that **is** that record, and §4.5's transition out of the outstanding set.

`invalidate()` is complete: §11.8's four steps, at both the global and the
objective scope.

**All four operations of §3.5 are now built.**

Nothing executes, nothing is published, and no compensation, retry or
queueing exists here.

## The surface is exactly four operations

§3.5, verbatim:

```
  authorize(ExecutionRequest) → Intent | Refusal
  settle(intent_id, Outcome) → Receipt
  attempt(intent_id) → AttemptToken | Refusal
  invalidate(scope, reason) → count
```

**There is no `execute()`.** *"The Kernel is called; it never calls. This
one absence is what keeps it independent of execution technology."*

Two names differ from the specification's prose, both by ratified
decision: `Intent` is `Warrant` (Objective Engine Specification §13.1
Conflict A), and `Refusal` is `KernelRefusal` (Roadmap §2 C8, so it is not
the third unqualified refusal in the codebase).

## What it holds, and why so little

§3.3 gives the Kernel six things to own. Two of them are state:

| Owned | Here |
|---|---|
| **The Intent** — issuance, lifecycle, expiry | `_outstanding`, empty at construction |
| **The Override switch** — suspension state | `_override`, running at construction |

The other four — the attestation contract, the precondition set, the
receipt-write obligation, and event emission — are behaviour, and belong
to later parts.

**Injected dependencies are two.** §7.3 is why there are not more:

> *"The Kernel verifies each attestation's presence, attestor identity,
> subject match, and freshness. **It never re-derives the verdict.**"*

So the Kernel holds **no attestor**. Not the Reversibility Registry, not
the Permission System, not the Broker. Their answers arrive inside the
`ExecutionRequest` as `Attestation` values, and the Kernel checks them.
Holding an attestor would be the reimplementation §1.2 forbids, and §3.4's
table names the real owner of every one.

What remains is what §3.3 genuinely assigns:

- **`Clock`** — §4.3 sources `issued_at` and `expires_at` to the Kernel.
  Every value object in `foundation/` refuses to read ambient time
  precisely so that one component does, and this is it.
- **`ReceiptLedger`** — §7.2 K3's obligation. *"The Kernel owns the
  obligation; A1 owns the storage."* The ledger is injected, never
  constructed, so the Kernel does not decide where the audit spine lives.

- **`AdmissionProvider`** — K1's source. Founder decision (R28): *"Kernel
  obtains admission information through its admission provider… maintain
  separation between Objective lifecycle and Warrant lifecycle."* The
  Kernel reads a published `AdmissionRecord`; it never imports the
  Objective Engine, which is why C15 can ship before C17.

## One dependency is still deliberately absent

**The Event Bus.** §3.3 gives the Kernel *"what is published, when. Not
the bus, which already exists."* Nothing is published yet, and Objective
Engine Specification §10.3 records that *"zero subscribers is a valid,
fully functional configuration"* — so wiring an unused bus would be a
dependency with no use. It arrives with publication.

## K1 is structural admission, not lifecycle admission

**Founder Decision, 2026-08-06**, superseding ADR-0021 D5. Kernel
Specification §7.2 K1 governs, and it refuses on exactly three
conditions:

```
    objective missing · objective unknown · objective terminal
```

**K1 does not enforce `EXECUTING`.** `READY` and `WAITING` are
non-terminal and pass.

**ADR-0023 D1** settles where the liveness requirement lives, and it is
neither K1 nor the mint: **attestation A1**. Mission Control refuses when
a task is *"not dispatched, or dependencies unmet"*, and an objective that
is not `EXECUTING` has no such task. §3.4's test decides it — Mission
Control owns dispatch readiness, so a Kernel enforcing `EXECUTING` would
be second-guessing the owner.

| Check | Question |
|---|---|
| **K1** | Is this objective admitted and not finished? — *structural* |
| **A1** | Is this task dispatched, with dependencies met? — *Mission Control* |

C8's three objective reasons map one-to-one onto K1's three refusals, so
no new `RefusalReason` was needed and C8 stays frozen.

## The subject of an attestation is this request's payload digest

§7.3 requires a **subject match** and C7 (ED-022) deliberately left the
subject opaque: *"What identifies a subject — a payload digest, a
capability, a request id — is the Kernel's business, not this value's."*

The Kernel's answer is the **`payload_digest`**, on §4.4's authority: *"An
Intent is bound to its `actor`, `capability`, and `payload_digest`.
Presenting it for a different capability or a mutated payload is
refused."* §8.2 calls the digest *"the load-bearing term."*

An attestation gathered for one payload therefore cannot be presented for
another, which is the transfer §7.3's subject match exists to stop.

**TODO(ADR-0022):** the subject does **not** yet bind the A2 attestation
to the `reversibility_class` the request carries. ADR-0022 §5.1 records
the gap as **R34**: a caller can present a genuine, fresh, correctly
attributed A2 attestation together with a *different* class, and nothing
here detects it. The dangerous direction is understatement — claiming
`reversible` for an `irreversible` action yields §8.5's budget of 3
instead of 1 and evades §8.4's *"never automatically retried. Ever."*

The recommended close, which reopens no frozen component: make the A2
attestation's subject a digest of `(payload_digest, reversibility_class)`.
`ReversibilityRegistry.attest()` already takes its subject from the
caller, and the subject convention here is C15's own. Until then, ADR-0022
directs that the carried class is **trusted**.

## `attempt()` refuses in two shapes, and one of them is a recorded gap

§3.5 declares `attempt(intent_id) → AttemptToken | Refusal` and lists four
refusal conditions: *"expired, cancelled, settled, or out of attempt
budget."* **C8's `RefusalReason` can name none of them.** Its eleven
members cover K1's three objective conditions, K2, K3's ledger write,
§7.3's two attestation failures, and §11's four infrastructure
conditions. A lapsed warrant, a spent budget and a settled warrant are
none of those.

This is **R40**, and it is the same family as the shipped **R39**: a
constitutionally required refusal with no vocabulary to express it. Both
close with one decision about C8, and this part does not take it — C8 is
frozen at `c8.0` and the founder's brief for Part 6 forbids a new
`RefusalReason`.

So the four conditions **raise `AttemptNotAuthorized`** rather than
returning a refusal wearing a reason that is not true of it. C8's own
`InvalidKernelRefusal` states why that is the safer of the two:

> *"one that names the wrong check, or names no check at all, is worse
> than no record because it looks like evidence."*

The behaviour §12.1's twelfth guarantee requires is unaffected — *"a
live, unexpired, uninvalidated Intent — `attempt()` refuses otherwise"* —
because every one of the four conditions still fails closed and opens no
attempt. What is missing is the **record**, not the refusal.

The one condition C8 *can* name is the `AttemptRecord` write failing, and
that returns a real `KernelRefusal` — `LEDGER_UNAVAILABLE` at
`K3_RECEIPT_INTENT_WRITE`. Downgrading it to an exception for the sake of
a uniform shape would throw away a refusal the constitution can record.

## `settle()` has no refusal channel, and that is the specification

§3.5 gives three of the four operations an escape and gives settlement
none:

```
  authorize(ExecutionRequest) → Intent | Refusal
  attempt(intent_id)          → AttemptToken | Refusal
  settle(intent_id, Outcome)  → Receipt              ← no refusal
```

**R40 therefore does not extend to `settle()`.** Where `attempt()` raises
because C8 cannot name a refusal it is required to make, settlement raises
because §3.5 gives it nothing else to return. `NothingToSettle` is the
specified shape here, not a workaround, and it stays the right shape after
R39 and R40 are closed.

It is a `RuntimeError` rather than a `ValueError` for the reason
`LedgerUnavailable` gives: a caller wrapping `Receipt(...)` construction in
`except ValueError` to catch `InvalidReceipt` must never absorb *"this
warrant was already settled"* by accident.

**A failed outcome write propagates `LedgerUnavailable` untouched.** §11.3
is fail-closed and A1 forbids buffering, and the warrant stays outstanding
— so the state remains honestly *unsettled* rather than a settlement the
ledger never heard of, which is §9.5's reconciliation gap.

## One outcome record per warrant, not one per attempt

C5's own docstring reads *"one receipt per attempt… several receipts may
share one `warrant_id`."* §9.1 and §4.4 say otherwise, and they govern:

> `IntentRecord ──┬── AttemptRecord (0..n)`
> `              └── OutcomeRecord (0..1, terminal)`
>
> *"One Intent, N attempts, N attempt records, **one outcome record**."*

C13 already resolved it the same way — `record_outcome` refuses a second
outcome for one warrant. So `Receipt.attempt` carries **how many attempts
the warrant used**, and `started_at` is the first attempt's moment, making
`Receipt.duration` the span of the whole authorized execution. Nothing is
changed in C5 or C13 to say this; it is recorded here because the two
readings exist and only one is implementable.

## Invalidation is one operation at two scopes, and only one suspends

§11.8 gives the global form four numbered steps, and step order is the
guarantee:

```
   invalidate(scope=all, reason="founder override")
      1. Set suspension. K2 now refuses every mint.        ← milliseconds
      2. Invalidate every MINTED intent not yet attempted.
      3. Intents already ATTEMPTING run to settlement.
      4. Objective Engine keeps admitting. Mission Control
         keeps assigning. Work queues at the Kernel boundary.
```

**Step 1 precedes step 2 because otherwise the sweep has a hole.** A mint
completing between the two would produce a warrant the sweep has already
passed, surviving an Override that was meant to reach everything. K2
refusing first closes the window, which is what §11.8's *"milliseconds"*
is about.

Steps 3 and 4 are **absences here**, not code. Nothing touches an attempted
warrant, and nothing in this module admits, assigns or queues.

**Only `SCOPE_ALL` suspends.** Objective Engine Specification §10.5 makes
termination *"`kernel.invalidate(scope=objective_id, reason=…)` — the same
operation the founder's global Override uses, **at a narrower scope**.
Nothing new is built."* A narrower scope reaches fewer intents; it does not
stop the machine. §11.8 attributes suspension to the founder's global
Override, and §10.2's diagram gets *"no new mints"* for a terminated
objective from K1 instead — the Engine publishes the terminal state and
`OBJECTIVE_TERMINAL` does the rest. A scoped invalidation that suspended
globally would stop all autonomy because one objective was cancelled.

**There is no confirmation and no friction**, per §11.8 and VEDA 04 A3, and
none can be added: the parameters are `scope` and `reason`, a shipped test
fails the build on any third.

## Two things invalidation cannot do

**It cannot record itself.** §4.5 lists six terminal states and says *"all
six are recorded. **None is a deletion.**"* §4.4 is more specific:
cancellation *"writes a terminal outcome record of kind `cancelled`."*
There is no such record available. C13's `RecordKind` is closed to
`intent · attempt · outcome`; the outcome record **is** C5's `Receipt`,
which requires an `attempt` of at least 1 and one of §6.3's four execution
outcomes — and an invalidated warrant was never attempted, so a receipt for
one would be a claim that something ran.

So invalidation writes nothing. The intent record survives untouched — the
ledger deletes nothing at any privilege level — but **no record says the
warrant was invalidated**, and for an objective-scoped call the `reason`
has no destination at all. Recorded as **R46**. Closing it needs either a
fourth `RecordKind` or a widened outcome vocabulary, and both are GREEN
components this part does not open.

**It cannot be undone.** §3.5's surface is four operations and none of them
resumes. C14's `OverrideSwitch.resume()` exists and the Kernel reaches it
from nowhere, so a suspended Kernel stays suspended for the life of the
process. Recorded as **R47**; adding a fifth operation would be a
speculative API, which is precisely what §3.4's test forbids.

## What `attempt()` and `settle()` deliberately do not re-check

**Not K1.** No `AdmissionProvider` lookup happens here. §3.5 lists four
conditions and the objective's state is not among them, and re-reading
admission would put a fifth gate on the path that no specification asks
for.

**Not K2.** §11.8 is precise: suspension **fails closed on minting**, and
its mechanism for work already authorized is `invalidate()` — *"invalidate
every MINTED intent not yet attempted"* — while *"intents already
ATTEMPTING run to settlement."* A K2 check here would contradict the
second clause and duplicate the first. The Override reaches an
outstanding warrant through Part 8, not through this operation.

**Not the payload digest.** §4.4 says the digest *"is checked at
`attempt()`, not merely at mint"* — but §3.5's operation, and Roadmap
Amendment 001 M4, give `attempt()` an **identifier and nothing else**.
There is no capability and no payload here to compare against
`Warrant.matches()`. Recorded as **R41**; the signature is fixed by §3.5
and is not changed to close it.

**Not the Event Bus.** §3.5 says settlement *"Publishes"* and §10.2 names
`INTENT_SETTLED`. Nothing is published here: §3.3 gives the Kernel *"what
is published, when. **Not the bus**, which already exists"*, the bus is
Mission Control's, and §3.6's dependency rule — enforced by a shipped
architecture guard — forbids this module importing it. Roadmap §2 puts the
subscriber at **C18**, which depends on C13 and C15. §10.3 makes zero
subscribers *"a valid, fully functional configuration"*, and §10.1's
guarantee is **coverage, never veto** — which the durable outcome record
already provides. Publication arrives with its component.

## Two things settlement cannot say, because it has nowhere to say them

`settle(warrant_id, outcome)` carries an id and one enum member. ADR-0023
§6.3 records the founder ruling that it keeps that API and that *"the
Kernel owns all Receipt metadata; Receipt construction occurs internally
using Kernel state."* Two `Receipt` fields are **not** metadata and are not
Kernel state:

**`compensation_ref`.** §6.3 makes it mandatory for `PARTIAL` — *"the most
dangerous outcome"* — and C5 refuses to construct a partial receipt
without one. The Kernel cannot invent a compensating action, so `PARTIAL`
is unreachable through this API and `InvalidReceipt` propagates naming the
missing reference. Recorded as **R43**.

**`detail`.** *"In the caller's words"*, and there are no caller's words in
the signature, so every receipt this Kernel writes carries `None`.
Diagnostic only — C5 states it is *"never load-bearing and never read to
make a decision"* — so nothing constitutional turns on it. Recorded as
**R44**.

Neither is closed here: closing either changes `settle()`'s API, which is
a ratified decision this part does not reopen.

## Placement

`master_agent/kernel/`, not `foundation/`. It depends on two other
packages — `foundation` and `ledger` — and `foundation/` admits a module
only if it has no dependency on any other Kalpavriksha package.

§3.6 places it in **Shared Infrastructure**: both the Brain and the
Operator depend on it, neither depends on the other, and *"dependency
direction is strictly downward — the Kernel imports no Worker, no
Provider, no Environment, and no concrete capability."*

## Size

§14 R9 sets a **600-line ceiling**: *"if the Kernel exceeds roughly 600
lines, something in it belongs somewhere else."* Read as executable lines,
since documentation is not what the ceiling is about.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from master_agent.foundation.admission import AdmissionRecord
from master_agent.foundation.attempt_token import AttemptToken
from master_agent.foundation.attestation import (
    AttestationQuestion,
    AttestationVerdict,
)
from master_agent.foundation.clock import Clock
from master_agent.foundation.execution_request import ActionClass, ExecutionRequest
from master_agent.foundation.override import OverrideSwitch
from master_agent.foundation.receipt import ExecutionOutcome, Receipt
from master_agent.foundation.refusal import (
    KernelCheck,
    KernelRefusal,
    RefusalReason,
)
from master_agent.foundation.warrant import ReversibilityClass, Warrant
from master_agent.ledger.receipt_ledger import (
    AttemptRecord,
    IntentRecord,
    LedgerUnavailable,
    ReceiptLedger,
)

#: The scope value that reaches every outstanding intent. §11.8 shows
#: `invalidate(scope=all, reason="founder override")`; §10.5 shows an
#: `objective_id` in the same position.
SCOPE_ALL = "all"

#: How old an attestation may be and still be relied on.
#:
#: **No frozen document specifies this value.** §7.3 requires freshness to
#: be verified and §14 R3 rates skipping it High — *"if validation degrades
#: to 'a field is present,' the Kernel becomes ceremony"* — but neither the
#: Kernel Specification nor any VEDA gives a window.
#:
#: Sixty seconds is chosen to be short: an `ExecutionRequest` is assembled
#: and authorized in one breath, and §4.3's reasoning for intent expiry
#: applies with more force to the evidence behind it — *"an intent minted
#: before an approval and used hours later is authorized against a world
#: that no longer exists."*
#:
#: **Awaiting founder ratification.** Named as a constant rather than
#: buried so that changing it is a visible decision. See the Part 3 health
#: report's R31.
DEFAULT_ATTESTATION_MAX_AGE = timedelta(seconds=60)

#: §8.5's attempt budgets, completed by ADR-0023 D3.
#:
#: `irreversible` = 1 and `reversible` = 3 are §8.5 verbatim.
#: `reversible_until` = **2 is forced**, not chosen: it must exceed 1
#: because the effect is undoable, and fall below 3 because *"the undo
#: window is not extended by retrying"* — every attempt burns the
#: founder's window to change their mind. One integer satisfies both.
#: `read_only` = 5 is bounded (an unbounded budget is a permission with no
#: end) and above `reversible` because there is no effect to duplicate.
ATTEMPT_BUDGET: dict[ReversibilityClass, int] = {
    ReversibilityClass.READ_ONLY: 5,
    ReversibilityClass.REVERSIBLE: 3,
    ReversibilityClass.REVERSIBLE_UNTIL: 2,
    ReversibilityClass.IRREVERSIBLE: 1,
}

#: §4.4's *"class-specific default"*, keyed by `ActionClass` because §4.4's
#: own examples are *"seconds for a filesystem write, the Broker's derived
#: deadline for a provider call."* ADR-0023 D4.
VALIDITY_DEFAULT: dict[ActionClass, timedelta] = {
    ActionClass.LOCAL: timedelta(seconds=30),
    ActionClass.INTELLIGENCE: timedelta(seconds=300),
}


def _required_questions(action_class: ActionClass) -> tuple[AttestationQuestion, ...]:
    """§7.4's attestation set for one action class.

    > | `local` | K1 · K2 · **A1 · A2 · A3 · A4 · A5 · A6** · K3 |
    > | `intelligence` | … plus **A7 · A8** |
    >
    > *"The sets differ by two attestations. That is the entire difference
    > between the pipelines inside the Kernel."*

    Derived from C7's own `is_intelligence_only`, never restated here —
    the mapping belongs to the vocabulary that owns the questions.
    Declaration order is §7.3's table order, which is what makes §7.1's
    *"the reason returned is the most fundamental one"* well-defined.
    """
    if action_class is ActionClass.INTELLIGENCE:
        return tuple(AttestationQuestion)
    return tuple(q for q in AttestationQuestion if not q.is_intelligence_only)


@runtime_checkable
class AdmissionProvider(Protocol):
    """Where K1 reads a published `AdmissionRecord`.

    Founder decision (R28): admission stays **outside** the
    `ExecutionRequest` boundary, and the Kernel obtains it through this
    port. That is what keeps the Objective lifecycle and the Warrant
    lifecycle separate — a request carrying its own admission would let a
    caller assert the very thing K1 exists to check.

    Objective Engine Specification §10.1: *"The Objective Engine's
    responsibility ends at admission."* It publishes; the Kernel reads.
    The Kernel never imports the Engine, which is why C15 ships before
    C17.
    """

    def admission_for(self, objective_id: str) -> AdmissionRecord | None:
        """The published record, or `None` if no objective resolves.

        `None` is *"unknown objective"* — §7.2 K1's second refusal. It is
        not an error, and it is not a way to say *"exists but not
        ready"*: a record that exists is returned whatever its state, and
        K1 decides.
        """
        ...


class InvalidKernel(ValueError):
    """Raised at construction for a Kernel that could not enforce anything.

    At construction, never later. A Kernel wired to something that cannot
    keep its side of §7.2 would fail on the first mint — which is the one
    moment where failing late is most expensive.
    """


class AttemptNotAuthorized(RuntimeError):
    """The warrant does not authorize another attempt.

    Raised by `attempt()` for §3.5's four conditions — the warrant is not
    outstanding, has expired, has been settled or cancelled, or its
    attempt budget is spent.

    **This exists because C8 cannot name any of them, not because a
    refusal would be wrong here.** §3.5 says these are refusals and §7.5
    says refusals are data. Both remain true; what is missing is a
    `RefusalReason`, and adding one is a decision about a frozen component
    (`kalpavriksha-s1-c8.0`) that this part does not take. Recorded as
    **R40**, alongside the shipped **R39**, which is the same gap reached
    from the mint.

    Until that decision is taken, an exception is the honest shape.
    `InvalidKernelRefusal` states the alternative's cost: a refusal *"that
    names the wrong check, or names no check at all, is worse than no
    record because it looks like evidence."*

    Deliberately a `RuntimeError` and **not** a `ValueError`, following
    `LedgerUnavailable`: a caller wrapping value construction in `except
    ValueError` must never absorb "this warrant is spent" by accident.

    Nothing is written when this is raised, because nothing happened — no
    attempt was opened, so §9.1's `AttemptRecord (0..n)` correctly has one
    fewer.
    """


class NothingToSettle(RuntimeError):
    """There is no live warrant this settlement could be the outcome of.

    Raised by `settle()` when the warrant was never minted here, has
    already been settled, or has opened no attempt.

    **Unlike `AttemptNotAuthorized`, this is not a symptom of R40.** §3.5
    gives `settle()` the return type `Receipt` and no refusal channel at
    all, so an exception is the shape the specification leaves — and it
    stays the right shape after R39 and R40 are closed.

    A `RuntimeError` rather than a `ValueError`, following
    `LedgerUnavailable`: a caller wrapping `Receipt(...)` construction in
    `except ValueError` to catch `InvalidReceipt` must never absorb *"this
    warrant was already settled"* by accident.

    Nothing is written when this is raised. §9.1's outcome record is
    terminal and written once, and a settlement that could not identify
    its warrant has nothing to be terminal about.
    """


class Kernel:
    """The sole minting authority. Structure only in Part 1.

    Constructed with the two collaborators §3.3 assigns it, owning the two
    pieces of state §3.3 names, and exposing the four operations of §3.5 —
    none of which is implemented here.
    """

    __slots__ = (
        "_admission",
        "_attempts",
        "_clock",
        "_ledger",
        "_outstanding",
        "_override",
    )

    def __init__(
        self,
        clock: Clock,
        ledger: ReceiptLedger,
        admission: AdmissionProvider,
    ) -> None:
        if not isinstance(clock, Clock):
            raise InvalidKernel(
                "clock must satisfy the canonical Clock protocol; the Kernel "
                "is the component that reads it, which is why every value "
                "object refuses to"
            )
        if not isinstance(ledger, ReceiptLedger):
            raise InvalidKernel(
                "ledger must be a ReceiptLedger; §7.2 K3 makes the intent "
                "write the Kernel's obligation, and there is nothing to "
                "write to without one"
            )
        if not isinstance(admission, AdmissionProvider):
            raise InvalidKernel(
                "admission must satisfy the AdmissionProvider protocol; K1 "
                "is the constitutional anchor and has nothing to anchor to "
                "without a published record to read"
            )

        self._clock: Clock = clock
        self._ledger: ReceiptLedger = ledger
        self._admission: AdmissionProvider = admission

        #: §3.3 — the Override switch. Running at construction: a Kernel
        #: that started suspended would refuse every mint with nobody
        #: having asked for that.
        self._override: OverrideSwitch = OverrideSwitch(suspended=False)

        #: §3.3 — the Intent's lifecycle. Empty at construction: warrants
        #: are minted, never restored, and §4.1 makes them short-lived.
        self._outstanding: dict[str, Warrant] = {}

        #: How many attempts each outstanding warrant has opened. §3.3
        #: assigns the Intent's **lifecycle** to the Kernel, and *"one
        #: Intent, N attempts"* (§4.4) is that lifecycle; the count is not
        #: §3.4's receipt storage, which stays A1's.
        #:
        #: It is not on the `Warrant`, and cannot be: C4 states that *"a
        #: warrant that knew how many attempts had been used would be a
        #: mutable object wearing a frozen decorator."*
        #:
        #: A warrant appears here only once it has an attempt, and the
        #: ledger's own `(warrant_id, attempt_seq)` key is the crosscheck
        #: — a sequence this counter got wrong is refused at the write
        #: rather than recorded.
        self._attempts: dict[str, int] = {}

    # ---- §3.5 · the four operations ----------------------------------

    def authorize(self, request: ExecutionRequest) -> Warrant | KernelRefusal:
        """Perform the three checks, verify the attestations, write the
        receipt intent, mint. Refuse on any failure, naming which.

        §7.4's order: **K1 · K2 · the attestations · K3**, then the mint.

        **On ordering the write against construction.** §7.2 K3 *"runs
        last, after every other check has passed"*, and its guarantee is
        that **nothing executes without a durable intent**. The `Warrant`
        is therefore *built* before the write and *returned* only after it
        succeeds. Building a frozen value is not executing, and this is
        the only order that cannot orphan a record: if construction were
        to fail after the write, the ledger would hold an intent with no
        warrant — the reconciliation gap §9.5 exists to make impossible.

        Nothing is registered until the write has succeeded.
        """
        admitted = self._check_preconditions(request)
        if isinstance(admitted, KernelRefusal):
            return admitted

        stamp = self._clock.stamp()
        issued_at = stamp.moment
        warrant_id = self._warrant_id(stamp.sequence)

        warrant = Warrant(
            warrant_id=warrant_id,
            objective_id=request.objective_id,
            principal_id=request.principal_id,
            capability=request.capability,
            payload_digest=request.payload_digest,
            reversibility_class=request.reversibility_class,
            consequence_ceiling=admitted.consequence_ceiling,
            attempt_budget=ATTEMPT_BUDGET[request.reversibility_class],
            issued_at=issued_at,
            expires_at=self._expires_at(
                issued_at, request.action_class, admitted.deadline
            ),
        )

        # K3. The write is the last thing that can refuse.
        try:
            self._ledger.record_intent(
                IntentRecord(
                    warrant_id=warrant_id,
                    objective_id=request.objective_id,
                    principal_id=request.principal_id,
                    capability=request.capability,
                    reversibility_class=request.reversibility_class,
                    expected_effect=request.expected_effect,
                    consequence=request.consequence,
                    recorded_at=issued_at,
                )
            )
        except LedgerUnavailable as exc:
            return KernelRefusal(
                reason=RefusalReason.LEDGER_UNAVAILABLE,
                failed_check=KernelCheck.K3_RECEIPT_INTENT_WRITE,
                attestor=None,
                remediable=True,
                detail=str(exc),
            )

        self._register(warrant)
        return warrant

    # ---- mint derivations --------------------------------------------

    @staticmethod
    def _expires_at(
        issued_at: datetime, action_class: ActionClass, deadline: datetime
    ) -> datetime:
        """§4.4's `min()`, with the terms this Kernel can reach. ADR-0023 D4.

        > `expires_at = min(grant validity, budget deadline, class-specific
        > default)`

        Grant validity is omitted because the A3 attestation carries no
        expiry — **R37**. Dropping a term from a `min()` can only lengthen
        the window, so the result is bounded by the two remaining terms and
        tightens when A3 can carry one.

        Deterministic: `issued_at` is read once by the caller and reused,
        so the two terms cannot drift apart.
        """
        return min(issued_at + VALIDITY_DEFAULT[action_class], deadline)

    @staticmethod
    def _warrant_id(sequence: int) -> str:
        """Deterministic, monotonic, and never random.

        §4.3 sources the token to the Kernel and says no more. The
        `Clock`'s stamp *"consumes a sequence number"*, which is the only
        monotonic source the Kernel holds — and using it keeps the Kernel
        verifiable, which `uuid4()` would not.
        """
        return f"wrt-{sequence:012d}"

    @staticmethod
    def _correlation_id(objective_id: str) -> str:
        """The logical unit several executions share (C5).

        Derived from the objective, so every warrant minted under one
        objective correlates without the Kernel storing a mapping.
        """
        return f"cor-{objective_id}"

    @staticmethod
    def _trace_id(sequence: int) -> str:
        """**This** execution (C5). One per mint, from the same stamp as
        the warrant id."""
        return f"trc-{sequence:012d}"

    @staticmethod
    def _receipt_id(sequence: int) -> str:
        """The outcome record's identity, from the warrant's own sequence.

        §9.1 makes the outcome record `0..1` per warrant, so keying it to
        the mint sequence is unique by construction and needs no second
        source of monotonicity. Reading `stamp()` here would consume a
        sequence number and silently shift the identity of the next
        warrant minted — the same reason `attempt()` reads `now()`.
        """
        return f"rcp-{sequence:012d}"

    @staticmethod
    def _sequence_of(warrant_id: str) -> int:
        """Recover the mint sequence `_warrant_id()` encoded.

        The Part 5 health report's §3.1 resolution of **R29**: the receipt
        identifiers are *"pure functions of data already on the
        `Warrant`"*, so settlement re-derives them and the Kernel stores
        nothing at mint. Only ever called with an id this Kernel minted,
        which is the invariant that makes the parse total.
        """
        return int(warrant_id.removeprefix("wrt-"))

    def attempt(self, warrant_id: str) -> AttemptToken | KernelRefusal:
        """Open one attempt against a live warrant. Refuses when expired,
        cancelled, settled, or out of attempt budget (§8).

        **The warrant is never mutated and never re-authorized.** §4.4:
        *"One Intent, N attempts, N attempt records, one outcome record."*
        This is the operation that makes the second half of that sentence
        true, and §8.1 is why it exists at all — *"the root cause is not
        the loop. It is that there was nothing for the loop to be bounded
        by."* The bound is `Warrant.attempt_budget`, set at mint from the
        class and never by a caller.

        **Order, and the one thing that must precede the token.** The
        `AttemptRecord` is durable before an `AttemptToken` exists,
        because the token is §8.6's idempotency key and a Worker holding
        one *"treats it as settled fact."* A token handed out before the
        record was written would authorize an attempt the ledger has never
        heard of, which is §9.5's reconciliation gap arriving one layer
        earlier than the orphan it is named for.

        **Time is read with `now()`, not `stamp()`.** An attempt needs a
        moment, not an ordering token, and `stamp()` *"consumes a sequence
        number"* — spending one here would silently shift the id of the
        next warrant minted. Determinism of the mint is worth more than a
        sequence this value has no field for.

        Four of §3.5's five failure conditions raise `AttemptNotAuthorized`
        rather than returning a refusal; the module docstring records why
        as **R40**. The fifth — the write failing — is the one C8 can
        name, and it returns a real `KernelRefusal`.
        """
        warrant = self._outstanding.get(warrant_id)
        if warrant is None:
            raise AttemptNotAuthorized(
                f"{warrant_id!r} is not outstanding; an attempt runs "
                "against a live warrant this Kernel minted, and there is "
                "no other way to obtain one (§4.2)"
            )

        now = self._clock.now()

        if warrant.is_expired(now):
            raise AttemptNotAuthorized(
                f"{warrant_id!r} expired at "
                f"{warrant.expires_at.isoformat()}; an authorization used "
                "after its window is authorized against a world that has "
                "moved (§4.4), and this action needs a new one"
            )

        used = self._attempts.get(warrant_id, 0)
        if used >= warrant.attempt_budget:
            raise AttemptNotAuthorized(
                f"{warrant_id!r} has used all {warrant.attempt_budget} of "
                "its authorized attempts; the budget is set at mint from "
                "the action's class and is never extended by a retry "
                "(§8.5). A further attempt requires a new warrant"
            )

        attempt_seq = used + 1

        # §9.1's `AttemptRecord (0..n)`, durable before the token exists.
        try:
            self._ledger.record_attempt(
                AttemptRecord(
                    warrant_id=warrant_id,
                    attempt_seq=attempt_seq,
                    recorded_at=now,
                )
            )
        except LedgerUnavailable as exc:
            return KernelRefusal(
                reason=RefusalReason.LEDGER_UNAVAILABLE,
                failed_check=KernelCheck.K3_RECEIPT_INTENT_WRITE,
                attestor=None,
                remediable=True,
                detail=str(exc),
            )

        self._attempts[warrant_id] = attempt_seq
        return AttemptToken(
            warrant_id=warrant_id,
            attempt_seq=attempt_seq,
            opened_at=now,
        )

    def settle(self, warrant_id: str, outcome: ExecutionOutcome) -> Receipt:
        """Record what happened. Terminal. Never mutates the warrant.

        §9.1's `OutcomeRecord (0..1, terminal)`, which C13 states **is**
        the shipped `Receipt` — *"there is no second outcome type, and
        building one would be a second description of one event."*

        **Order, and why the write precedes the transition.** The receipt
        is constructed, written, and only then does the warrant leave the
        outstanding set. If the write fails, `LedgerUnavailable`
        propagates and the warrant is still outstanding — the state stays
        honestly *unsettled*, rather than a settlement the ledger never
        heard of. §11.3: fail closed, no buffering.

        **The transition is a removal, never a mutation.** §4.4 —
        *"Nothing mutates an Intent, ever, at any privilege level. State
        changes are separate append-only records referencing it."* The
        outcome record is that separate record; the outstanding set is
        where §13.3 keeps the Kernel's memory bounded.

        **Every field comes from the warrant, the ledger, or the clock.**
        Nothing is taken from the caller except the outcome itself, so a
        settlement cannot describe an execution other than the one that
        was authorized.

        Raises `NothingToSettle` when no live warrant answers — see that
        exception for why this is a raise rather than a refusal.
        """
        warrant = self._outstanding.get(warrant_id)
        if warrant is None:
            raise NothingToSettle(
                f"{warrant_id!r} is already settled"
                if self._ledger.is_settled(warrant_id)
                else f"{warrant_id!r} is not outstanding; a settlement "
                "records the outcome of a warrant this Kernel minted, and "
                "there is no other kind"
            )

        attempts = self._attempts.get(warrant_id, 0)
        started_at = self._first_attempt_at(warrant_id)
        if attempts == 0 or started_at is None:
            raise NothingToSettle(
                f"{warrant_id!r} has opened no attempt; an outcome record "
                "describes what an attempt did, and §4.5 sends an "
                "unattempted warrant to EXPIRED or CANCELLED, never to "
                "SETTLED"
            )

        sequence = self._sequence_of(warrant_id)
        receipt = Receipt(
            receipt_id=self._receipt_id(sequence),
            objective_id=warrant.objective_id,
            principal_id=warrant.principal_id,
            warrant_id=warrant_id,
            correlation_id=self._correlation_id(warrant.objective_id),
            trace_id=self._trace_id(sequence),
            capability=warrant.capability,
            attempt=attempts,
            outcome=outcome,
            started_at=started_at,
            completed_at=self._clock.now(),
        )

        # Terminal, and durable before the lifecycle moves.
        self._ledger.record_outcome(receipt)

        del self._outstanding[warrant_id]
        self._attempts.pop(warrant_id, None)
        return receipt

    def _first_attempt_at(self, warrant_id: str) -> datetime | None:
        """When the first attempt opened, read from the record that is the
        only evidence of it.

        §9.2 — *"every arrow is an identifier, never a copy."* The Kernel
        keeps the attempt **count** because §3.3 gives it the Intent's
        lifecycle; the attempt **moments** are A1's records, and reading
        one is cheaper than holding a second copy that would eventually
        disagree with it.

        The ledger returns records in append order, so the first
        `AttemptRecord` is attempt 1.
        """
        for record in self._ledger.read(warrant_id):
            if isinstance(record, AttemptRecord):
                return record.recorded_at
        return None

    def invalidate(self, scope: str, reason: str) -> int:
        """Cancel outstanding unexecuted intents. The Override's mechanism,
        and the only bulk operation (§11.8).

        Returns **how many intents were invalidated** — §3.5's `count`.

        **There is no confirmation parameter, and there will never be
        one** — §11.8 and VEDA 04 A3 both forbid it. Nor is there a
        refusal: §3.5 gives this operation the return type `count`, and
        VEDA 01 §10 requires the gesture to be *"immediately, with no
        confirmation dialogue and no persuasion."* An invalidation that
        reached nothing returns `0`; it does not object.

        `scope` is `SCOPE_ALL` or an `objective_id` (Objective Engine
        Specification §10.5). Only `SCOPE_ALL` suspends — see the module
        docstring for why a terminated objective must not stop the machine.

        **Suspension is set before the sweep**, per §11.8's numbering.
        Reversing them would leave a window in which a mint completes
        behind the sweep and survives the Override.

        **An attempted warrant is never touched.** §11.8 step 3 —
        *"intents already ATTEMPTING run to settlement; an in-flight write
        cannot be un-written."* The attempt count is the Kernel's record of
        which those are.

        A blank `reason` at `SCOPE_ALL` raises `InvalidOverride`: C14 owns
        that invariant — *"the founder is owed a sentence about their own
        machine, not a silent stop"* — and it is not restated here.
        """
        if scope == SCOPE_ALL:
            # §11.8 step 1, and it must be first.
            self._override = self._override.suspend(reason)

        # §11.8 step 2. Materialised before removal: a view cannot be
        # mutated while it is being read, and the count is what §3.5
        # returns.
        invalidated = [
            warrant_id
            for warrant_id, warrant in self._outstanding.items()
            if warrant_id not in self._attempts
            and (scope == SCOPE_ALL or warrant.objective_id == scope)
        ]

        for warrant_id in invalidated:
            del self._outstanding[warrant_id]

        return len(invalidated)

    # ---- §7.2 K1 · objective binding ----------------------------------

    def _admission_for(self, objective_id: str) -> AdmissionRecord | None:
        """Read the published record. **No caching.**

        A cached admission is an authority that outlives its source — the
        defect §11.1 names for permissions and rejects for the same reason
        here. §10.2's diagram has the state changing under the Kernel's
        feet, so every check reads afresh.

        A provider that raises is **not** caught. Nothing is minted, which
        is fail-closed, and the failure is not a decision the Kernel made
        — so it must not become a `KernelRefusal` and enter the ledger as
        one. See the Part 2 health report's R30.
        """
        return self._admission.admission_for(objective_id)

    def _check_objective_binding(
        self, request: ExecutionRequest
    ) -> AdmissionRecord | KernelRefusal:
        """K1. Returns the record when it passes, a refusal when it does not.

        §7.2: *"`objective_id` present, resolves to an admitted objective
        in a non-terminal state."* **Structural admission only** — whether
        the objective is *running* is the mint path's question, per the
        Founder Decision of 2026-08-06 superseding ADR-0021 D5.

        The record is returned rather than discarded because the mint path
        needs the envelope it carries (§10.3: `consequence_ceiling`,
        `budget`, `deadline`), and reading it twice would invite the two
        reads to disagree.

        **`OBJECTIVE_MISSING` is unreachable from here**, and deliberately
        so: `ExecutionRequest` refuses a blank `objective_id` at
        construction, so the condition is *prevented* rather than
        detected. C8 keeps the reason for callers C9 does not guard —
        C17's admission path among them.
        """
        record = self._admission_for(request.objective_id)

        if record is None:
            return KernelRefusal(
                reason=RefusalReason.OBJECTIVE_UNKNOWN,
                failed_check=KernelCheck.K1_OBJECTIVE_BINDING,
                attestor=None,
                remediable=True,
                detail=(
                    f"no admitted objective resolves to "
                    f"{request.objective_id!r}"
                ),
            )

        if record.is_terminal:
            return KernelRefusal(
                reason=RefusalReason.OBJECTIVE_TERMINAL,
                failed_check=KernelCheck.K1_OBJECTIVE_BINDING,
                attestor=None,
                remediable=False,
                detail=(
                    f"objective {record.objective_id!r} is "
                    f"{record.state.value}; a finished objective does not "
                    "become unfinished, and this action needs a new one"
                ),
            )

        return record

    # ---- §7.2 K2 · override state -------------------------------------

    def _check_override_state(self) -> KernelRefusal | None:
        """K2. `None` when autonomy is running.

        §7.2: *"Global suspension is not active. **Why the Kernel:** the
        Override's meaning **is** 'the Kernel stops minting.' No other
        component can express that."*

        §11.8 is precise about what suspension stops: **minting, and only
        minting.** Work already attempting runs to settlement, the
        Objective Engine keeps admitting, Mission Control keeps assigning,
        and work queues at the Kernel boundary. None of that is here,
        because none of it is the Kernel's.

        The refusal carries the founder's own words verbatim. §7.5: *"a
        thousand refusals are one state — 'autonomy is suspended; 1,000
        actions are waiting' — not a thousand queue items."* Identical
        suspensions therefore produce identical refusals, which is what
        lets a surface collapse them.
        """
        if not self._override.is_suspended:
            return None

        return KernelRefusal(
            reason=RefusalReason.OVERRIDE_ACTIVE,
            failed_check=KernelCheck.K2_OVERRIDE_STATE,
            attestor=None,
            remediable=True,
            detail=self._override.reason or "autonomy is suspended",
        )

    # ---- §7.4 · the precondition set, in order ------------------------

    def _check_preconditions(
        self, request: ExecutionRequest
    ) -> AdmissionRecord | KernelRefusal:
        """Everything that can refuse before the receipt write.

        §7.4's order for both action classes:

        ```
          local        K1 · K2 · A1 A2 A3 A4 A5 A6 · K3
          intelligence K1 · K2 · A1 A2 A3 A4 A5 A6 A7 A8 · K3
        ```

        This runs the first two groups and stops. **K3 is not here** — it
        needs an `IntentRecord`, and one field of that record has no
        source today (see the Part 4 health report's R35).

        §7.1 is why the order is fixed rather than incidental: *"Checks run
        cheapest-and-most-fundamental first, so a refusal costs as little
        as possible and the reason returned is the most fundamental one. An
        action with no objective is refused for having no objective, never
        for a budget problem it also had."*

        Returns the `AdmissionRecord` when everything passes, because the
        envelope it carries (§10.3) is what the mint will bound the warrant
        against.
        """
        admitted = self._check_objective_binding(request)
        if isinstance(admitted, KernelRefusal):
            return admitted

        suspended = self._check_override_state()
        if suspended is not None:
            return suspended

        unattested = self._verify_attestations(request)
        if unattested is not None:
            return unattested

        return admitted

    # ---- §7.3 · the eight attestations --------------------------------

    def _verify_attestations(
        self, request: ExecutionRequest
    ) -> KernelRefusal | None:
        """Verify every attestation §7.4 requires. `None` when all pass.

        §7.3, and this is the whole of it:

        > *"The Kernel verifies each attestation's **presence, attestor
        > identity, subject match, and freshness**. **It never re-derives
        > the verdict.** An attestation whose attestor is wrong, whose
        > subject does not match this request, or which is stale is
        > treated as absent."*

        **No attestor is called and no verdict is recomputed.** Every
        answer arrives inside the request; this reads them.

        §14 R3 is the risk this method exists against — *"if validation
        degrades to 'a field is present,' the Kernel becomes ceremony"* —
        so all four properties are checked, not just presence.

        Questions are checked in §7.3's table order and the **first**
        failure is returned, per §7.1: *"a refusal costs as little as
        possible and the reason returned is the most fundamental one."*
        """
        now = self._clock.now()
        supplied = {a.question: a for a in request.attestations}

        for question in _required_questions(request.action_class):
            attestation = supplied.get(question)

            if attestation is None:
                return self._attestation_absent(
                    question, "no attestation was supplied"
                )

            # §7.3's attestor-identity check. C7 makes a mis-attributed
            # attestation unconstructable (ED-019), so this cannot fail
            # through the public constructor — it is here because §7.3
            # assigns the check to the Kernel, and §14 R3 warns against
            # validation that thins out because something else covers it.
            if attestation.attestor != question.canonical_attestor:
                return self._attestation_absent(
                    question,
                    f"attributed to {attestation.attestor!r}, but "
                    f"{question.value!r} is answered by "
                    f"{question.canonical_attestor!r}",
                )

            # TODO(ADR-0022): when R34 is closed, the A2 subject becomes a
            # digest of (payload_digest, reversibility_class) and this
            # comparison binds the carried class to the registry's answer.
            # Until then the carried class is trusted, per ADR-0022.
            if attestation.subject != request.payload_digest:
                return self._attestation_absent(
                    question,
                    "attests to a different subject than this request",
                )

            if attestation.is_stale(now, DEFAULT_ATTESTATION_MAX_AGE):
                return self._attestation_absent(
                    question,
                    f"answered at {attestation.attested_at.isoformat()} and "
                    "is no longer fresh",
                )

            if attestation.verdict is AttestationVerdict.REFUSED:
                # Carried, never re-derived. §7.3.
                return KernelRefusal(
                    reason=RefusalReason.ATTESTATION_REFUSED,
                    failed_check=question,
                    attestor=question.canonical_attestor,
                    remediable=True,
                    detail=attestation.reason or "the attestor refused",
                )

        return None

    @staticmethod
    def _attestation_absent(
        question: AttestationQuestion, why: str
    ) -> KernelRefusal:
        """§7.3 — missing, mis-attributed, subject-mismatched and stale all
        arrive here, because all four *"are treated as absent."*

        `detail` says which of the four it was, so the record distinguishes
        them even though the reason does not. C8's ED-025 chose two
        attestation reasons rather than eight for exactly this division of
        labour: the reason says *what kind*, `failed_check` says *which
        question*, and `detail` says *why*.
        """
        return KernelRefusal(
            reason=RefusalReason.ATTESTATION_ABSENT,
            failed_check=question,
            attestor=question.canonical_attestor,
            remediable=True,
            detail=f"{question.value}: {why}",
        )

    # ---- the Intent lifecycle (§3.3) ----------------------------------

    def _register(self, warrant: Warrant) -> None:
        """Take a minted warrant into the outstanding set.

        Bookkeeping, not minting: the caller has already decided. §4.4 —
        *"Can two executions share one? **No.**"* — so a warrant enters
        once, and a second registration under one id is refused rather
        than silently replacing the first.
        """
        if not isinstance(warrant, Warrant):
            raise InvalidKernel("_register expects a Warrant")
        if warrant.warrant_id in self._outstanding:
            raise InvalidKernel(
                f"{warrant.warrant_id!r} is already outstanding; one warrant "
                "authorizes one logical action (§4.4)"
            )
        self._outstanding[warrant.warrant_id] = warrant

    def _is_outstanding(self, warrant_id: str) -> bool:
        """Whether a warrant is minted and not yet settled."""
        return warrant_id in self._outstanding

    # ---- reading owned state -----------------------------------------

    @property
    def override(self) -> OverrideSwitch:
        """The suspension state the Kernel owns (§3.3).

        An immutable value, so a reader cannot suspend autonomy by
        touching what it was handed. Changing it is `invalidate()`'s.
        """
        return self._override

    @property
    def outstanding_count(self) -> int:
        """How many minted intents have not yet settled.

        A count, not the warrants: §7.5's *"a thousand refusals are one
        state"* applies to outstanding work too, and handing out the
        collection would let a caller reach the Intent lifecycle §3.3
        assigns the Kernel.
        """
        return len(self._outstanding)
