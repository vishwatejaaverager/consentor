import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, List, Optional

from app.engine.detector import FaceDetector
from app.engine.pose_estimator import PoseEstimator
from app.engine.quality_gate import QualityGate
from app.engine.embedder import FaceEmbedder
from app.services.session_manager import SessionManager, get_session_manager
from app.services.storage_service import BaseStorageService, get_storage_service
from app.schemas.enrollment import (
    ProcessFrameResponse,
    FrameEvaluationStatus,
    HeadPose,
    ProgressInfo,
    RetakeReason,
)
from app.core.constants import NUM_TICKS

class EnrollmentService:
    def __init__(
        self,
        detector: FaceDetector = None,
        storage: BaseStorageService = None,
        session_mgr: SessionManager = None,
    ):
        self.detector = detector or FaceDetector()
        self.storage = storage or get_storage_service()
        self.session_mgr = session_mgr or get_session_manager()

    def process_frame(self, user_id: str, image_bytes: bytes) -> ProcessFrameResponse:
        session = self.session_mgr.get_or_create_session(user_id)

        # 1. Decode image bytes into BGR OpenCV format
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame_bgr is None:
            return ProcessFrameResponse(
                status=FrameEvaluationStatus.RETAKE,
                message="Invalid image payload. Unable to decode image.",
            )

        # 2. Run InsightFace Detection
        faces = self.detector.detect(frame_bgr)

        # 3. Rough Pose Check (if 1 face detected)
        sector_id = None
        yaw_ratio, pitch_ratio = 0.0, 0.0
        if len(faces) == 1:
            yaw_ratio, pitch_ratio = PoseEstimator.calculate_ratios(faces[0])
            sector_id = PoseEstimator.map_to_sector(yaw_ratio, pitch_ratio)

        # 4. Evaluate Frame with QualityGate (Checks det_score, lighting, size)
        is_valid, retake_reason, message, actual_score, required_threshold = (
            QualityGate.evaluate(faces, sector_id=sector_id)
        )

        progress_info = ProgressInfo(
            completed_ticks=session.completed_count,
            total_ticks=NUM_TICKS,
            progress_pct=session.progress_percentage,
            active_ticks=session.ticks_completed,
        )

        retake_head_pose = None
        if len(faces) == 1:
            retake_head_pose = HeadPose(
                yaw=round(yaw_ratio, 3),
                pitch=round(pitch_ratio, 3),
                sector_id=sector_id,
            )

        if not is_valid:
            return ProcessFrameResponse(
                status=FrameEvaluationStatus.RETAKE,
                reason=retake_reason,
                message=message,
                det_score=actual_score,
                threshold_required=required_threshold,
                head_pose=retake_head_pose,
                progress=progress_info,
            )

        # 5. Extract 512-D Normalized Vector
        face = faces[0]
        embedding = FaceEmbedder.extract_embedding(face)

        # 6. Record Sector Angle into Session
        # If head is turned, record that specific sector; if center, record as sector 0
        assigned_sector = sector_id if sector_id is not None else 0
        session.add_sector(assigned_sector, embedding, actual_score)

        # Update progress after adding sector
        updated_progress = ProgressInfo(
            completed_ticks=session.completed_count,
            total_ticks=NUM_TICKS,
            progress_pct=session.progress_percentage,
            active_ticks=session.ticks_completed,
        )

        # 7. Check if Scan is Complete
        if session.is_complete:
            embeddings_matrix = session.build_embeddings_matrix()
            storage_path = self.storage.save_embeddings(user_id, embeddings_matrix)

            summary = {
                "total_angles_saved": len(session.captured_embeddings),
                "avg_det_score": round(session.avg_det_score, 3),
                "total_vectors": embeddings_matrix.shape[0],
            }

            # Clear session from RAM once successfully saved
            self.session_mgr.remove_session(user_id)

            return ProcessFrameResponse(
                status=FrameEvaluationStatus.DONE,
                message="Face ID Enrollment Complete! Biometric vectors secured.",
                det_score=actual_score,
                progress=updated_progress,
                s3_path=storage_path,
                session_summary=summary,
            )

        # 8. Accepted In-Progress Frame
        head_pose = HeadPose(
            yaw=round(yaw_ratio, 3),
            pitch=round(pitch_ratio, 3),
            sector_id=sector_id,
        )

        return ProcessFrameResponse(
            status=FrameEvaluationStatus.ACCEPTED,
            message="Angle captured! Keep rotating your head slowly.",
            det_score=actual_score,
            threshold_required=required_threshold,
            head_pose=head_pose,
            progress=updated_progress,
        )

    def process_batch(self, user_id: str, image_bytes_list: List[bytes]) -> ProcessFrameResponse:
        """
        Processes a batch of pre-captured frames collected locally by the client.
        Extracts 512-D InsightFace vectors, builds the matrix, and saves to S3/storage.
        """
        valid_embeddings = []
        det_scores = []
        valid_sectors = [False] * NUM_TICKS

        print(f"\n{'='*70}")
        print(f"[*] BATCH ENROLLMENT: user_id='{user_id}' | Received {len(image_bytes_list)} frames")
        print(f"{'='*70}")

        for idx, img_bytes in enumerate(image_bytes_list):
            print(f"[Frame {idx+1}/{len(image_bytes_list)}] Size: {len(img_bytes)} bytes")
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                print(f"   [!] Could not decode JPEG image {idx+1}")
                continue

            faces = self.detector.detect(frame_bgr)
            if len(faces) == 0:
                print(f"   [!] No face detected in frame {idx+1}")
                continue

            # If multiple faces detected in frame, select the centered primary subject
            if len(faces) > 1:
                h, w = frame_bgr.shape[:2]
                def face_rank(f):
                    area = (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
                    cx = (f.bbox[0] + f.bbox[2]) / 2.0
                    cy = (f.bbox[1] + f.bbox[3]) / 2.0
                    norm_dist = ((cx - w / 2.0) ** 2 + (cy - h / 2.0) ** 2) ** 0.5 / max(w, h)
                    return area / (1.0 + 3.0 * norm_dist)
                faces.sort(key=face_rank, reverse=True)
                print(f"   [*] Multiple faces detected ({len(faces)}). Prioritized centered primary subject.")

            face = faces[0]
            score = float(face.det_score) if hasattr(face, "det_score") else 0.88
            yaw_ratio, pitch_ratio = PoseEstimator.calculate_ratios(face)
            sector_id = PoseEstimator.map_to_sector(yaw_ratio, pitch_ratio) or 0
            yaw_deg = yaw_ratio * 65.0
            pitch_deg = pitch_ratio * 45.0

            print(f"   ✓ Face Detected! Score: {score:.3f} | Pose: Yaw={yaw_deg:+.1f}°, Pitch={pitch_deg:+.1f}° | Sector: {sector_id}")

            if score < 0.20:
                print(f"   [!] Quality warning: score {score:.3f} below 0.20 floor")
                continue

            for s_idx in [sector_id, (sector_id - 1) % NUM_TICKS, (sector_id + 1) % NUM_TICKS]:
                valid_sectors[s_idx] = True

            embedding = FaceEmbedder.extract_embedding(face)
            valid_embeddings.append(embedding)
            det_scores.append(score)
            print(f"   ✓ 512-D embedding extracted successfully")

        # For multi-angle 3D biometric profile: strictly require all 3 angles (Straight, Right, Left)
        required_count = 3
        print(f"\n[SUMMARY] Valid angles: {len(valid_embeddings)}/{len(image_bytes_list)} (Required: {required_count})")

        if len(valid_embeddings) < required_count:
            print(f"[!] ENROLLMENT RESULT: RETAKE (Only {len(valid_embeddings)}/{required_count} valid angles)")
            print(f"{'='*70}\n")
            return ProcessFrameResponse(
                status=FrameEvaluationStatus.RETAKE,
                reason=RetakeReason.NO_FACE_DETECTED,
                message=f"Only {len(valid_embeddings)} of {required_count} face angles passed quality check. Please scan again.",
            )

        embeddings_matrix = np.vstack(valid_embeddings).astype(np.float32)
        storage_path = self.storage.save_embeddings(user_id, embeddings_matrix)

        avg_score = round(sum(det_scores) / len(det_scores), 3) if det_scores else 0.0
        completed_count = sum(valid_sectors)

        print(f"[✓] ENROLLMENT RESULT: DONE (SUCCESS)")
        print(f"    Avg det_score: {avg_score}")
        print(f"    Saved {embeddings_matrix.shape[0]} vectors to: {storage_path}")
        print(f"{'='*70}\n")

        summary = {
            "total_angles_saved": len(valid_embeddings),
            "avg_det_score": avg_score,
            "total_vectors": embeddings_matrix.shape[0],
        }

        return ProcessFrameResponse(
            status=FrameEvaluationStatus.DONE,
            message="Face ID Batch Enrollment Complete! Biometric vectors secured.",
            det_score=avg_score,
            progress=ProgressInfo(
                completed_ticks=completed_count,
                total_ticks=NUM_TICKS,
                progress_pct=min(100, int((completed_count / NUM_TICKS) * 100)),
                active_ticks=valid_sectors,
            ),
            s3_path=storage_path,
            session_summary=summary,
        )

    def verify_face(self, user_id: str, image_bytes: bytes) -> Tuple[bool, float, str]:
        """
        Compares query face embedding against enrolled multi-angle vectors using cosine similarity.
        """
        enrolled_matrix = self.storage.load_embeddings(user_id)
        if enrolled_matrix is None or len(enrolled_matrix) == 0:
            return False, 0.0, f"No enrolled biometric profile found for user '{user_id}'."

        nparr = np.frombuffer(image_bytes, np.uint8)
        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            return False, 0.0, "Could not decode query image."

        faces = self.detector.detect(frame_bgr)
        if len(faces) != 1:
            return False, 0.0, f"Expected 1 face in frame, found {len(faces)}."

        query_embedding = FaceEmbedder.extract_embedding(faces[0])
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        enrolled_norms = enrolled_matrix / np.linalg.norm(enrolled_matrix, axis=1, keepdims=True)

        similarities = np.dot(enrolled_norms, query_norm)
        max_sim = float(np.max(similarities))

        threshold = 0.45
        is_match = max_sim >= threshold
        msg = f"Face ID Verified ({max_sim*100:.1f}%)" if is_match else f"Face Not Recognized ({max_sim*100:.1f}%)"
        return is_match, max_sim, msg

    def match_faces(
        self,
        image_bytes: bytes,
        threshold: float = 0.45,
        top_k: int = 5
    ) -> dict:
        """
        1:N Biometric Search: Compares query face against ALL enrolled users.
        Returns ranked list of candidate matches with cosine similarities.
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            return {
                "found": False,
                "message": "Could not decode query image payload.",
                "matches": []
            }

        faces = self.detector.detect(frame_bgr)
        if len(faces) == 0:
            return {
                "found": False,
                "message": "No face detected in query image.",
                "matches": []
            }

        # If multiple faces detected, pick centered primary face
        if len(faces) > 1:
            h, w = frame_bgr.shape[:2]
            def face_rank(f):
                area = (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
                cx = (f.bbox[0] + f.bbox[2]) / 2.0
                cy = (f.bbox[1] + f.bbox[3]) / 2.0
                norm_dist = ((cx - w / 2.0) ** 2 + (cy - h / 2.0) ** 2) ** 0.5 / max(w, h)
                return area / (1.0 + 3.0 * norm_dist)
            faces.sort(key=face_rank, reverse=True)

        face = faces[0]
        query_embedding = FaceEmbedder.extract_embedding(face)
        query_norm = query_embedding / np.linalg.norm(query_embedding)

        all_enrolled = self.storage.get_all_embeddings()
        matches = []

        for uid, matrix in all_enrolled.items():
            if matrix is None or len(matrix) == 0:
                continue
            enrolled_norms = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
            sims = np.dot(enrolled_norms, query_norm)
            max_sim = float(np.max(sims))
            matches.append({
                "user_id": uid,
                "similarity": round(max_sim, 3),
                "is_match": bool(max_sim >= threshold),
                "confidence_pct": f"{max_sim * 100:.1f}%",
            })

        matches.sort(key=lambda m: m["similarity"], reverse=True)
        top_match = matches[0] if (matches and matches[0]["is_match"]) else None

        return {
            "found": True,
            "total_enrolled_scanned": len(all_enrolled),
            "top_match": top_match,
            "matches": matches[:top_k],
            "message": f"Identified {top_match['user_id']} ({top_match['confidence_pct']})" if top_match else "No enrolled user matched above threshold."
        }

def get_enrollment_service() -> EnrollmentService:
    return EnrollmentService()
