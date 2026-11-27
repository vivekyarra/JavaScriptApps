from pharos import core
from pharos.schemas import CaseInput
from pharos.store import Store


def test_sent_state_is_saved_and_survives_a_new_decision_version(tmp_path):
    st = Store(str(tmp_path / "c.db"))
    core.set_default_store(st)
    d = core.decide_and_ask(CaseInput(package_dir="samples/dev/dev-01-oakridge", case_id="cq"), st)
    q = d.engineer_questions[0]
    st.set_clarification("cq", q, "Engineer of record", True)
    again = Store(str(tmp_path / "c.db"))
    assert again.clarification_state("cq")[again.question_key(q)] is True
    # a later version that raises the same question keeps its saved state
    d2 = core.decide_and_ask(CaseInput(case_id="cq", recovery_target_weeks=2), st)
    assert d2.version == 2 and q in d2.engineer_questions
    assert st.clarification_state("cq")[st.question_key(q)] is True


def test_api_round_trip(monkeypatch):
    from fastapi.testclient import TestClient
    from pharos.api import app

    core.set_default_store(Store(":memory:"))
    c = TestClient(app)
    assert c.post("/api/cases/from-sample", data={"sample_id": "dev/dev-01-oakridge", "case_id": "cq2"}).status_code == 200
    items = c.get("/api/cases/cq2/clarifications").json()
    assert items and not any(i["sent"] for i in items)
    first = items[0]
    r = c.post("/api/cases/cq2/clarifications", json={"question": first["question"], "party": first["party"], "sent": True})
    assert r.status_code == 200
    assert next(i for i in c.get("/api/cases/cq2/clarifications").json() if i["qkey"] == first["qkey"])["sent"] is True
    assert c.post("/api/cases/nope/clarifications", json={"question": "x", "party": "Vendor", "sent": True}).status_code == 404
