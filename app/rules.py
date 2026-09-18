"""Deterministic checks. No AI calls here, so every function is unit-testable.

Three jobs:
  1. compare_with_ai()     — where the citizen and the AI disagree (or the AI can help
                             with a "not sure")
  2. consistency_rules()   — answers that contradict each other
  3. reliability()         — a 0–100 score for the submission (formula in README)

All functions work on a *flat* dict of field -> value (see flatten()).
"""

from app.schemas import (
    AI_READABLE_FIELDS,
    FIELD_SECTION,
    Flag,
    Reliability,
    ReliabilityComponent,
    VisionPredictions,
)

DISAGREEMENT_THRESHOLD = 0.7  # AI must be at least this sure before we question the citizen
SUGGESTION_THRESHOLD = 0.5  # ...and at least this sure before we offer a suggestion for "not sure"

MULTI_FIELDS = {"habitats", "natural_debris"}

# Human-readable names used inside flag messages.
FIELD_NAMES = {
    "channel_form": "channel form",
    "bottom_type": "bottom type",
    "bank_type": "bank type",
    "habitats": "habitats",
    "natural_debris": "natural debris",
    "water_flow": "water flow",
    "water_aspect": "water aspect",
    "barriers": "barriers",
    "draining_pipes": "draining pipes",
    "construction": "construction",
    "impervious_left": "impervious surface on the left bank",
    "impervious_right": "impervious surface on the right bank",
    "vegetation_left": "vegetation on the left bank",
    "vegetation_right": "vegetation on the right bank",
    "vegetation_type_left": "vegetation type on the left bank",
    "vegetation_type_right": "vegetation type on the right bank",
    "water_height_m": "water height",
    "sewage_discharge": "sewage discharge",
    "overall_assessment": "overall assessment",
}


def flatten(answers: dict) -> dict:
    """{"site": {...}, "section_a": {...}, ...} -> {"channel_form": ..., ...}.
    Already-flat dicts pass through unchanged."""
    flat: dict = {}
    for key, value in answers.items():
        if key.startswith("section_") and isinstance(value, dict):
            flat.update(value)
        elif key == "site":
            continue
        else:
            flat[key] = value
    return flat


def _pretty(value) -> str:
    if isinstance(value, list):
        return ", ".join(_pretty(v) for v in value) if value else "none"
    if value == "not_sure":
        return "Not sure"
    if value in ("yes", "no"):
        return value.capitalize()
    return str(value)


def _same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return set(a or []) == set(b or [])
    return a == b


# --------------------------------------------------------------------------
# 1. Citizen vs AI
# --------------------------------------------------------------------------

def compare_with_ai(answers: dict, predictions: VisionPredictions | None) -> list[Flag]:
    """Return one flag per AI-readable field the citizen has answered where either
    (a) they disagree and the AI is confident, or (b) the citizen said "not sure"
    and the AI has a reasonable suggestion. Agreement produces no flag."""
    if predictions is None:
        return []
    flat = flatten(answers)
    flags: list[Flag] = []
    for field in AI_READABLE_FIELDS:
        if field not in flat or flat[field] in (None, ""):
            continue
        citizen = flat[field]
        pred = getattr(predictions, field)
        ai_value = [v.value for v in pred.value] if isinstance(pred.value, list) else pred.value.value
        section = FIELD_SECTION[field]
        name = FIELD_NAMES.get(field, field)

        if _same(citizen, ai_value):
            continue
        if ai_value == "not_sure":
            continue  # the AI cannot help here

        if citizen == "not_sure" and pred.confidence >= SUGGESTION_THRESHOLD:
            flags.append(
                Flag(
                    id=f"ai:{field}",
                    kind="ai_suggestion",
                    section=section,
                    field=field,
                    fields=[field],
                    message=(
                        f"You weren't sure about the {name}. Our AI thinks it is "
                        f"\"{_pretty(ai_value)}\" because {pred.evidence.rstrip('.')}. "
                        "Use this answer?"
                    ),
                    citizen_value=citizen,
                    ai_value=ai_value,
                    ai_confidence=pred.confidence,
                    ai_evidence=pred.evidence,
                )
            )
        elif citizen != "not_sure" and pred.confidence >= DISAGREEMENT_THRESHOLD:
            flags.append(
                Flag(
                    id=f"ai:{field}",
                    kind="ai_disagreement",
                    section=section,
                    field=field,
                    fields=[field],
                    message=(
                        f"Our AI thinks the {name} looks like \"{_pretty(ai_value)}\" because "
                        f"{pred.evidence.rstrip('.')}. You answered \"{_pretty(citizen)}\". "
                        "Keep your answer or change it?"
                    ),
                    citizen_value=citizen,
                    ai_value=ai_value,
                    ai_confidence=pred.confidence,
                    ai_evidence=pred.evidence,
                )
            )
    return flags


# --------------------------------------------------------------------------
# 2. Consistency rules
# --------------------------------------------------------------------------

def _has(flat: dict, *fields: str) -> bool:
    return all(flat.get(f) not in (None, "") for f in fields)


def _rule(rule_id: str, section: str, field: str, fields: list[str], message: str, flat: dict) -> Flag:
    return Flag(
        id=f"rule:{rule_id}",
        kind="rule",
        section=section,
        field=field,
        fields=fields,
        message=message,
        citizen_value=flat.get(field),
    )


def consistency_rules(answers: dict) -> list[Flag]:
    """Flag answers that contradict each other. Only rules whose fields are all
    answered are evaluated, so this can run after every section."""
    flat = flatten(answers)
    flags: list[Flag] = []

    # Dry stream but a water height was given.
    if _has(flat, "water_flow", "water_height_m") and flat["water_flow"] == "Dry":
        try:
            height = float(flat["water_height_m"])
        except (TypeError, ValueError):
            height = 0.0
        if height > 0:
            flags.append(
                _rule(
                    "dry_but_water_height", "section_b", "water_height_m", ["water_flow", "water_height_m"],
                    f"You said the water flow is \"Dry\" but gave a water height of {height:g} m. "
                    "A dry stream should have a height of 0. Which one is right?",
                    flat,
                )
            )

    # No vegetation on a bank, but a vegetation type was chosen for it.
    for side in ("left", "right"):
        veg, veg_type = f"vegetation_{side}", f"vegetation_type_{side}"
        if flat.get(veg) == "no" and flat.get(veg_type) not in (None, "", "not_sure"):
            flags.append(
                _rule(
                    f"vegetation_type_without_vegetation_{side}", "section_c", veg_type, [veg, veg_type],
                    f"You said there is no vegetation on the {side} bank, but chose "
                    f"\"{flat[veg_type]}\" as its vegetation type. Please check one of them.",
                    flat,
                )
            )

    # Overall "Good" despite clear pressure signs.
    if flat.get("overall_assessment") == "Good":
        reasons = []
        if flat.get("sewage_discharge") == "yes":
            reasons.append("you reported sewage discharge")
        if flat.get("draining_pipes") == "yes":
            reasons.append("you reported pipes draining polluted water")
        if flat.get("bottom_type", "").startswith("Artificial"):
            reasons.append("the bottom is artificial")
        if flat.get("water_aspect") in ("Has foam", "Has colours-altered colour"):
            reasons.append(f"the water \"{flat['water_aspect']}\"")
        if reasons:
            flags.append(
                _rule(
                    "good_despite_pressures", "section_d", "overall_assessment",
                    ["overall_assessment", "sewage_discharge", "draining_pipes", "bottom_type", "water_aspect"],
                    "You rated the stream \"Good\", but " + " and ".join(reasons) +
                    ". That usually points to \"Moderate\" or \"Poor\". Keep \"Good\" or change it?",
                    flat,
                )
            )

    # Overall "Poor" although nothing reported suggests a problem.
    if flat.get("overall_assessment") == "Poor" and _has(
        flat, "bottom_type", "bank_type", "water_aspect", "sewage_discharge", "draining_pipes", "barriers", "construction"
    ):
        pristine = (
            flat["bottom_type"] == "Natural"
            and flat["bank_type"] == "Natural"
            and flat["water_aspect"] == "Clear-transparent"
            and all(flat[f] == "no" for f in ("sewage_discharge", "draining_pipes", "barriers", "construction"))
        )
        if pristine:
            flags.append(
                _rule(
                    "poor_despite_no_pressures", "section_d", "overall_assessment",
                    ["overall_assessment", "bottom_type", "bank_type", "water_aspect", "sewage_discharge",
                     "draining_pipes", "barriers", "construction"],
                    "You rated the stream \"Poor\", but you reported natural bed and banks, clear water and no "
                    "pressures. Is there something the form did not capture, or should this be \"Good\"?",
                    flat,
                )
            )

    return flags


# --------------------------------------------------------------------------
# 3. Reliability score
# --------------------------------------------------------------------------

def reliability(
    final_answers: dict,
    predictions: VisionPredictions | None,
    flags: list[Flag],
    photos: dict,
) -> Reliability:
    """0–100. See README for the formula.

    Components (max points):
      AI agreement   50  — share of AI-readable fields whose final answer matches a
                           confident (>= 0.5) AI prediction
      Photos         20  — 6 each for upstream/downstream/context, 2 for biodiversity
      Consistency    30  — minus 10 per unresolved flag, minus 3 per "not sure"
    If the AI was unavailable the agreement component is dropped and the rest is
    rescaled to 100, so a citizen without AI is not penalised for our outage.
    """
    flat = flatten(final_answers)
    components: list[ReliabilityComponent] = []
    ai_available = predictions is not None

    if ai_available:
        judged = agreed = 0
        for field in AI_READABLE_FIELDS:
            pred = getattr(predictions, field)
            ai_value = [v.value for v in pred.value] if isinstance(pred.value, list) else pred.value.value
            if pred.confidence < SUGGESTION_THRESHOLD or ai_value == "not_sure" or field not in flat:
                continue
            judged += 1
            if _same(flat[field], ai_value):
                agreed += 1
        pts = 50 * agreed / judged if judged else 0
        components.append(
            ReliabilityComponent(
                name="AI agreement", points=round(pts, 1), max_points=50,
                note=f"{agreed} of {judged} answers match what the AI saw" if judged else "AI had no confident readings",
            )
        )

    photo_pts = sum(6 for r in ("upstream", "downstream", "context") if r in photos) + (2 if "biodiversity" in photos else 0)
    components.append(
        ReliabilityComponent(name="Photos", points=photo_pts, max_points=20, note=f"{len(photos)} photo(s) provided")
    )

    # Unresolved = rule flags that still hold on the final answers, plus AI flags never answered.
    still_open = {f.id for f in consistency_rules(final_answers)}
    unresolved = [f for f in flags if (f.kind == "rule" and f.id in still_open) or (f.kind != "rule" and f.decision is None)]
    not_sure_count = sum(1 for v in flat.values() if v == "not_sure")
    consistency_pts = max(0, 30 - 10 * len(unresolved) - 3 * not_sure_count)
    components.append(
        ReliabilityComponent(
            name="Consistency", points=consistency_pts, max_points=30,
            note=f"{len(unresolved)} unresolved flag(s), {not_sure_count} \"not sure\" answer(s)",
        )
    )

    total = sum(c.points for c in components)
    max_total = sum(c.max_points for c in components)
    score = round(100 * total / max_total) if max_total else 0
    return Reliability(score=max(0, min(100, score)), components=components, ai_available=ai_available)


def run_checks(answers: dict, predictions: VisionPredictions | None, prior_flags: list[Flag], photos: dict):
    """Everything the /api/check endpoint needs: merged flags (keeping decisions the
    citizen already made) and the current reliability."""
    decisions = {f.id: f for f in prior_flags if f.decision is not None}
    fresh = compare_with_ai(answers, predictions) + consistency_rules(answers)
    merged: list[Flag] = []
    seen: set[str] = set()
    for flag in fresh:
        seen.add(flag.id)
        prior = decisions.get(flag.id)
        if prior is not None:
            flag.decision = prior.decision
            flag.decided_value = prior.decided_value
            flag.citizen_value = prior.citizen_value
        merged.append(flag)
    # Keep decided AI flags whose field no longer differs (the citizen changed to the AI value).
    for flag in prior_flags:
        if flag.id not in seen and flag.decision in ("changed", "accepted"):
            merged.append(flag)
    return merged, reliability(answers, predictions, merged, photos)
