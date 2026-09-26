from typing import List
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from app.schemas.enrollment import (
    ProcessFrameResponse,
    StartEnrollmentRequest,
    StartEnrollmentResponse,
    ProgressInfo,
)
from app.services.enrollment_service import EnrollmentService, get_enrollment_service
from app.services.session_manager import SessionManager, get_session_manager
from app.core.constants import NUM_TICKS

router = APIRouter()

@router.post("/process-frame", response_model=ProcessFrameResponse, include_in_schema=False)
async def process_frame(
    user_id: str = Form(..., description="Unique ID of the user enrolling"),
    image: UploadFile = File(..., description="Camera JPEG/PNG snapshot"),
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
):
    """Internal frame evaluation fallback for web portal."""
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image file received.",
        )

    response = enrollment_service.process_frame(user_id=user_id, image_bytes=image_bytes)
    return response

@router.post("/batch", response_model=ProcessFrameResponse, summary="Batch process pre-captured frames collected locally on device")
async def process_batch(
    user_id: str = Form(..., description="Unique ID of the user enrolling"),
    images: List[UploadFile] = File(..., description="Batch of camera frames captured around 360-degree rotation"),
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
):
    """
    Client-first enrollment: Frontend captures qualified angle frames locally,
    then uploads all profile frames in one single batch request.
    """
    image_bytes_list = []
    for img in images:
        content = await img.read()
        if content:
            image_bytes_list.append(content)

    if not image_bytes_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid image files received in batch.",
        )

    return enrollment_service.process_batch(user_id=user_id, image_bytes_list=image_bytes_list)

@router.post("/verify", summary="Verify live face image against enrolled Face ID profile")
async def verify_face(
    user_id: str = Form(..., description="Unique ID of the user"),
    image: UploadFile = File(..., description="Live camera snapshot to verify"),
    enrollment_service: EnrollmentService = Depends(get_enrollment_service),
):
    """Verifies a single face image against the enrolled 512-D vectors."""
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image file received.",
        )
    is_match, score, message = enrollment_service.verify_face(user_id=user_id, image_bytes=image_bytes)
    return {
        "verified": is_match,
        "similarity": round(score, 4),
        "user_id": user_id,
        "message": message,
    }
