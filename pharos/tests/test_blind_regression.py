"""Guard: the blind scenarios that pass after the post-first-run fixes keep passing. This is a regression
check, not an accuracy claim: the fixes were tuned on this set (see docs/BLIND_EVAL.md)."""
from pharos.blind_eval import BLIND, run

KNOWN_FAILING = {"eskerhal-04", "fenwick-01", "fenwick-03", "kestrel-01", "kestrel-03", "kestrel-04"}


def test_no_regression_on_blind_set():
    if not BLIND.exists():
        return
    res = run("regression")
    failing = {r["id"] for r in res["scenarios"] if not r["scenario_ok"]}
    assert failing <= KNOWN_FAILING, sorted(failing - KNOWN_FAILING)
    assert res["totals"]["items_ok"] >= 127
