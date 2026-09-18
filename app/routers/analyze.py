"""POST /api/analyze — store the photos, ask the vision model to read them.

Photos are saved to disk under a new photo_set_id together with the
predictions (predictions.json). A later /api/submissions call references the
photo_set_id, so the server, not the browser, is the source of AI results.
"""

import io
import json
import logging

from fastapi import APIRouter, File, UploadFile
from PIL import Image, ImageOps

from app import config, db
from app.schemas import AnalysisResult
from app.vision import get_provider
from app.vision.base import Photo, VisionUnavailable

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ai"])

PHOTO_ROLES = ("upstream", "downstream", "context", "biodiversity")


def prepare_image(raw: bytes) -> bytes:
    """Fix phone rotation, drop alpha, downscale, re-encode as JPEG."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((config.MAX_IMAGE_EDGE, config.MAX_IMAGE_EDGE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(
    upstream: UploadFile | None = File(None),
    downstream: UploadFile | None = File(None),
    context: UploadFile | None = File(None),
    biodiversity: UploadFile | None = File(None),
) -> AnalysisResult:
    uploads = {"upstream": upstream, "downstream": downstream, "context": context, "biodiversity": biodiversity}

    photo_set_id = db.new_id()
    folder = config.UPLOAD_DIR / photo_set_id
    folder.mkdir(parents=True, exist_ok=True)

    photos: list[Photo] = []
    stored: dict[str, str] = {}
    for role in PHOTO_ROLES:
        f = uploads[role]
        if f is None or not f.filename:
            continue
        raw = await f.read()
        if not raw:
            continue
        try:
            data = prepare_image(raw)
        except Exception:
            log.warning("Could not decode %s photo; skipping", role)
            continue
        filename = f"{role}.jpg"
        (folder / filename).write_bytes(data)
        stored[role] = filename
        photos.append(Photo(role=role, media_type="image/jpeg", data=data))

    provider = get_provider()
    result = AnalysisResult(photo_set_id=photo_set_id, photos=stored, ai_available=False)

    if not photos:
        result.error = "No readable photos were uploaded."
    else:
        try:
            result.predictions = provider.analyse(photos)
            result.ai_available = True
            result.model = getattr(provider, "model", provider.name)
        except VisionUnavailable as e:
            result.error = str(e)
        except Exception as e:  # last resort: never crash the form because the AI hiccupped
            log.exception("Vision provider failed")
            result.error = f"AI photo reading failed unexpectedly ({type(e).__name__})."

    (folder / "analysis.json").write_text(result.model_dump_json(indent=2))
    return result


def load_analysis(photo_set_id: str) -> AnalysisResult | None:
    path = config.UPLOAD_DIR / photo_set_id / "analysis.json"
    if not path.exists():
        return None
    return AnalysisResult.model_validate(json.loads(path.read_text()))
