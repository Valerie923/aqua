from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.routers.analyze import load_analysis
from app.insights import one_health_risks, suggest_overall
from app.rules import reliability
from app.schemas import Reliability, SubmissionIn, SubmissionOut

router = APIRouter(prefix="/api", tags=["submissions"])


def _to_out(row: db.Submission) -> SubmissionOut:
    return SubmissionOut(
        id=row.id,
        created_at=row.created_at,
        photo_set_id=row.photo_set_id,
        photos=row.photos or {},
        answers=row.answers,
        ai_predictions=row.ai_predictions,
        ai_model=row.ai_model,
        flags=row.flags or [],
        final_answers=row.final_answers,
        reliability_score=row.reliability_score,
        reliability=row.reliability,
        suggested_overall=row.suggested_overall,
        one_health=row.one_health,
        notes=row.notes,
    )


@router.post("/submissions", response_model=SubmissionOut, status_code=201)
def create_submission(body: SubmissionIn, session: Session = Depends(db.get_db)) -> SubmissionOut:
    photos: dict[str, str] = {}
    ai_predictions = None
    ai_model = None
    if body.photo_set_id:
        analysis = load_analysis(body.photo_set_id)
        if analysis is None:
            raise HTTPException(404, "Unknown photo_set_id")
        photos = analysis.photos
        if analysis.predictions is not None:
            ai_predictions = analysis.predictions.model_dump(mode="json")
            ai_model = analysis.model

    final = body.final_answers or body.answers
    predictions = analysis.predictions if body.photo_set_id and analysis else None
    # The score is always computed server-side so it cannot be edited in the browser.
    rel: Reliability = reliability(final.model_dump(mode="json"), predictions, body.flags, photos)

    row = db.Submission(
        id=db.new_id(),
        created_at=db.now_iso(),
        site_name=final.site.name,
        lat=final.site.lat,
        lon=final.site.lon,
        photo_set_id=body.photo_set_id,
        photos=photos,
        answers=body.answers.model_dump(mode="json"),
        ai_predictions=ai_predictions,
        ai_model=ai_model,
        flags=[f.model_dump(mode="json") for f in body.flags],
        final_answers=final.model_dump(mode="json"),
        reliability_score=rel.score,
        reliability=rel.model_dump(mode="json"),
        suggested_overall=suggest_overall(final.model_dump(mode="json")).model_dump(),
        one_health=one_health_risks(final.model_dump(mode="json")).model_dump(),
    )
    session.add(row)
    session.commit()
    return _to_out(row)


@router.get("/submissions", response_model=list[SubmissionOut])
def list_submissions(session: Session = Depends(db.get_db)) -> list[SubmissionOut]:
    rows = session.scalars(select(db.Submission).order_by(db.Submission.created_at.desc())).all()
    return [_to_out(r) for r in rows]


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: str, session: Session = Depends(db.get_db)) -> SubmissionOut:
    row = session.get(db.Submission, submission_id)
    if row is None:
        raise HTTPException(404, "Submission not found")
    return _to_out(row)
