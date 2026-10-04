from fastapi import APIRouter

from app.schemas import form_options
from app.sites import SEED_SITES

router = APIRouter(prefix="/api", tags=["form"])


@router.get("/sites")
def list_sites() -> list[dict]:
    return SEED_SITES


@router.get("/form-options")
def get_form_options() -> dict:
    """Option lists straight from the Pydantic schema, so the UI never drifts."""
    return form_options()
