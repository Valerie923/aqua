import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.routers import analyze as analyze_router
from app.vision.base import VisionUnavailable
from tests.fixtures import SAMPLE_ANSWERS, SAMPLE_PREDICTIONS


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def _jpeg(color=(120, 90, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="JPEG")
    return buf.getvalue()


class FakeProvider:
    """Stands in for Claude in tests: returns the fixed sample predictions."""

    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def analyse(self, photos):
        self.calls.append([p.role for p in photos])
        return SAMPLE_PREDICTIONS


def test_health_and_form_options(client):
    assert client.get("/api/health").json()["ok"] is True
    opts = client.get("/api/form-options").json()
    assert "channel_form" in opts and "human_only_fields" in opts
    assert len(client.get("/api/sites").json()) >= 3


def test_analyze_without_api_key_is_honest(client):
    files = {"upstream": ("up.jpg", _jpeg(), "image/jpeg")}
    r = client.post("/api/analyze", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["ai_available"] is False
    assert body["predictions"] is None
    assert "not configured" in body["error"]
    assert body["photos"] == {"upstream": "upstream.jpg"}


def test_analyze_with_provider_and_submit(client, monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(analyze_router, "get_provider", lambda: fake)

    files = {
        "upstream": ("up.jpg", _jpeg(), "image/jpeg"),
        "downstream": ("down.jpg", _jpeg((60, 90, 120)), "image/jpeg"),
        "context": ("ctx.jpg", _jpeg((10, 120, 30)), "image/jpeg"),
    }
    r = client.post("/api/analyze", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ai_available"] is True
    assert body["model"] == "fake-model"
    assert body["predictions"]["water_aspect"]["value"] == "Muddy-turbid"
    assert fake.calls == [["upstream", "downstream", "context"]]
    assert "water_withdrawal" in body["human_only"]

    # stored photos are served back
    assert client.get(f"/uploads/{body['photo_set_id']}/upstream.jpg").status_code == 200

    # submission picks up the server-side predictions
    r = client.post(
        "/api/submissions",
        json={"photo_set_id": body["photo_set_id"], "answers": SAMPLE_ANSWERS.model_dump(mode="json")},
    )
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["ai_predictions"]["water_aspect"]["evidence"] == "the water looks brown and cloudy"
    assert sub["answers"]["site"]["name"].startswith("Kallang")

    assert client.get(f"/api/submissions/{sub['id']}").status_code == 200
    assert any(s["id"] == sub["id"] for s in client.get("/api/submissions").json())


def test_analyze_provider_error_does_not_break_form(client, monkeypatch):
    class Broken:
        name = "broken"

        def analyse(self, photos):
            raise VisionUnavailable("The AI service is busy. Please try again in a minute.")

    monkeypatch.setattr(analyze_router, "get_provider", lambda: Broken())
    r = client.post("/api/analyze", files={"context": ("c.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["ai_available"] is False
    assert "busy" in r.json()["error"]


def test_submission_without_photos(client):
    r = client.post("/api/submissions", json={"answers": SAMPLE_ANSWERS.model_dump(mode="json")})
    assert r.status_code == 201
    assert r.json()["ai_predictions"] is None


def test_submission_rejects_bad_option(client):
    data = SAMPLE_ANSWERS.model_dump(mode="json")
    data["section_a"]["bottom_type"] = "Concrete"
    r = client.post("/api/submissions", json={"answers": data})
    assert r.status_code == 422


def test_provider_selection_follows_api_keys(monkeypatch):
    from app import config
    from app import vision

    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
    assert vision.provider_name() == "none"
    assert vision.get_provider().name == "none"

    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    assert vision.provider_name() == "gemini"
    assert vision.model_name() == "gemini-2.5-flash"
    assert vision.get_provider().model == "gemini-2.5-flash"

    monkeypatch.setattr(config, "VISION_MODEL", "gemini-2.5-pro")
    assert vision.get_provider().model == "gemini-2.5-pro"


def test_gemini_schema_is_accepted_by_sdk():
    """The SDK must be able to turn VisionPredictions into a Gemini response schema."""
    from google.genai import _transformers, types
    from app.schemas import VisionPredictions

    schema = _transformers.t_schema(None, VisionPredictions)
    assert isinstance(schema, types.Schema)
    assert set(schema.required or []) >= {"channel_form", "water_aspect", "vegetation_type_right"}


def test_check_and_submit_with_audit_trail(client, monkeypatch):
    fake = FakeProvider()
    monkeypatch.setattr(analyze_router, "get_provider", lambda: fake)
    r = client.post("/api/analyze", files={
        "upstream": ("u.jpg", _jpeg(), "image/jpeg"),
        "downstream": ("d.jpg", _jpeg(), "image/jpeg"),
        "context": ("c.jpg", _jpeg(), "image/jpeg"),
    })
    photo_set_id = r.json()["photo_set_id"]
    answers = SAMPLE_ANSWERS.model_dump(mode="json")

    # After section B: the AI disagrees on water aspect.
    partial = {"section_a": answers["section_a"], "section_b": answers["section_b"]}
    r = client.post("/api/check", json={"photo_set_id": photo_set_id, "answers": partial, "flags": []})
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [f["id"] for f in body["flags"]]
    assert ids == ["ai:water_aspect"]
    assert body["reliability"]["ai_available"] is True

    # Citizen keeps their answer; re-check keeps the decision.
    flag = body["flags"][0]
    flag["decision"] = "kept"
    r = client.post("/api/check", json={"photo_set_id": photo_set_id, "answers": answers, "flags": [flag]})
    assert r.json()["flags"][0]["decision"] == "kept"

    # Submit with the audit trail; server computes the score.
    r = client.post("/api/submissions", json={
        "photo_set_id": photo_set_id, "answers": answers, "final_answers": answers, "flags": [flag],
    })
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["flags"][0]["decision"] == "kept"
    assert 0 <= sub["reliability_score"] <= 100
    assert sub["reliability"]["score"] == sub["reliability_score"]
    assert [c["name"] for c in sub["reliability"]["components"]] == ["AI agreement", "Photos", "Consistency"]


def test_check_without_photos_still_runs_rules(client):
    answers = SAMPLE_ANSWERS.model_dump(mode="json")
    answers["section_b"]["water_height_m"] = 0.5
    answers["section_a"]["water_flow"] = "Dry"
    r = client.post("/api/check", json={"answers": answers})
    body = r.json()
    assert [f["id"] for f in body["flags"]] == ["rule:dry_but_water_height"]
    assert body["reliability"]["ai_available"] is False


def test_submission_score_ignores_client_supplied_value(client):
    answers = SAMPLE_ANSWERS.model_dump(mode="json")
    r = client.post("/api/submissions", json={"answers": answers, "reliability_score": 100})
    assert r.status_code == 201
    # No AI, 0 photos: score comes from the server formula, not the request.
    assert r.json()["reliability_score"] == round(100 * 27 / 50)


def test_check_and_submission_carry_insights(client):
    answers = SAMPLE_ANSWERS.model_dump(mode="json")
    answers["section_b"]["sewage_discharge"] = "yes"
    r = client.post("/api/check", json={"answers": answers})
    body = r.json()
    assert body["suggested_overall"]["value"] == "Poor"
    assert body["one_health"]["risk_level"] == "high"

    r = client.post("/api/submissions", json={"answers": answers})
    sub = r.json()
    assert sub["suggested_overall"]["value"] == "Poor"
    assert [x["id"] for x in sub["one_health"]["risks"]][0] == "mosquito_breeding"
    assert sub["one_health"]["risk_level"] == "high"
    listed = client.get("/api/submissions").json()
    assert next(x for x in listed if x["id"] == sub["id"])["one_health"]["risk_level"] == "high"


def test_fhir_export_and_send(client, monkeypatch):
    from app import fhir as fhir_mod

    r = client.post("/api/submissions", json={"answers": SAMPLE_ANSWERS.model_dump(mode="json")})
    sid = r.json()["id"]

    r = client.get(f"/api/submissions/{sid}/fhir")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/fhir+json")
    assert "attachment" in r.headers["content-disposition"]
    bundle = r.json()
    assert bundle["resourceType"] == "Bundle" and bundle["entry"][0]["resource"]["resourceType"] == "Location"

    monkeypatch.setattr(fhir_mod, "send_bundle", lambda b, url: {"server": url, "bundle_type": "transaction-response", "created": ["Location/9"]})
    from app.routers import fhir_export
    monkeypatch.setattr(fhir_export, "send_bundle", lambda b, url: {"server": url, "bundle_type": "transaction-response", "created": ["Location/9"]})
    r = client.post(f"/api/submissions/{sid}/fhir/send")
    assert r.status_code == 200, r.text
    assert r.json()["created"] == ["Location/9"]

    monkeypatch.setattr(fhir_export, "send_bundle", lambda b, url: (_ for _ in ()).throw(fhir_mod.FhirSendError("Could not reach the FHIR server")))
    r = client.post(f"/api/submissions/{sid}/fhir/send")
    assert r.status_code == 502 and "Could not reach" in r.json()["detail"]

    assert client.get("/api/submissions/nope/fhir").status_code == 404
