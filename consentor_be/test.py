import cv2
import numpy as np
from insightface.app import FaceAnalysis

app = FaceAnalysis(name="buffalo_l")

reference = cv2.imread("reference.jpg")
query = cv2.imread("q.png")

reference_faces = app.get(reference)
query_faces = app.get(query)

if len(reference_faces) != 1:
    raise ValueError(f"Reference image has {len(reference_faces)} faces")

if len(query_faces) != 1:
    raise ValueError(f"Query image has {len(query_faces)} faces")

reference_embedding = reference_faces[0].normed_embedding
query_embedding = query_faces[0].normed_embedding

similarity = np.dot(reference_embedding, query_embedding)

print(f"Similarity: {similarity:.4f}")