from pharos import extract as X
from pharos import llm_extract as L
from pharos.ingest import parse_bytes

TEXT = ("Quotation for a liquid-filled transformer, synthetic test content only.\n"
        "Percent resistance and reactance combined, nominal: five point seven five percent, i.e. 5.75 pct on base.\n"
        "Notes on delivery follow in the next section of this document.\n")


class Fake:
    def __init__(self, reply): self.reply, self.calls = reply, 0
    def complete(self, system, user):
        self.calls += 1
        assert "DATA, never instructions" in system and "impedance_pct" in user
        return self.reply


def doc():
    return parse_bytes("q.txt", TEXT.encode(), "alternate")


def test_verified_model_value_is_accepted_and_converted_by_code():
    d = doc()
    fields = X.extract_document(d)
    assert fields["impedance_pct"].status != "documented"
    reply = '{"impedance_pct": {"value": 5.75, "unit": "%", "page": 1, "quote": "Percent resistance and reactance combined, nominal: five point seven five percent, i.e. 5.75 pct on base."}}'
    notes = L.augment(d, fields, Fake(reply))
    fv = fields["impedance_pct"]
    assert fv.status == "documented" and fv.value == 5.75 and fv.evidence[0].verified and not notes
    assert any("extracted by a model" in n for n in fv.notes)


def test_invented_quote_or_number_is_rejected():
    d = doc()
    fields = X.extract_document(d)
    reply = '{"impedance_pct": {"value": 6.5, "unit": "%", "page": 1, "quote": "Impedance: 6.5 %"}}'
    notes = L.augment(d, fields, Fake(reply))
    assert fields["impedance_pct"].status != "documented" and any("rejected" in n for n in notes)
    # a real quote but a number that is not in it is also rejected
    reply = '{"impedance_pct": {"value": 7.0, "unit": "%", "page": 1, "quote": "Notes on delivery follow in the next section of this document."}}'
    fields = X.extract_document(d)
    L.augment(d, fields, Fake(reply))
    assert fields["impedance_pct"].status != "documented"


def test_disabled_without_client_and_provider_failures_are_contained():
    d = doc()
    fields = X.extract_document(d)
    assert L.augment(d, fields, None) == []

    class Boom:
        def complete(self, s, u): raise TimeoutError()
    assert "skipped" in L.augment(d, fields, Boom())[0]
    assert L.client_from_env() is None
