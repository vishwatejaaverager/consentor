from typing import Optional, Dict, Any, List
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from enum import Enum

class FrameEvaluationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    RETAKE = "RETAKE"
    DONE = "DONE"

class RetakeReason(str, Enum):
    NO_FACE_DETECTED = "NO_FACE_DETECTED"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    FACE_TOO_FAR = "FACE_TOO_FAR"
    POOR_LIGHTING_OR_BLUR = "POOR_LIGHTING_OR_BLUR"
    OFF_ANGLE = "OFF_ANGLE"

class HeadPose(BaseModel):
    yaw: float
    pitch: float
    sector_id: Optional[int] = None

class ProgressInfo(BaseModel):
    completed_ticks: int
    total_ticks: int = 60
    progress_pct: int
    active_ticks: List[bool]

class ProcessFrameResponse(BaseModel):
    status: FrameEvaluationStatus
    message: str
    reason: Optional[RetakeReason] = None
    det_score: Optional[float] = None
    threshold_required: Optional[float] = None
    head_pose: Optional[HeadPose] = None
    progress: Optional[ProgressInfo] = None
    s3_path: Optional[str] = None
    session_summary: Optional[Dict[str, Any]] = None

class StartEnrollmentRequest(BaseModel):
    user_id: str

class StartEnrollmentResponse(BaseModel):
    session_id: str
    user_id: str
    message: str
