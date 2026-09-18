"""POST /api/check — compare answers so far with the AI reading and the
consistency rules. Called after every section and again on the review screen.
Deterministic: no AI call happens here; predictions come from the stored analysis."""

from fastapi import APIRouter

from app.routers.analyze import load_analysis
from app.rules import run_checks
from app.schemas import CheckIn, CheckOut

router = APIRouter(prefix="/api", tags=["checks"])


@router.post("/check", response_model=CheckOut)
def check(body: CheckIn) -> CheckOut:
    predictions, photos = None, {}
    if body.photo_set_id:
        analysis = load_analysis(body.photo_set_id)
        if analysis is not None:
            predictions, photos = analysis.predictions, analysis.photos
    flags, rel = run_checks(body.answers, predictions, body.flags, photos)
    return CheckOut(flags=flags, reliability=rel)
