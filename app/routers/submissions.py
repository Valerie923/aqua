from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.routers.analyze import load_analysis
from app.schemas import SubmissionIn, SubmissionOut

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

    row = db.Submission(
        id=db.new_id(),
        created_at=db.now_iso(),
        site_name=body.answers.site.name,
        lat=body.answers.site.lat,
        lon=body.answers.site.lon,
        photo_set_id=body.photo_set_id,
        photos=photos,
        answers=body.answers.model_dump(mode="json"),
        ai_predictions=ai_predictions,
        ai_model=ai_model,
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
