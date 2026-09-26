import math
from typing import Tuple, Optional
from app.core.constants import NUM_TICKS

class PoseEstimator:
    """Calculates head yaw, pitch, and sector indices from 5 facial landmarks."""

    @staticmethod
    def calculate_ratios(face) -> Tuple[float, float]:
        """Calculates normalized Yaw and Pitch pose ratios from 5 facial keypoints."""
        kps = face.kps  # 0: left_eye, 1: right_eye, 2: nose, 3: left_mouth, 4: right_mouth
        left_eye, right_eye, nose = kps[0], kps[1], kps[2]

        eye_center_x = (left_eye[0] + right_eye[0]) / 2.0
        eye_center_y = (left_eye[1] + right_eye[1]) / 2.0

        eye_dist = math.sqrt((right_eye[0] - left_eye[0]) ** 2 + (right_eye[1] - left_eye[1]) ** 2)
        if eye_dist == 0:
            return 0.0, 0.0

        # In selfie / mirrored preview, turning to user's right points nose towards image right (larger X).
        # Positive yaw indicates turning right (+yaw), negative indicates turning left (-yaw).
        yaw_ratio = (nose[0] - eye_center_x) / eye_dist
        pitch_ratio = (nose[1] - eye_center_y) / eye_dist - 0.55
        return float(yaw_ratio), float(pitch_ratio)

    @staticmethod
    def map_to_sector(yaw_ratio: float, pitch_ratio: float, num_ticks: int = NUM_TICKS) -> Optional[int]:
        """Maps yaw & pitch into one of 60 radial sectors. Returns None if face is centered."""
        magnitude = math.sqrt(yaw_ratio ** 2 + pitch_ratio ** 2)
        if magnitude <= 0.15:
            return None  # Frontal/center zone

        angle_deg = (math.degrees(math.atan2(yaw_ratio, -pitch_ratio)) + 360.0) % 360.0
        return int((angle_deg / 360.0) * num_ticks) % num_ticks
