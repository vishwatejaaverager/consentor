from typing import Dict, List, Optional
import numpy as np

from app.core.constants import NUM_TICKS, MIN_COMPLETED_TICKS

class EnrollmentSession:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.ticks_completed: List[bool] = [False] * NUM_TICKS
        self.captured_embeddings: Dict[int, np.ndarray] = {}
        self.det_scores: List[float] = []

    def add_sector(self, sector_id: int, embedding: np.ndarray, det_score: float):
        """Marks the sector as completed and saves its best 512-D embedding."""
        # Include current and adjacent ticks for smooth coverage like iOS
        for idx in [sector_id, (sector_id - 1) % NUM_TICKS, (sector_id + 1) % NUM_TICKS]:
            self.ticks_completed[idx] = True

        self.captured_embeddings[sector_id] = embedding
        self.det_scores.append(det_score)

    @property
    def completed_count(self) -> int:
        return sum(self.ticks_completed)

    @property
    def progress_percentage(self) -> int:
        return int((self.completed_count / NUM_TICKS) * 100)

    @property
    def is_complete(self) -> bool:
        return self.completed_count >= MIN_COMPLETED_TICKS

    @property
    def avg_det_score(self) -> float:
        if not self.det_scores:
            return 0.0
        return float(sum(self.det_scores) / len(self.det_scores))

    def build_embeddings_matrix(self) -> np.ndarray:
        """Stacks all unique angle embeddings into one (N, 512) matrix."""
        vectors = list(self.captured_embeddings.values())
        if not vectors:
            return np.empty((0, 512), dtype=np.float32)
        return np.vstack(vectors).astype(np.float32)


class SessionManager:
    """Singleton session manager tracking in-flight enrollment scans."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance.sessions: Dict[str, EnrollmentSession] = {}
        return cls._instance

    def get_or_create_session(self, user_id: str) -> EnrollmentSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = EnrollmentSession(user_id)
        return self.sessions[user_id]

    def reset_session(self, user_id: str) -> EnrollmentSession:
        self.sessions[user_id] = EnrollmentSession(user_id)
        return self.sessions[user_id]

    def remove_session(self, user_id: str):
        self.sessions.pop(user_id, None)

_session_manager = SessionManager()

def get_session_manager() -> SessionManager:
    return _session_manager
