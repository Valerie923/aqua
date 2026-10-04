"""One Health insight, rule-based and deterministic.

Two jobs:
  1. suggest_overall()   — a suggested Good / Moderate / Poor with reasons, shown to the
                           citizen BEFORE they pick their own. Their pick is final.
  2. one_health_risks()  — plain-language risk notes, each citing the answers that
                           triggered it and one line on why it matters for people,
                           animals and the environment.

Everything works on the flat field -> value dict from rules.flatten().
"""

from pydantic import BaseModel, Field

from app.rules import flatten

ARTIFICIAL = "Artificial (concrete or stones with concrete)"


class SuggestedOverall(BaseModel):
    value: str | None = Field(None, description="Good / Moderate / Poor, or None if too few answers")
    reasons: list[str] = Field(default_factory=list, description="Plain-language reasons, citing answers")
    pressure_points: int = 0
    not_sure_fields: list[str] = Field(default_factory=list)
    message: str = ""


class Risk(BaseModel):
    id: str
    level: str = Field(..., description="high / medium / low / positive")
    title: str
    message: str = Field(..., description="Plain language, cites the answers that triggered it")
    why_it_matters: str = Field(..., description="One line: people, animals, environment")
    fields: list[str]


class OneHealth(BaseModel):
    risk_level: str = Field(..., description="high / medium / low / positive / unknown")
    risks: list[Risk]
    summary: str


# --------------------------------------------------------------------------
# 1. Suggested overall assessment
# --------------------------------------------------------------------------

# (field, value or predicate, points, reason). Points add up to a "pressure" total:
#   0–1 -> Good, 2–4 -> Moderate, 5+ -> Poor.
def _pressures(flat: dict) -> tuple[int, list[str]]:
    points, reasons = 0, []

    def add(n: int, reason: str):
        nonlocal points
        points += n
        reasons.append(reason)

    if flat.get("sewage_discharge") == "yes":
        add(5, "you reported sewage discharge")  # enough for "Poor" on its own
    if flat.get("draining_pipes") == "yes":
        add(2, "you reported pipes draining polluted water")
    aspect = flat.get("water_aspect")
    if aspect in ("Has foam", "Has colours-altered colour"):
        add(2, f'the water "{aspect}"')
    elif aspect == "Muddy-turbid":
        add(1, "the water is muddy or turbid")
    if flat.get("bottom_type") == ARTIFICIAL:
        add(2, "the stream bottom is artificial")
    if flat.get("bank_type") == ARTIFICIAL:
        add(1, "the banks are artificial")
    no_veg = [s for s in ("left", "right") if flat.get(f"vegetation_{s}") == "no"]
    if len(no_veg) == 2:
        add(2, "there is no vegetation on either bank")
    elif no_veg:
        add(1, f"there is no vegetation on the {no_veg[0]} bank")
    if flat.get("impervious_left") == "yes" and flat.get("impervious_right") == "yes":
        add(1, "both banks are mostly paved or built over")
    if flat.get("barriers") == "yes":
        add(1, "there is a dam or artificial barrier")
    if flat.get("construction") == "yes":
        add(1, "there are works in the stream")
    if flat.get("water_flow") in ("Stagnant-intermittent", "Dry"):
        add(1, f'the water flow is "{flat["water_flow"]}"')
    if flat.get("habitats") == ["none"]:
        add(1, "you saw no habitats (no riffles, pools, vegetation, roots or debris)")
    return points, reasons


SUGGESTION_FIELDS = (
    "bottom_type", "bank_type", "water_aspect", "water_flow", "habitats", "sewage_discharge",
    "draining_pipes", "barriers", "construction", "vegetation_left", "vegetation_right",
    "impervious_left", "impervious_right",
)


def suggest_overall(answers: dict) -> SuggestedOverall:
    flat = flatten(answers)
    answered = [f for f in SUGGESTION_FIELDS if flat.get(f) not in (None, "", [])]
    if len(answered) < 6:
        return SuggestedOverall(message="Not enough answers yet to suggest an overall assessment.")
    not_sure = [f for f in answered if flat.get(f) == "not_sure"]
    points, reasons = _pressures(flat)
    value = "Good" if points <= 1 else "Moderate" if points <= 4 else "Poor"
    if reasons:
        message = f'Based on your answers this stream looks "{value}" because ' + "; ".join(reasons) + "."
    else:
        message = f'Based on your answers this stream looks "{value}": you reported no pressures.'
    if not_sure:
        message += f" ({len(not_sure)} answer(s) you were not sure about were left out.)"
    return SuggestedOverall(value=value, reasons=reasons, pressure_points=points, not_sure_fields=not_sure, message=message)


# --------------------------------------------------------------------------
# 2. One Health risks
# --------------------------------------------------------------------------

def one_health_risks(answers: dict) -> OneHealth:
    flat = flatten(answers)
    risks: list[Risk] = []

    # Mosquito breeding: slow or stagnant water with places for larvae to sit.
    flow = flat.get("water_flow")
    habitats = flat.get("habitats") or []
    debris = [d for d in (flat.get("natural_debris") or []) if d != "none"]
    if flow in ("Slow", "Stagnant-intermittent") and ("pools" in habitats or debris):
        holders = []
        if "pools" in habitats:
            holders.append("pools")
        if debris:
            holders.append("natural debris (" + ", ".join(debris) + ")")
        risks.append(
            Risk(
                id="mosquito_breeding", level="medium", title="Mosquito breeding risk",
                message=f'The water flow is "{flow}" and you saw {" and ".join(holders)}. '
                        "In Singapore's warm climate, still water that sits in pools or among debris is where "
                        "Aedes mosquitoes breed.",
                why_it_matters="People: dengue and other mosquito-borne diseases. Animals: mosquitoes also bite "
                               "wildlife and pets. Environment: a sign the stream is not flushing itself.",
                fields=["water_flow", "habitats", "natural_debris"],
            )
        )

    # Pathogens and pollution.
    signs = []
    if flat.get("sewage_discharge") == "yes":
        signs.append("sewage discharge")
    if flat.get("draining_pipes") == "yes":
        signs.append("pipes draining polluted water")
    aspect = flat.get("water_aspect")
    if aspect == "Has foam":
        signs.append("foam on the water")
    elif aspect == "Has colours-altered colour":
        signs.append("altered water colour")
    if signs:
        risks.append(
            Risk(
                id="pathogen_pollution", level="high", title="Pollution and germ risk — avoid contact",
                message="You reported " + ", ".join(signs) + ". Do not touch or wade in the water and keep "
                        "pets away until it has been checked.",
                why_it_matters="People: skin and stomach infections from contact. Animals: fish and birds take in "
                               "the pollutants. Environment: oxygen drops and sensitive species disappear.",
                fields=["sewage_discharge", "draining_pipes", "water_aspect"],
            )
        )

    # Low biodiversity, heat and flood resilience.
    no_veg = [s for s in ("left", "right") if flat.get(f"vegetation_{s}") == "no"]
    if flat.get("bottom_type") == ARTIFICIAL and no_veg:
        where = "either bank" if len(no_veg) == 2 else f"the {no_veg[0]} bank"
        risks.append(
            Risk(
                id="low_biodiversity_resilience", level="medium", title="Low biodiversity and resilience",
                message=f"The bottom is artificial and there is no vegetation on {where}. Concrete channels with "
                        "bare banks give plants and animals nowhere to live, heat up in the sun and push rain "
                        "downstream fast.",
                why_it_matters="People: hotter surroundings and higher flash-flood peaks. Animals: no shelter, food "
                               "or shade. Environment: the stream cannot clean itself or hold water.",
                fields=["bottom_type", "vegetation_left", "vegetation_right"],
            )
        )

    # Positive note.
    if (
        flat.get("vegetation_left") == "yes"
        and flat.get("vegetation_right") == "yes"
        and aspect == "Clear-transparent"
        and flat.get("sewage_discharge") != "yes"
        and flat.get("draining_pipes") != "yes"
    ):
        risks.append(
            Risk(
                id="wellbeing_positive", level="positive", title="Good for wellbeing and recreation",
                message="Both banks have vegetation and the water is clear with no pollution signs. This is the "
                        "kind of stream people enjoy walking along and wildlife can use.",
                why_it_matters="People: green, cool space that lifts mood. Animals: shelter, shade and food. "
                               "Environment: roots hold the banks and filter runoff.",
                fields=["vegetation_left", "vegetation_right", "water_aspect", "sewage_discharge", "draining_pipes"],
            )
        )

    levels = {r.level for r in risks}
    if "high" in levels:
        risk_level, summary = "high", "High: pollution signs reported. Avoid contact with the water."
    elif "medium" in levels:
        risk_level, summary = "medium", "Medium: conditions that can affect health or wildlife were reported."
    elif "positive" in levels:
        risk_level, summary = "positive", "Positive: a healthy-looking stretch with no risks reported."
    elif any(flat.get(f) not in (None, "", []) for f in ("water_flow", "water_aspect", "sewage_discharge")):
        risk_level, summary = "low", "Low: no specific One Health risk was triggered by your answers."
    else:
        risk_level, summary = "unknown", "Not enough answers yet."
    return OneHealth(risk_level=risk_level, risks=risks, summary=summary)
