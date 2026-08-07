the output length limit. Continue exactly where you left off. Do not restart or repeat prior text. Finish the answer directly.]

| Priority | Component | Effort | Dependencies |
|----------|-----------|--------|--------------|
| **1** | Intent Layer | Medium | Planner exists; needs real parsing/clarification |
| **2** | Planner wiring to `cli.py` | Low | Planner exists; `MissionService.start()` exists |
| **3** | ExpectedOutcome in `cli.py` path | Low | Planner produces it; need `CapabilityCall` → `MissionPlan` |
| **4** | Reporter module | Medium | New module; Brain interface |
| **5** | MissionManager wiring | Low | `MissionManager.transition()` exists; needs live path |
| **6** | Verification per step in `cli.py` | Low | Runtime `_verify()` exists; needs `ExpectedOutcome` |

---

## Wiring Paths Comparison

| Path | Planner Used? | ExpectedOutcome? | Verification? | MissionPlan? |
|------|---------------|------------------|---------------|--------------|
| **Founder (`kalpavriksha`)** | ✅ Yes | ✅ Per step | ✅ Runtime | ✅ MissionPlan |
| **Demo (`cli.py`)** | ❌ No (regex) | ❌ No | ❌ None | ❌ CapabilityCall |

---

*Generated from verified sources only. Scores based on frozen Constitution and implementation evidence only.*