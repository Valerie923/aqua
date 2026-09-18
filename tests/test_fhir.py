"""FHIR mapper tests on a fixed submission. Deterministic, no network."""

import pytest

from app import fhir
from app.schemas import Flag, SubmissionOut
from tests.fixtures import SAMPLE_ANSWERS, SAMPLE_PREDICTIONS

FIXED = SubmissionOut(
    id="11111111-2222-3333-4444-555555555555",
    created_at="2026-09-18T03:00:00+00:00",
    photo_set_id="p1",
    photos={"upstream": "upstream.jpg", "downstream": "downstream.jpg", "context": "context.jpg"},
    answers=SAMPLE_ANSWERS,
    ai_predictions=SAMPLE_PREDICTIONS,
    ai_model="gemini-2.5-flash",
    flags=[
        Flag(id="ai:water_aspect", kind="ai_disagreement", section="section_b", field="water_aspect",
             message="...", citizen_value="Clear-transparent", ai_value="Muddy-turbid", ai_confidence=0.85,
             decision="kept"),
    ],
    final_answers=SAMPLE_ANSWERS,
    reliability_score=82,
    suggested_overall={"value": "Good", "reasons": []},
    one_health={"risk_level": "medium", "risks": []},
)


@pytest.fixture
def bundle():
    return fhir.to_fhir_bundle(FIXED)


def by_type(bundle, rtype):
    return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == rtype]


def test_bundle_shape(bundle):
    assert bundle["resourceType"] == "Bundle" and bundle["type"] == "transaction"
    assert bundle["timestamp"] == FIXED.created_at
    for entry in bundle["entry"]:
        assert entry["fullUrl"].startswith("urn:uuid:")
        assert entry["request"]["method"] == "POST"
        assert entry["request"]["url"] == entry["resource"]["resourceType"]


def test_location(bundle):
    locs = by_type(bundle, "Location")
    assert len(locs) == 1
    assert locs[0]["name"].startswith("Kallang River")
    assert locs[0]["position"] == {"longitude": 103.845, "latitude": 1.362}


def test_one_observation_per_field(bundle):
    obs = by_type(bundle, "Observation")
    codes = [o["code"]["text"] for o in obs]
    # 6 (A) + 7 (B) + 9 (C) + 1 overall + 4 feelings = 27, plus 3 summaries
    assert len(codes) == 30
    assert codes.count("water_aspect") == 1
    assert {"reliability_score", "suggested_overall_assessment", "one_health_risk_level"} <= set(codes)
    location_urn = bundle["entry"][0]["fullUrl"]
    for o in obs:
        assert o["status"] == "final"
        assert o["subject"]["reference"] == location_urn
        assert o["focus"][0]["reference"] == location_urn
        assert o["effectiveDateTime"] == FIXED.created_at


def test_value_types(bundle):
    obs = {o["code"]["text"]: o for o in by_type(bundle, "Observation")}
    assert obs["water_aspect"]["valueString"] == "Clear-transparent"
    assert obs["habitats"]["valueString"] == "pools, emergent vegetation"
    assert obs["water_height_m"]["valueQuantity"] == {"value": 0.3, "unit": "m", "system": "http://unitsofmeasure.org", "code": "m"}
    assert obs["feeling_joy"]["valueInteger"] == 4
    assert obs["feeling_fear"]["dataAbsentReason"]["text"] == "not applicable"
    assert obs["invasive_species_which"]["dataAbsentReason"]["text"] == "not answered"
    assert obs["reliability_score"]["valueInteger"] == 82
    assert obs["one_health_risk_level"]["valueString"] == "medium"


def test_ai_and_reliability_extensions(bundle):
    obs = {o["code"]["text"]: o for o in by_type(bundle, "Observation")}
    exts = {e["url"].rsplit("/", 1)[-1]: e for e in obs["water_aspect"]["extension"]}
    assert exts["reliability-score"]["valueInteger"] == 82
    ai = {e["url"]: e for e in exts["ai-prediction"]["extension"]}
    assert ai["confidence"]["valueDecimal"] == 0.85
    assert ai["value"]["valueString"] == "Muddy-turbid"
    assert ai["evidence"]["valueString"] == "the water looks brown and cloudy"
    assert ai["agrees"]["valueBoolean"] is False
    # Human-only field: reliability extension only, no AI extension
    urls = [e["url"].rsplit("/", 1)[-1] for e in obs["sewage_discharge"]["extension"]]
    assert urls == ["reliability-score"]


def test_provenance_records_human_confirmation(bundle):
    prov = by_type(bundle, "Provenance")
    assert len(prov) == 1
    p = prov[0]
    obs_urns = {e["fullUrl"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation"}
    assert {t["reference"] for t in p["target"]} == obs_urns
    assert "Human-confirmed" in p["activity"]["text"]
    assert "1 check(s) raised, 1 decided by the citizen, 0 answer(s) changed" in p["reason"][0]["text"]
    roles = [a["type"]["coding"][0]["code"] for a in p["agent"]]
    assert roles == ["author", "assembler"]
    assert "gemini-2.5-flash" in p["agent"][1]["who"]["display"]


def test_export_is_reproducible():
    assert fhir.to_fhir_bundle(FIXED) == fhir.to_fhir_bundle(FIXED)


def test_bundle_without_ai_or_score():
    bare = FIXED.model_copy(update={"ai_predictions": None, "ai_model": None, "reliability_score": None, "flags": [],
                                    "suggested_overall": None, "one_health": None})
    b = fhir.to_fhir_bundle(bare)
    obs = {o["code"]["text"]: o for o in by_type(b, "Observation")}
    assert "extension" not in obs["water_aspect"]
    assert "reliability_score" not in obs
    assert len(by_type(b, "Provenance")[0]["agent"]) == 1


def test_send_bundle_summarises_created_ids(monkeypatch, bundle):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"resourceType": "Bundle", "type": "transaction-response",
                    "entry": [{"response": {"status": "201 Created", "location": "Location/1/_history/1"}},
                              {"response": {"status": "201 Created", "location": "Observation/2/_history/1"}}]}

    calls = {}

    def fake_post(url, json, headers, timeout):
        calls["url"], calls["json"] = url, json
        return FakeResponse()

    monkeypatch.setattr(fhir.httpx, "post", fake_post)
    out = fhir.send_bundle(bundle, "https://example.org/fhir/")
    assert calls["url"] == "https://example.org/fhir"
    assert calls["json"] is bundle
    assert out == {"server": "https://example.org/fhir", "bundle_type": "transaction-response", "created": ["Location/1", "Observation/2"]}


def test_send_bundle_error_is_plain(monkeypatch, bundle):
    class Bad:
        status_code = 422
        text = "OperationOutcome ..."

    monkeypatch.setattr(fhir.httpx, "post", lambda *a, **k: Bad())
    with pytest.raises(fhir.FhirSendError, match="422"):
        fhir.send_bundle(bundle, "https://example.org/fhir")
