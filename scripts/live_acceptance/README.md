# Live acceptance runners

**These are not tests. They are not run by pytest and must not be.** Each one
drives the real Founder Edition pipeline with real side effects — real provider
quota, a real visible browser, real files on the founder's Desktop. That is the
point of them: §30 of the canonical convergence brief is explicit that *"Founder
Edition is not complete because tests are green."*

Run one deliberately, read what it prints, and record the result in
`docs/CONVERGENCE_HANDOFF.md`.

```bash
python scripts/live_acceptance/b_medium_golden_mission.py
```

## Safety

Every runner here pins `KALPAVRIKSHA_FMEA_REASONING_TIER=gemini`, which scopes the
reasoning ladder to Gemini alone. Without it a 429 mid-run falls through to the
desktop AI applications exactly as the product should — and on one recorded
occasion launched twenty-three ChatGPT/Kimi/Perplexity processes on the founder's
machine before anything could stop it. Correct product behaviour, unacceptable
harness behaviour. See `kalpavriksha_desktop.py`'s own comment at the ladder.

They also set `KALPAVRIKSHA_DISABLE_MIC=1` so a harness never listens to the room.

## What each one covers

| Runner | Brief § | Proves |
|---|---|---|
| `b_medium_golden_mission.py` | §30 B | Founder → Intent → Planner → Mission Control → Runtime → Worker → Verification → Evidence → Reporter → Founder, with a real browser observation binding into a later step |
| `c_founder_checkpoint.py` | §30 C | The founder's own "show me before you write it", planned by Gemini. **Needs quota.** |
| `c2_checkpoint_mechanism.py` | §30 C | The checkpoint *mechanism*, on a hand-authored plan — no quota. Continue resumes the same payload; Stop does not execute the mutation. |
| `e_persistence_recovery.py` | §30 E | That the record survives the process that wrote it, and that the audit is truthful. Reports resume-after-restart as unwired rather than claiming it. No quota needed. |
| `d_permission_gate.py` | §30 D | An irreversible capability holds at the boundary, executes nothing before approval, and really happens afterwards. |

## Reading the result

The runner verifies **independently**, by reading the disk after the mission
claims to be done — never by trusting the mission's own report. `LIVE ACCEPTANCE
B: PASS` means the folder and file were observed to exist with the observed page
title and final URL in them, not that the pipeline said so.

A `PASS` leaves its artifact folder on the Desktop on purpose: it is the evidence.
Delete it by hand once you have looked at it.
