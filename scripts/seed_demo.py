"""Seed demo submissions by running each demo scenario through the REAL pipeline.

    export GEMINI_API_KEY=...
    python scripts/seed_demo.py [--reset]

For every scenario in demo/scenarios.json whose photos exist under demo/photos/<id>/:
  1. the photos are analysed by the configured vision provider (live call),
  2. the citizen answers from the scenario are checked against that reading and the
     consistency rules (real flags),
  3. because no human is present, every flag is recorded as "kept" and the submission
     is tagged notes="demo" so the UI can say so,
  4. the submission is stored with the server-computed score and insights.
Nothing is hard-coded: run it twice and the AI reading may differ slightly.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete  # noqa: E402

from app import db  # noqa: E402
from app.config import UPLOAD_DIR  # noqa: E402
from app.insights import one_health_risks, suggest_overall  # noqa: E402
from app.routers.analyze import prepare_image  # noqa: E402
from app.routers.demo import PHOTOS_DIR, available_scenarios  # noqa: E402
from app.rules import run_checks  # noqa: E402
from app.schemas import AnalysisResult, FormAnswers  # noqa: E402
from app.vision import get_provider, model_name, provider_name  # noqa: E402
from app.vision.base import Photo, VisionUnavailable  # noqa: E402


def analyse_scenario(sc: dict) -> AnalysisResult:
    photo_set_id = db.new_id()
    folder = UPLOAD_DIR / photo_set_id
    folder.mkdir(parents=True, exist_ok=True)
    photos, stored = [], {}
    for role, url in sc["photos"].items():
        src = PHOTOS_DIR / sc["id"] / Path(url).name
        data = prepare_image(src.read_bytes())
        (folder / f"{role}.jpg").write_bytes(data)
        stored[role] = f"{role}.jpg"
        photos.append(Photo(role=role, media_type="image/jpeg", data=data))
    result = AnalysisResult(photo_set_id=photo_set_id, photos=stored, ai_available=False)
    try:
        result.predictions = get_provider().analyse(photos)
        result.ai_available = True
        result.model = model_name()
    except VisionUnavailable as e:
        result.error = str(e)
    (folder / "analysis.json").write_text(result.model_dump_json(indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="delete earlier demo submissions first")
    args = parser.parse_args()

    db.init_db()
    scenarios = available_scenarios()
    if not scenarios:
        print("No demo scenario has photos yet. See demo/README.md.")
        return 1
    if provider_name() == "none":
        print("No vision API key set (GEMINI_API_KEY or ANTHROPIC_API_KEY). Refusing to seed without a real AI reading.")
        return 1

    session = db.SessionLocal()
    if args.reset:
        n = session.execute(delete(db.Submission).where(db.Submission.notes == "demo")).rowcount
        session.commit()
        print(f"Removed {n} earlier demo submission(s).")

    for sc in scenarios:
        print(f"→ {sc['name']}: analysing {len(sc['photos'])} photo(s) with {provider_name()} ({model_name()})…")
        analysis = analyse_scenario(sc)
        if not analysis.ai_available:
            print(f"   AI reading failed: {analysis.error}. Skipping this scenario.")
            continue
        answers = FormAnswers.model_validate({"site": sc["site"], **sc["answers"]})
        answers_json = answers.model_dump(mode="json")
        flags, rel = run_checks(answers_json, analysis.predictions, [], analysis.photos)
        for f in flags:
            f.decision = "kept"
        row = db.Submission(
            id=db.new_id(),
            created_at=db.now_iso(),
            site_name=answers.site.name,
            lat=answers.site.lat,
            lon=answers.site.lon,
            photo_set_id=analysis.photo_set_id,
            photos=analysis.photos,
            answers=answers_json,
            ai_predictions=analysis.predictions.model_dump(mode="json"),
            ai_model=analysis.model,
            flags=[f.model_dump(mode="json") for f in flags],
            final_answers=answers_json,
            reliability_score=rel.score,
            reliability=rel.model_dump(mode="json"),
            suggested_overall=suggest_overall(answers_json).model_dump(),
            one_health=one_health_risks(answers_json).model_dump(),
            notes="demo",
        )
        session.add(row)
        session.commit()
        print(f"   saved {row.id}: {len(flags)} flag(s) (all recorded as 'kept'), reliability {rel.score}/100, "
              f"One Health {row.one_health['risk_level']}")
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
