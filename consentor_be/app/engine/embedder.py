import numpy as np

class FaceEmbedder:
    """Extracts normalized 512-D deep feature embeddings."""

    @staticmethod
    def extract_embedding(face) -> np.ndarray:
        """Returns the normalized (512,) float32 embedding vector for a detected face."""
        embedding = face.normed_embedding
        return np.array(embedding, dtype=np.float32)
