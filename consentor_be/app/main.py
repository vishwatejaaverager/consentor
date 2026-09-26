from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router
from app.engine.detector import FaceDetector

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm InsightFace model on application startup
    print("[*] Pre-warming InsightFace buffalo_l engine...")
    _ = FaceDetector()
    print("[✓] Model pre-warmed and ready for inference!")
    yield
    print("[*] Shutting down Consentor API...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Enable CORS for Flutter Web & Mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

app.include_router(api_router, prefix=settings.API_V1_STR)

from fastapi.responses import RedirectResponse

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }

@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/docs")

