"""FHIR endpoints (Track 7).

  GET  /api/submissions/{id}/fhir        -> the R4 transaction Bundle as JSON (download)
  POST /api/submissions/{id}/fhir/send   -> POST that Bundle to a FHIR server, return created IDs
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config, db
from app.fhir import FhirSendError, send_bundle, to_fhir_bundle
from app.routers.submissions import _to_out

router = APIRouter(prefix="/api", tags=["fhir"])


def _load(submission_id: str, session: Session) -> db.Submission:
    row = session.get(db.Submission, submission_id)
    if row is None:
        raise HTTPException(404, "Submission not found")
    return row


@router.get("/submissions/{submission_id}/fhir")
def export_fhir(submission_id: str, session: Session = Depends(db.get_db)) -> JSONResponse:
    bundle = to_fhir_bundle(_to_out(_load(submission_id, session)))
    return JSONResponse(
        bundle,
        media_type="application/fhir+json",
        headers={"Content-Disposition": f'attachment; filename="streamcheck-{submission_id}.fhir.json"'},
    )


class SendOut(BaseModel):
    server: str
    bundle_type: str | None
    created: list[str]


@router.post("/submissions/{submission_id}/fhir/send", response_model=SendOut)
def send_fhir(submission_id: str, session: Session = Depends(db.get_db)) -> SendOut:
    bundle = to_fhir_bundle(_to_out(_load(submission_id, session)))
    try:
        return SendOut(**send_bundle(bundle, config.FHIR_SERVER_URL))
    except FhirSendError as e:
        raise HTTPException(502, str(e)) from e
