"""StreamCheck — FastAPI entry point.

Routes:
  GET  /                    the single-page form (static/)
  GET  /api/form-options    option lists from the Pydantic schema
  GET  /api/sites           seeded sites
  POST /api/analyze         photos -> AI predictions
  POST /api/submissions     save a completed form
  GET  /api/submissions     list / GET /api/submissions/{id}
  GET  /uploads/...         stored photos
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, db
from app.routers import analyze, sites, submissions

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"



@asynccontextmanager
async def lifespan(_: FastAPI):
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    yield


app = FastAPI(title="StreamCheck", version="0.1.0", lifespan=lifespan)
app.include_router(sites.router)
app.include_router(analyze.router)
app.include_router(submissions.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "ai_configured": bool(config.ANTHROPIC_API_KEY), "model": config.VISION_MODEL}


app.mount("/uploads", StaticFiles(directory=str(config.UPLOAD_DIR), check_dir=False), name="uploads")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
