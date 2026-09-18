"""HL7 FHIR R4 export (Track 7).

One submission -> one transaction Bundle:
  - Location           the site (name + GPS position)
  - Observation x N    one per form field, code.text = field name, value as
                       valueString / valueQuantity / valueInteger, subject -> Location.
                       Extensions carry the AI confidence + evidence for that field
                       and the submission's reliability score.
  - Observation x 3    reliability_score, suggested_overall_assessment, one_health_risk_level
  - Provenance         records that a human confirmed the values after an AI-assisted check

A transaction Bundle can be downloaded as-is or POSTed to any FHIR server; the
server resolves the urn:uuid references and assigns real IDs.
"""

import uuid

import httpx

from app import config
from app.schemas import AI_READABLE_FIELDS, SubmissionOut

EXT_BASE = "https://streamcheck.app/fhir/StructureDefinition"
FIELD_SYSTEM = "https://streamcheck.app/fhir/CodeSystem/oneaquahealth-form"

# Human-readable display names for the field codes.
FIELD_DISPLAY = {
    "channel_form": "Channel form",
    "bottom_type": "Bottom type",
    "bank_type": "Bank type",
    "habitats": "Habitats",
    "natural_debris": "Natural debris",
    "water_flow": "Water flow",
    "water_aspect": "Water aspect",
    "water_withdrawal": "Water withdrawal",
    "barriers": "Barriers (dams or transversal artificial barriers)",
    "draining_pipes": "Pipes draining polluted water",
    "sewage_discharge": "Sewage discharge",
    "construction": "Works in stream",
    "water_height_m": "Water height",
    "impervious_left": "Impervious surface, left riparian zone",
    "impervious_right": "Impervious surface, right riparian zone",
    "vegetation_left": "Vegetation, left riparian zone",
    "vegetation_right": "Vegetation, right riparian zone",
    "vegetation_type_left": "Vegetation type, left riparian zone",
    "vegetation_type_right": "Vegetation type, right riparian zone",
    "invasive_species": "Invasive species present",
    "invasive_species_which": "Invasive species (which)",
    "vegetation_cuts": "Recent vegetation cuts on banks",
    "overall_assessment": "Overall assessment",
    "feeling_joy": "Feeling: joy",
    "feeling_serenity": "Feeling: serenity",
    "feeling_anger": "Feeling: anger",
    "feeling_fear": "Feeling: fear",
}


def _urn(resource_id: str) -> str:
    return f"urn:uuid:{resource_id}"


def _stable_uuid(submission_id: str, name: str) -> str:
    """Same submission + same field -> same UUID, so exports are reproducible."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"streamcheck/{submission_id}/{name}"))


def _value_element(field: str, value) -> dict:
    """Pick the right FHIR value[x] for a form value."""
    if value is None or value == "":
        return {"dataAbsentReason": {"text": "not answered"}}
    if field == "water_height_m":
        return {"valueQuantity": {"value": float(value), "unit": "m", "system": "http://unitsofmeasure.org", "code": "m"}}
    if field.startswith("feeling_"):
        if value == "not_applicable":
            return {"dataAbsentReason": {"text": "not applicable"}}
        return {"valueInteger": int(value)}
    if isinstance(value, list):
        return {"valueString": ", ".join(value) if value else "none"}
    return {"valueString": str(value)}


def _field_values(final_answers: dict) -> list[tuple[str, object]]:
    """Flatten the final answers into (field, value) pairs in form order."""
    out: list[tuple[str, object]] = []
    for section in ("section_a", "section_b", "section_c", "section_d"):
        for field, value in final_answers[section].items():
            if field == "feelings":
                for feeling, score in value.items():
                    out.append((f"feeling_{feeling}", score))
            else:
                out.append((field, value))
    return out


def _observation(sub_id: str, name: str, display: str, value_element: dict, when: str, location_urn: str, extensions: list[dict]) -> dict:
    obs = {
        "resourceType": "Observation",
        "id": _stable_uuid(sub_id, name),
        "status": "final",
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "survey", "display": "Survey"}]}],
        "code": {"coding": [{"system": FIELD_SYSTEM, "code": name, "display": display}], "text": name},
        "subject": {"reference": location_urn, "display": "Assessed stream site"},
        "focus": [{"reference": location_urn}],
        "effectiveDateTime": when,
        **value_element,
    }
    if extensions:
        obs["extension"] = extensions
    return obs


def to_fhir_bundle(sub: SubmissionOut) -> dict:
    final = (sub.final_answers or sub.answers).model_dump(mode="json")
    when = sub.created_at
    location_id = _stable_uuid(sub.id, "location")
    location_urn = _urn(location_id)
    preds = sub.ai_predictions.model_dump(mode="json") if sub.ai_predictions else None
    score = sub.reliability_score

    entries: list[dict] = []

    # 1. Location
    site = final["site"]
    entries.append(
        {
            "fullUrl": location_urn,
            "resource": {
                "resourceType": "Location",
                "id": location_id,
                "identifier": [{"system": "https://streamcheck.app/site", "value": sub.id}],
                "status": "active",
                "name": site["name"],
                "description": "Urban stream assessment site (OneAquaHealth citizen science)",
                "mode": "instance",
                "physicalType": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/location-physical-type", "code": "area"}]},
                "position": {"longitude": site["lon"], "latitude": site["lat"]},
            },
            "request": {"method": "POST", "url": "Location"},
        }
    )

    # 2. One Observation per form field
    observation_urns: list[str] = []
    for field, value in _field_values(final):
        extensions: list[dict] = []
        if score is not None:
            extensions.append({"url": f"{EXT_BASE}/reliability-score", "valueInteger": score})
        if preds and field in AI_READABLE_FIELDS:
            p = preds[field]
            ai_value = ", ".join(p["value"]) if isinstance(p["value"], list) else p["value"]
            extensions.append(
                {
                    "url": f"{EXT_BASE}/ai-prediction",
                    "extension": [
                        {"url": "confidence", "valueDecimal": p["confidence"]},
                        {"url": "value", "valueString": ai_value},
                        {"url": "evidence", "valueString": p["evidence"]},
                        {"url": "agrees", "valueBoolean": _agrees(value, p["value"])},
                    ],
                }
            )
        obs = _observation(sub.id, field, FIELD_DISPLAY.get(field, field), _value_element(field, value), when, location_urn, extensions)
        urn = _urn(obs["id"])
        observation_urns.append(urn)
        entries.append({"fullUrl": urn, "resource": obs, "request": {"method": "POST", "url": "Observation"}})

    # 3. Summary observations
    summaries = []
    if score is not None:
        summaries.append(("reliability_score", "StreamCheck reliability score (0-100)", {"valueInteger": score}))
    if sub.suggested_overall and sub.suggested_overall.get("value"):
        summaries.append(("suggested_overall_assessment", "Rule-based suggested overall assessment", {"valueString": sub.suggested_overall["value"]}))
    if sub.one_health:
        summaries.append(("one_health_risk_level", "One Health risk level", {"valueString": sub.one_health["risk_level"]}))
    for name, display, value_element in summaries:
        obs = _observation(sub.id, name, display, value_element, when, location_urn, [])
        urn = _urn(obs["id"])
        observation_urns.append(urn)
        entries.append({"fullUrl": urn, "resource": obs, "request": {"method": "POST", "url": "Observation"}})

    # 4. Provenance: a human confirmed these values
    n_flags = len(sub.flags)
    n_decided = sum(1 for f in sub.flags if f.decision)
    n_changed = sum(1 for f in sub.flags if f.decision in ("changed", "accepted"))
    agents = [
        {
            "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type", "code": "author"}]},
            "role": [{"text": "Citizen scientist (human, final decision on every value)"}],
            "who": {"display": "Citizen scientist"},
        }
    ]
    if sub.ai_model:
        agents.append(
            {
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type", "code": "assembler"}]},
                "role": [{"text": "AI second pair of eyes (suggestions only, no authority)"}],
                "who": {"display": f"StreamCheck vision model: {sub.ai_model}"},
            }
        )
    provenance_id = _stable_uuid(sub.id, "provenance")
    entries.append(
        {
            "fullUrl": _urn(provenance_id),
            "resource": {
                "resourceType": "Provenance",
                "id": provenance_id,
                "target": [{"reference": u} for u in observation_urns],
                "recorded": when,
                "activity": {"text": "Human-confirmed after AI-assisted consistency check"},
                "reason": [{"text": f"{n_flags} check(s) raised, {n_decided} decided by the citizen, {n_changed} answer(s) changed"}],
                "agent": agents,
            },
            "request": {"method": "POST", "url": "Provenance"},
        }
    )

    return {
        "resourceType": "Bundle",
        "id": _stable_uuid(sub.id, "bundle"),
        "type": "transaction",
        "timestamp": when,
        "entry": entries,
    }


def _agrees(citizen, ai) -> bool:
    if isinstance(citizen, list) or isinstance(ai, list):
        return set(citizen or []) == set(ai or [])
    return citizen == ai


class FhirSendError(Exception):
    pass


def send_bundle(bundle: dict, server_url: str | None = None) -> dict:
    """POST a transaction Bundle to a FHIR server and summarise what it created."""
    url = (server_url or config.FHIR_SERVER_URL).rstrip("/")
    try:
        r = httpx.post(url, json=bundle, headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}, timeout=30)
    except httpx.HTTPError as e:
        raise FhirSendError(f"Could not reach the FHIR server at {url}: {type(e).__name__}") from e
    if r.status_code >= 400:
        raise FhirSendError(f"FHIR server answered {r.status_code}: {r.text[:300]}")
    body = r.json()
    created = []
    for entry in body.get("entry", []):
        loc = entry.get("response", {}).get("location") or ""
        if loc:
            created.append(loc.split("/_history")[0])
    return {"server": url, "bundle_type": body.get("type"), "created": created}
