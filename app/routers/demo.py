"""Demo scenarios: real photos in demo/photos/<scenario>/ plus the citizen answers in
demo/scenarios.json. Only scenarios whose photos are actually on disk are listed, and
the photos always go through the real /api/analyze call — nothing is pre-computed."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["demo"])

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo"
PHOTOS_DIR = DEMO_DIR / "photos"
REQUIRED = ("upstream", "downstream", "context")
OPTIONAL = ("biodiversity",)


def load_scenarios() -> list[dict]:
    path = DEMO_DIR / "scenarios.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def scenario_photos(scenario_id: str) -> dict[str, str]:
    """role -> filename for the photos present on disk."""
    folder = PHOTOS_DIR / scenario_id
    found: dict[str, str] = {}
    for role in REQUIRED + OPTIONAL:
        for ext in ("jpg", "jpeg", "png"):
            if (folder / f"{role}.{ext}").exists():
                found[role] = f"{role}.{ext}"
                break
    return found


def available_scenarios() -> list[dict]:
    out = []
    for sc in load_scenarios():
        photos = scenario_photos(sc["id"])
        if all(r in photos for r in REQUIRED):
            out.append({**sc, "photos": {role: f"/demo-photos/{sc['id']}/{name}" for role, name in photos.items()}})
    return out


@router.get("/api/demo")
def list_demo() -> list[dict]:
    return [{k: v for k, v in sc.items() if k != "answers"} for sc in available_scenarios()]


@router.get("/demo-photos/{scenario_id}/{filename}")
def demo_photo(scenario_id: str, filename: str) -> FileResponse:
    """Serve one demo photo. Path pieces are validated against what is on disk."""
    if filename not in scenario_photos(scenario_id).values():
        raise HTTPException(404, "No such demo photo")
    return FileResponse(PHOTOS_DIR / scenario_id / filename)
