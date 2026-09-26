from typing import List, Tuple, Optional, Any
from app.core.constants import (
    MIN_DET_SCORE_FRONTAL,
    MIN_DET_SCORE_ANGLE,
    MIN_BBOX_SIZE,
)
from app.schemas.enrollment import RetakeReason

class QualityGate:
    """Evaluates face frames against quality, resolution, lighting, and blur thresholds."""

    @staticmethod
    def evaluate(
        faces: List[Any],
        sector_id: Optional[int] = None
    ) -> Tuple[bool, Optional[RetakeReason], str, float, float]:
        """
        Evaluates detected faces.
        Returns:
            (is_valid, retake_reason, message, actual_score, required_threshold)
        """
        # 1. Face Count Validation
        if len(faces) == 0:
            return (
                False,
                RetakeReason.NO_FACE_DETECTED,
                "No face detected. Please position your face inside the frame.",
                0.0,
                MIN_DET_SCORE_FRONTAL,
            )

        if len(faces) > 1:
            return (
                False,
                RetakeReason.MULTIPLE_FACES,
                "Multiple faces detected. Please ensure only you are visible.",
                0.0,
                MIN_DET_SCORE_FRONTAL,
            )

        face = faces[0]
        det_score = float(face.det_score)

        # 2. Bounding Box / Face Distance Check
        bbox = face.bbox  # [x1, y1, x2, y2]
        box_w = bbox[2] - bbox[0]
        box_h = bbox[3] - bbox[1]

        if box_w < MIN_BBOX_SIZE or box_h < MIN_BBOX_SIZE:
            return (
                False,
                RetakeReason.FACE_TOO_FAR,
                "Move closer to the camera to fill the circular frame.",
                det_score,
                MIN_DET_SCORE_ANGLE if sector_id is not None else MIN_DET_SCORE_FRONTAL,
            )

        # 3. Detection Score & Lighting Threshold
        required_threshold = (
            MIN_DET_SCORE_ANGLE if sector_id is not None else MIN_DET_SCORE_FRONTAL
        )

        if det_score < required_threshold:
            return (
                False,
                RetakeReason.POOR_LIGHTING_OR_BLUR,
                "Low lighting or blur detected. Please face the light and hold steady.",
                det_score,
                required_threshold,
            )

        # 4. Passed Quality Gate
        return True, None, "Face quality verified.", det_score, required_threshold
