import os
import cv2
import numpy as np
import json
from pathlib import Path
from insightface.app import FaceAnalysis

class FaceIDEmbedder:
    def __init__(self, data_dir="enrolled_face_data"):
        self.data_dir = Path(data_dir)
        self.images_dir = self.data_dir / "images"
        self.db_path = self.data_dir / "embeddings.npy"
        self.meta_path = self.data_dir / "metadata.json"
        
        print("Initializing InsightFace model (buffalo_l)...")
        self.app = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        print("InsightFace Model ready!")

    def process_enrolled_dataset(self):
        """Processes all captured angle face images and generates normalized 512D embeddings"""
        if not self.images_dir.exists():
            print(f"Error: Directory '{self.images_dir}' not found. Run enrollment app first.")
            return False

        image_files = list(self.images_dir.glob("*.jpg"))
        if not image_files:
            print(f"No face images found in '{self.images_dir}'.")
            return False

        print(f"\nProcessing {len(image_files)} multi-angle face captures...")
        embeddings = []
        metadata = []

        for img_path in sorted(image_files):
            img = cv2.imread(str(img_path))
            if img is None:
                continue

            faces = self.app.get(img)
            if len(faces) > 0:
                # Extract normalized embedding (512-dimensional vector)
                emb = faces[0].normed_embedding
                embeddings.append(emb)
                metadata.append({
                    "filename": img_path.name,
                    "bbox": faces[0].bbox.tolist(),
                    "det_score": float(faces[0].det_score)
                })
                print(f"  [✓] Encoded {img_path.name} (Detection confidence: {faces[0].det_score:.2f})")

        if len(embeddings) == 0:
            print("Error: Could not extract embeddings from captured images.")
            return False

        # Save embeddings matrix (N, 512)
        embeddings_matrix = np.array(embeddings, dtype=np.float32)
        np.save(str(self.db_path), embeddings_matrix)
        
        with open(self.meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"\nSuccessfully compiled enrolled Face ID database!")
        print(f"Saved database shape: {embeddings_matrix.shape} -> '{self.db_path}'")
        return True

    def verify_live_face(self, frame_bgr, threshold=0.45):
        """Compares a live query face against the enrolled multi-angle embeddings"""
        if not self.db_path.exists():
            return False, 0.0, "No enrolled database found"

        enrolled_embeddings = np.load(str(self.db_path)) # (N, 512)
        
        query_faces = self.app.get(frame_bgr)
        if len(query_faces) == 0:
            return False, 0.0, "No face detected"

        query_emb = query_faces[0].normed_embedding # (512,)
        
        # Calculate cosine similarity across all enrolled angles
        # similarity = dot product of normalized vectors
        similarities = np.dot(enrolled_embeddings, query_emb)
        max_similarity = float(np.max(similarities))
        
        is_match = max_similarity >= threshold
        status = "ACCESS GRANTED" if is_match else "ACCESS DENIED"
        
        return is_match, max_similarity, status

if __name__ == "__main__":
    embedder = FaceIDEmbedder()
    embedder.process_enrolled_dataset()
