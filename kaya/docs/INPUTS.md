# Inputs

## Document roles

| role | what it is | notes |
| --- | --- | --- |
| `spec` | the buyer's specification | requirements; "not less than", "maximum" and `±x %` tolerances are understood |
| `original` | baseline equipment documents (the approved unit) | what the alternate is compared against |
| `alternate` | the supplier's submittal for the substitute | required |
| `logistics` | site limits: freight elevator, floor loading, door, overhead clearance, cooling | or pass the same values as `project_facts` |
| `schedule` | project schedule (JSON) | needed for `decide_and_ask` to answer a recovery target |

Text-based PDFs and `.txt` are supported. A page with no text layer is marked unreadable and never guessed at.

## `manifest.json` (a package folder)

```json
{
  "id": "dev-01-oakridge",
  "title": "Oakridge data hall: transformer T1 alternate",
  "recovery_target_weeks": 4,
  "documents": [
    {"role": "spec", "path": "spec.pdf"},
    {"role": "original", "path": "original.pdf"},
    {"role": "alternate", "path": "alternate.pdf"},
    {"role": "logistics", "path": "logistics.pdf"},
    {"role": "schedule", "path": "schedule.json"}
  ],
  "revisions": [{"label": "B", "documents": [{"role": "alternate", "path": "alternate_revB.pdf", "revision": "B"}]}]
}
```

## `schedule.json`

All times are project weeks (week 0 = order release unless `order_release_week` says otherwise).

```json
{
  "milestone": {"name": "Energization", "install_test_weeks": 12},
  "order_release_week": 0,
  "submittal_approval_weeks": 4,
  "substituted_item": "T1",
  "substituted_item_label": "transformer",
  "items": [
    {"id": "T1", "name": "Main transformer T1", "baseline_arrival_week": 82, "requires": true},
    {"id": "SWGR1", "name": "Main switchgear SWGR-1", "arrival_week": 80, "vendor": "Switchgear vendor", "requires": true}
  ],
  "alternate_routes": [{"description": "mobile crane lift", "ready_week": 40, "source": "Quote CR-114"}],
  "remediation": [{"description": "hatch lift", "weeks": 3, "cost": {"amount": 18500, "currency": "USD", "source": "Quote CR-114"}}],
  "recovery_target_weeks": 4
}
```

* The alternate's arrival is `order_release_week + lead time`, plus `submittal_approval_weeks` when its lead time counts from approved drawings. If the quote does not say which, both cases are computed and the answer states the range.
* `alternate_routes[].ready_week` is only used when a physical blocker (for example an elevator limit) is found; without a dated alternative the recovery is reported as potential, not promised.
* A `cost` is reported only when it has a `source`.

## `project_facts`

```json
{"elevator_capacity_kg": 3600, "slab_limit_kg_m2": 3000, "door_width_mm": 2400, "door_height_mm": 2600,
 "ceiling_clearance_mm": 3000, "cooling_capacity_kw": 20, "schedule": { "...": "as above" }}
```

If a logistics document and a project fact disagree, the value is treated as `conflicting` and not used.
