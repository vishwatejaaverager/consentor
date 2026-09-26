from fastapi import APIRouter, File, UploadFile, Query, HTTPException, Depends
from typing import Optional

from app.services.enrollment_service import EnrollmentService, get_enrollment_service

router = APIRouter()

@router.post("/match-faces", summary="1:N Face Search (Identify User from Image)")
async def match_faces(
    image: UploadFile = File(..., description="Query photo to match against enrolled biometric database"),
    threshold: float = Query(0.45, ge=0.0, le=1.0, description="Cosine similarity match threshold"),
    top_k: int = Query(5, ge=1, le=50, description="Max candidate matches to return"),
    service: EnrollmentService = Depends(get_enrollment_service),
):
    """
    Compares query face against ALL enrolled users in database.
    Returns ranked list of matching users with similarity scores.
    """
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Image file required.")

    image_bytes = await image.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty image payload received.")

    result = service.match_faces(image_bytes=image_bytes, threshold=threshold, top_k=top_k)
    return result

@router.get("", summary="List Enrolled User IDs")
async def list_enrolled_users(
    service: EnrollmentService = Depends(get_enrollment_service),
):
    """Returns list of all user IDs with enrolled biometric profiles."""
    all_embeddings = service.storage.get_all_embeddings()
    return {
        "total_enrolled": len(all_embeddings),
        "users": list(all_embeddings.keys())
    }
