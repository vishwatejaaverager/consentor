import sys
import cv2
from pathlib import Path
from typing import List, Any

# Ensure workspace .venv site-packages is in sys.path if available
VENV_LIB = Path(__file__).resolve().parents[2] / ".venv" / "lib"
if VENV_LIB.exists():
    for site_pkg in VENV_LIB.glob("python*/site-packages"):
        if str(site_pkg) not in sys.path:
            sys.path.insert(0, str(site_pkg))

from insightface.app import FaceAnalysis

class FaceDetector:
    """Singleton wrapper for InsightFace buffalo_l engine."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FaceDetector, cls).__new__(cls)
            print("[+] Initializing InsightFace buffalo_l detector...")
            cls._instance.app = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
            cls._instance.app.prepare(ctx_id=0, det_thresh=0.20, det_size=(640, 640))
            print("[+] InsightFace engine ready with det_thresh=0.20!")
        return cls._instance

    def detect(self, image_bgr) -> List[Any]:
        """Detect faces and landmarks in a BGR numpy image with robust auto-padding fallback."""
        if image_bgr is None:
            return []
        
        faces = self.app.get(image_bgr)
        if len(faces) == 0:
            # If directly finding 0 faces (often due to tight image framing or angle), try with 30% padding
            h, w = image_bgr.shape[:2]
            pad = int(max(h, w) * 0.30)
            padded = cv2.copyMakeBorder(image_bgr, pad, pad, pad, pad, cv2.BORDER_REFLECT)
            padded_faces = self.app.get(padded)
            if len(padded_faces) > 0:
                for f in padded_faces:
                    f.bbox[0] = max(0, f.bbox[0] - pad)
                    f.bbox[1] = max(0, f.bbox[1] - pad)
                    f.bbox[2] = min(w, f.bbox[2] - pad)
                    f.bbox[3] = min(h, f.bbox[3] - pad)
                    if hasattr(f, 'kps') and f.kps is not None:
                        f.kps[:, 0] -= pad
                        f.kps[:, 1] -= pad
                return padded_faces

            # Second fallback: slight histogram equalization in case of lighting drop during head turn
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_gray = clahe.apply(gray)
            enhanced_bgr = cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)
            enh_faces = self.app.get(enhanced_bgr)
            if len(enh_faces) > 0:
                return enh_faces

        return faces
