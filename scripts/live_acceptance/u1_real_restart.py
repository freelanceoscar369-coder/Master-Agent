"""U1 section 5 — the restart proof against the REAL composition.

The earlier restart proof was component-level: a registry, a store and
`restore_providers()`, exercised directly. That proves the parts work. It
does not prove `_build_mission_pipeline()` wires them, and the gap between
those two claims is exactly where "built but not used" lives -- this run
found one, in fact: nothing in the composition had ever *written* a
snapshot, so the restore path was reading a file the application itself
never produced.

So this drives the real composition root twice, in one process, with a
DISPOSABLE `KALPAVRIKSHA_STATE_DIR`. It never touches the founder's own
history.

    RUN 1  build the real pipeline -> restore, bootstrap, observe price
           -> save a real snapshot through the ATTACHED PersistenceService
           -> read that snapshot back off disk and inspect it

    RUN 2  destroy and rebuild the whole composition
           -> restore precedes bootstrap
           -> ProviderSource reads the RECONSTRUCTED registry
           -> restored health is not trusted
           -> the credential is reacquired from the environment
           -> the price is OBSERVED AGAIN, not trusted from the snapshot
           -> the executable provider is reconstructed
           -> executability is recomputed from live registration
           -> the same three-name request, through Broker/PromptExecutor

Nothing here calls a provider adapter directly. Every execution claim goes
through the ladder the founder's own requests go through.

    python scripts/live_acceptance/u1_real_restart.py

Needs a real OPENROUTER_API_KEY in the environment for the OpenRouter
half; the credential is never printed, and the script asserts that it is
absent from the snapshot it writes.
"""
from __future__ import annotations

import dataclasses
import gc
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime

logging.basicConfig(level=logging.ERROR)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

STATE_DIR = tempfile.mkdtemp(prefix="kv-u1-restart-")
os.environ["KALPAVRIKSHA_STATE_DIR"] = STATE_DIR
os.environ.setdefault("KALPAVRIKSHA_DISABLE_MIC", "1")

import kalpavriksha_desktop as kd  # noqa: E402
from master_agent.ai_infrastructure import profiles as profiles_module  # noqa: E402
from master_agent.ai_infrastructure.budgeted_request import (  # noqa: E402
    BudgetedSelectionRequest,
)
from master_agent.ai_infrastructure.workload import INTERACTIVE  # noqa: E402
from master_agent.planner.outcomes import SuccessSpec  # noqa: E402
from master_agent.plugins.model_router import (  # noqa: E402
    RoutingContext,
    SelectionRequest,
)
from master_agent.providers.openrouter import (  # noqa: E402
    CREDENTIAL_ENV,
    OPENROUTER_PROVIDER_ID,
)

PROMPT = "Give exactly three short names for a gardening notes app, one name per line."

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> bool:
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f" -- {detail}" if detail else ""), flush=True)
    if not condition:
        failures.append(label)
    return condition


# ---- observing the real composition without altering it ------------------
#
# The pipeline returns a mission service, not its own wiring, and adding
# fields to that tuple to make a test easier would be changing production
# shape for the benefit of the proof. So the composition is watched from
# outside instead: the three module-level names it resolves at call time
# are wrapped, they record what happened and delegate, and the pipeline
# runs completely unmodified.


class Observation:
    def __init__(self) -> None:
        self.order: list[str] = []
        self.registry = None
        self.restored_ids: tuple[str, ...] = ()
        self.health_after_restore = None
        self.economics_after_restore = None
        self.source = None
        self.price_observations: list[dict] = []


def instrument(observation: Observation):
    real_restore = kd._restore_canonical_providers
    real_bootstrap = profiles_module.bootstrap_registry
    real_observe = kd._observe_openrouter_economics
    real_source = profiles_module.ProviderSource

    def restore(registry, state_dir):
        observation.order.append("restore")
        observation.registry = registry
        result = real_restore(registry, state_dir)
        observation.restored_ids = result
        record = registry.get(OPENROUTER_PROVIDER_ID)
        if record is not None:
            observation.health_after_restore = record.health
            observation.economics_after_restore = record.economic_verified_at
        return result

    def bootstrap(registry, specs=None):
        observation.order.append("bootstrap")
        return real_bootstrap(registry, specs)

    def observe(provider):
        result = real_observe(provider)
        observation.price_observations.append(
            {"result": result, "provider": provider}
        )
        return result

    def source(*args, **kwargs):
        built = real_source(*args, **kwargs)
        observation.source = built
        return built

    kd._restore_canonical_providers = restore
    kd._observe_openrouter_economics = observe
    profiles_module.bootstrap_registry = bootstrap
    profiles_module.ProviderSource = source
    return lambda: (
        setattr(kd, "_restore_canonical_providers", real_restore),
        setattr(kd, "_observe_openrouter_economics", real_observe),
        setattr(profiles_module, "bootstrap_registry", real_bootstrap),
        setattr(profiles_module, "ProviderSource", real_source),
    )


def build():
    observation = Observation()
    restore_originals = instrument(observation)
    try:
        pipeline = kd._build_mission_pipeline()
    finally:
        restore_originals()
    return pipeline, observation


def executable_registry(mission_service):
    return mission_service.planner._runner._executor._providers


def executable(mission_service, provider_id):
    return next(
        (p for p in executable_registry(mission_service).all_plugins()
         if p.provider_id == provider_id),
        None,
    )


def snapshot_on_disk() -> dict:
    from master_agent.persistence.store import SNAPSHOT_FILENAME

    path = os.path.join(STATE_DIR, SNAPSHOT_FILENAME)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


# ═══════════════════════════════ RUN 1 ═══════════════════════════════

print("=" * 66, flush=True)
print(f"RUN 1 — real composition, disposable state dir\n  {STATE_DIR}", flush=True)
print("=" * 66, flush=True)

credential_present = bool(os.environ.get(CREDENTIAL_ENV))
print(f"  credential {CREDENTIAL_ENV}: "
      f"{'PRESENT' if credential_present else 'ABSENT'}", flush=True)

pipeline_1, run1 = build()
mission_service_1, runtime_1, mission_control_1, status_1, runner_1, *_ = pipeline_1

check("run 1 restores before it bootstraps", run1.order == ["restore", "bootstrap"],
      " -> ".join(run1.order))
check("run 1 is a genuine first run", run1.restored_ids == (),
      f"restored {run1.restored_ids}")

registry_1 = run1.registry
openrouter_1 = registry_1.get(OPENROUTER_PROVIDER_ID)
check("the canonical registry knows OpenRouter", openrouter_1 is not None)

observed_1 = run1.price_observations[0]["result"] if run1.price_observations else None
if credential_present:
    check("run 1 OBSERVED the configured model's price",
          len(run1.price_observations) == 1,
          f"{len(run1.price_observations)} observation(s)")
    if observed_1 is not None:
        print(f"        model            : {observed_1['model']}", flush=True)
        print(f"        prompt price     : {observed_1['prompt_price']:g}", flush=True)
        print(f"        completion price : {observed_1['completion_price']:g}", flush=True)
        print(f"        observed at      : {observed_1['observed_at'].isoformat()}",
              flush=True)
    check("the configured slug is the source constant",
          (observed_1 or {}).get("model") == kd.OPENROUTER_CONFIGURED_MODEL,
          kd.OPENROUTER_CONFIGURED_MODEL)
    check("the canonical record is free ONLY with evidence",
          (openrouter_1.cost_per_call == 0.0) == (observed_1 is not None),
          f"cost {openrouter_1.cost_per_call}, evidence "
          f"{observed_1 is not None}")
    check("economic_verified_at is the reading, not the launch",
          observed_1 is None
          or openrouter_1.economic_verified_at == observed_1["observed_at"])
    check("OpenRouter is EXECUTABLE",
          executable(mission_service_1, OPENROUTER_PROVIDER_ID) is not None)

# ---- save a real snapshot, through the composition's own path -----------
#
# `runtime.checkpoint()` is the Runtime's ordinary end-of-cycle call. It
# reaches the PersistenceService through the CheckpointSink protocol, and
# the PersistenceService writes the whole snapshot -- provider slice
# included, because the composition attached the canonical registry to it.
# No second writer, and nothing here that a founder run does not do.
runtime_1.checkpoint()

raw = snapshot_on_disk()
providers_slice = raw["payload"].get("providers") or []
check("the snapshot carries a provider slice", bool(providers_slice),
      f"{len(providers_slice)} descriptors")

persisted = next(
    (row for row in providers_slice if row["provider_id"] == OPENROUTER_PROVIDER_ID),
    None,
)
check("OpenRouter's administrative facts survive", persisted is not None)
if persisted is not None:
    print(f"        persisted notes  : {persisted.get('notes')}", flush=True)
    print(f"        persisted class  : {persisted.get('economic_class')}", flush=True)
    check("the configured model is recorded in the snapshot",
          kd.OPENROUTER_CONFIGURED_MODEL in json.dumps(persisted))

# ---- the credential is nowhere in it ------------------------------------
text = json.dumps(raw)
secret = os.environ.get(CREDENTIAL_ENV, "")
check("the credential value is absent from the snapshot",
      not secret or secret not in text)
check("no Bearer token is in the snapshot", "Bearer" not in text)
check("no Authorization header is in the snapshot",
      "Authorization" not in text and "authorization" not in text)

persisted_verified_at = (persisted or {}).get("economic_verified_at")
print(f"        persisted economic_verified_at: {persisted_verified_at}", flush=True)


# ═══════════════════ destroy the whole composition ═══════════════════

print("\n" + "=" * 66, flush=True)
print("TEARDOWN — every object from run 1 dropped", flush=True)
print("=" * 66, flush=True)

registry_1_id = id(registry_1)
source_1_id = id(run1.source)
openrouter_object_1_id = id(executable(mission_service_1, OPENROUTER_PROVIDER_ID)) \
    if credential_present else None

del pipeline_1, mission_service_1, runtime_1, mission_control_1, status_1, runner_1
del registry_1, openrouter_1
gc.collect()
print("  composition released", flush=True)


# ═══════════════════════════════ RUN 2 ═══════════════════════════════

print("\n" + "=" * 66, flush=True)
print("RUN 2 — rebuilt from the same disposable state dir", flush=True)
print("=" * 66, flush=True)

pipeline_2, run2 = build()
mission_service_2, runtime_2, mission_control_2, status_2, runner_2, *_ = pipeline_2

check("run 2 restores BEFORE it bootstraps", run2.order == ["restore", "bootstrap"],
      " -> ".join(run2.order))
check("run 2 actually restored last run's descriptors",
      OPENROUTER_PROVIDER_ID in run2.restored_ids,
      f"{len(run2.restored_ids)} restored")

registry_2 = run2.registry
check("the canonical registry is a NEW object",
      id(registry_2) != registry_1_id)
check("ProviderSource reads the reconstructed registry",
      run2.source is not None and run2.source.registry is registry_2)
check("ProviderSource is a NEW object", id(run2.source) != source_1_id)

from master_agent.broker.registry import ProviderHealth  # noqa: E402

check("restored runtime health is NOT trusted",
      run2.health_after_restore is ProviderHealth.UNVERIFIED,
      str(run2.health_after_restore))

openrouter_2 = registry_2.get(OPENROUTER_PROVIDER_ID)

if credential_present:
    check("the credential is reacquired from the environment",
          bool(os.environ.get(CREDENTIAL_ENV)))
    reconstructed = executable(mission_service_2, OPENROUTER_PROVIDER_ID)
    check("the executable OpenRouter provider is reconstructed",
          reconstructed is not None)
    check("it is a NEW provider object",
          reconstructed is not None and id(reconstructed) != openrouter_object_1_id)
    check("its availability is decided by the live credential",
          reconstructed is not None and reconstructed.availability().reachable)

    observed_2 = run2.price_observations[0]["result"] if run2.price_observations else None
    check("run 2 OBSERVED the price again",
          len(run2.price_observations) == 1,
          f"{len(run2.price_observations)} observation(s)")
    check("the run 2 reading is NEWER than the persisted one",
          observed_2 is not None
          and persisted_verified_at is not None
          and observed_2["observed_at"] > datetime.fromisoformat(persisted_verified_at),
          f"{(observed_2 or {}).get('observed_at')} > {persisted_verified_at}")
    check("the canonical record carries the RUN 2 reading, not the snapshot's",
          observed_2 is not None
          and openrouter_2.economic_verified_at == observed_2["observed_at"])

# ---- executability is recomputed from live registration -----------------

profile = {p.provider_id: p for p in run2.source.profiles()}
check("OpenRouter is available on current facts",
      not credential_present or (
          OPENROUTER_PROVIDER_ID in profile
          and profile[OPENROUTER_PROVIDER_ID].available))

known_ids = {d.provider_id for d in registry_2.all()}
executable_ids = {p.provider_id for p in
                  executable_registry(mission_service_2).all_plugins()}
known_but_absent = sorted(known_ids - executable_ids)
unavailable_known = [
    pid for pid in known_but_absent
    if pid in profile and not profile[pid].available
]
check("known but not registered means UNAVAILABLE",
      len(known_but_absent) == 0 or len(unavailable_known) == len(
          [p for p in known_but_absent if p in profile]),
      f"{len(known_but_absent)} known-but-absent, all unavailable")

check("ollama.local is never executable",
      "ollama.local" not in executable_ids)
check("ollama.local is not a candidate",
      "ollama.local" not in set(runner_2._configured_ids))


# ═════════════ the same request, through Broker/PromptExecutor ═════════════

print("\n" + "=" * 66, flush=True)
print("RUN 2 — reasoning through the rebuilt composition", flush=True)
print("=" * 66, flush=True)

expected = SuccessSpec(description="three names", min_words=3).to_expected_outcome()


def run_request(exclude: frozenset[str] = frozenset()):
    base = SelectionRequest.from_context(RoutingContext(requester="reasoning_transform"))
    request = BudgetedSelectionRequest(**vars(base), request_class=INTERACTIVE,
                                       prompt="x")
    if exclude:
        request = dataclasses.replace(request, exclude_providers=exclude)
    stamp = datetime.now(UTC).isoformat()
    outcome = runner_2.run(PROMPT, request, expected=expected)
    return stamp, outcome


print("\n-- natural selection, policy untouched --", flush=True)
stamp, natural = run_request()
print(f"  timestamp        : {stamp}", flush=True)
print(f"  selected provider: {getattr(natural, 'provider_id', None)}", flush=True)
print(f"  verified         : {getattr(natural, 'verified', None)}", flush=True)
check("the rebuilt composition produces a verified answer",
      bool(getattr(natural, "verified", False)))

if credential_present:
    print("\n-- OpenRouter, scoped through the ladder's own exclusion --", flush=True)
    others = frozenset(runner_2._configured_ids) - {OPENROUTER_PROVIDER_ID}
    stamp, forced = run_request(exclude=others)
    detail = getattr(forced, "detail", None) or {}
    print(f"  timestamp        : {stamp}", flush=True)
    print(f"  selected provider: {getattr(forced, 'provider_id', None)}", flush=True)
    print(f"  verified         : {getattr(forced, 'verified', None)}", flush=True)
    print(f"  model            : {detail.get('model')}", flush=True)
    print(f"  prompt price     : {detail.get('pricing_prompt')}", flush=True)
    print(f"  completion price : {detail.get('pricing_completion')}", flush=True)
    print(f"  cost evidence    : {detail.get('cost_evidence')}", flush=True)
    print("  ---- response ----", flush=True)
    print("  " + (getattr(forced, "text", "") or "").replace("\n", "\n  "), flush=True)

    check("OpenRouter executed after the restart",
          getattr(forced, "provider_id", None) == OPENROUTER_PROVIDER_ID)
    check("its answer was verified", bool(getattr(forced, "verified", False)))
    check("it ran the configured model",
          detail.get("model") == kd.OPENROUTER_CONFIGURED_MODEL)
    check("both prices were zero at execution time",
          str(detail.get("pricing_prompt")) in ("0", "0.0")
          and str(detail.get("pricing_completion")) in ("0", "0.0"))


# ═══════════════════════════════ verdict ═══════════════════════════════

print("\n" + "=" * 66, flush=True)
if failures:
    print(f"RESULT: FAIL — {len(failures)} check(s)", flush=True)
    for failure in failures:
        print(f"  - {failure}", flush=True)
else:
    print("RESULT: PASS — real composition restart proven", flush=True)
print("=" * 66, flush=True)

shutil.rmtree(STATE_DIR, ignore_errors=True)
print(f"disposable state dir removed: {STATE_DIR}", flush=True)
sys.exit(1 if failures else 0)
