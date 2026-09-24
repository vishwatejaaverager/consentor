#!/usr/bin/env python3
import sys
import os
import math
import cv2
import numpy as np
import json
import subprocess
from pathlib import Path

# Resolve virtual environment site-packages if needed
VENV_PATH = Path(__file__).parent / ".venv" / "lib"
if VENV_PATH.exists():
    for site_pkg in VENV_PATH.glob("python*/site-packages"):
        if str(site_pkg) not in sys.path:
            sys.path.insert(0, str(site_pkg))

from insightface.app import FaceAnalysis

DATA_DIR = Path("enrolled_face_data")
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
METADATA_PATH = DATA_DIR / "metadata.json"
IMAGES_DIR = DATA_DIR / "images"

# Aesthetic Colors
BG_COLOR = (20, 20, 26)
CARD_BG = (32, 32, 42)
TEXT_WHITE = (250, 250, 250)
TEXT_GRAY = (160, 160, 175)
GREEN_MATCH = (90, 230, 110)
RED_MISMATCH = (80, 80, 240)
ACCENT_BLUE = (240, 160, 60)

def pick_file_macos():
    """Opens macOS native Finder file dialog to pick an image file"""
    try:
        cmd = 'POSIX path of (choose file with prompt "Select a face image to test against Face ID embeddings:" of type {"public.image"})'
        res = subprocess.run(["osascript", "-e", cmd], capture_output=True, text=True)
        path_str = res.stdout.strip()
        if path_str and os.path.exists(path_str):
            return path_str
    except Exception as e:
        print(f"File picker error: {e}")
    return None

def load_image_any_format(image_path):
    """Loads image of any format including Apple HEIC/HEIF using OpenCV, macOS sips, or PIL"""
    if not image_path or not os.path.exists(image_path):
        return None
        
    # 1. Standard OpenCV imread
    img = cv2.imread(image_path)
    if img is not None:
        return img
        
    # 2. If HEIC or unsupported format, convert using macOS built-in sips CLI
    ext = Path(image_path).suffix.lower()
    if ext in ['.heic', '.heif', '.avif', '.webp', '.tiff']:
        try:
            temp_jpg = Path("/tmp") / f"converted_{Path(image_path).stem}.jpg"
            res = subprocess.run(["sips", "-s", "format", "jpeg", str(image_path), "--out", str(temp_jpg)],
                                 capture_output=True, text=True)
            if res.returncode == 0 and temp_jpg.exists():
                img = cv2.imread(str(temp_jpg))
                temp_jpg.unlink(missing_ok=True)
                if img is not None:
                    return img
        except Exception as e:
            print(f"HEIC conversion notice: {e}")

    # 3. Fallback to PIL Image
    try:
        from PIL import Image
        pil_img = Image.open(image_path).convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return img
    except Exception as e:
        print(f"PIL image read notice: {e}")

    return None

def resize_preserve_aspect(img, max_w, max_h, bg_color=(32, 32, 42)):
    """Resizes image maintaining original aspect ratio with centered padding"""
    h, w = img.shape[:2]
    scale = min(max_w / w, max_h / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    container = np.full((max_h, max_w, 3), bg_color, dtype=np.uint8)
    
    dx = (max_w - nw) // 2
    dy = (max_h - nh) // 2
    container[dy:dy+nh, dx:dx+nw] = resized
    return container

class FaceIDVerificationUI:
    def __init__(self, canvas_w=1080, canvas_h=720):
        self.width = canvas_w
        self.height = canvas_h
        
        print("[+] Loading InsightFace Model for verification...")
        self.app = FaceAnalysis(name="buffalo_l", providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        print("[+] InsightFace Model Ready!")
        
        if not EMBEDDINGS_PATH.exists():
            print(f"Error: Enrolled database '{EMBEDDINGS_PATH}' not found!")
            print("Please run 'python3 face_id_app.py' first to complete enrollment.")
            sys.exit(1)
            
        self.enrolled_embeddings = np.load(str(EMBEDDINGS_PATH)) # (60, 512)
        print(f"[+] Loaded {len(self.enrolled_embeddings)} enrolled angle embeddings from '{EMBEDDINGS_PATH}'.")
        
        # Load metadata if available
        self.metadata = []
        if METADATA_PATH.exists():
            with open(METADATA_PATH, "r") as f:
                self.metadata = json.load(f)

    def analyze_image(self, image_path):
        img_bgr = load_image_any_format(image_path)
        if img_bgr is None:
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            return {
                "success": False,
                "error": f"Could not read or format image '{Path(image_path).name}'",
                "image_bgr": placeholder
            }
            
        faces = self.app.get(img_bgr)
        if len(faces) == 0:
            return {
                "success": False,
                "error": "No face detected in the selected image.",
                "image_bgr": img_bgr
            }
            
        query_face = faces[0]
        query_emb = query_face.normed_embedding # (512,)
        
        # Calculate Cosine Similarities against all 60 enrolled angle vectors
        similarities = np.dot(self.enrolled_embeddings, query_emb)
        
        max_idx = int(np.argmax(similarities))
        max_similarity = float(similarities[max_idx])
        avg_similarity = float(np.mean(similarities))
        min_similarity = float(np.min(similarities))
        
        bbox = query_face.bbox.astype(int)
        
        best_match_filename = f"sector_{max_idx:02d}.jpg"
        if max_idx < len(self.metadata):
            best_match_filename = self.metadata[max_idx].get("filename", best_match_filename)
            
        best_match_img_path = IMAGES_DIR / best_match_filename
        best_match_bgr = None
        if best_match_img_path.exists():
            best_match_bgr = cv2.imread(str(best_match_img_path))
            
        is_match = max_similarity >= 0.45
        
        return {
            "success": True,
            "image_bgr": img_bgr,
            "bbox": bbox,
            "det_score": float(query_face.det_score),
            "max_similarity": max_similarity,
            "avg_similarity": avg_similarity,
            "min_similarity": min_similarity,
            "best_sector_idx": max_idx,
            "best_match_filename": best_match_filename,
            "best_match_bgr": best_match_bgr,
            "all_similarities": similarities,
            "is_match": is_match
        }

    def render_results_ui(self, results, image_filename="Uploaded Image"):
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        canvas[:] = BG_COLOR
        
        # 1. Header Banner
        cv2.putText(canvas, "Face ID Vector Matcher & Analyzer", (40, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, TEXT_WHITE, 2, cv2.LINE_AA)
        cv2.putText(canvas, f"Comparing against enrolled dataset: {EMBEDDINGS_PATH}", (40, 78),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_GRAY, 1, cv2.LINE_AA)

        if not results["success"]:
            cv2.rectangle(canvas, (40, 110), (self.width - 40, self.height - 100), CARD_BG, -1)
            cv2.putText(canvas, f"Analysis Error: {results['error']}", (70, 200),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, RED_MISMATCH, 2, cv2.LINE_AA)
            cv2.putText(canvas, "Press 'O' or ENTER to choose another image.", (70, 250),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_GRAY, 1, cv2.LINE_AA)
            return canvas

        img_bgr = results["image_bgr"].copy()
        bbox = results["bbox"]
        max_sim = results["max_similarity"]
        avg_sim = results["avg_similarity"]
        best_idx = results["best_sector_idx"]
        is_match = results["is_match"]
        similarities = results["all_similarities"]
        
        # Draw bounding box
        box_color = GREEN_MATCH if is_match else RED_MISMATCH
        cv2.rectangle(img_bgr, (bbox[0], bbox[1]), (bbox[2], bbox[3]), box_color, 3)
        cv2.putText(img_bgr, f"Score: {max_sim*100:.1f}%", (bbox[0], max(0, bbox[1] - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2, cv2.LINE_AA)

        # 2. Side-by-Side Display Cards
        panel_w = 460
        panel_h = 380
        top_y = 110
        
        # Left Panel: Query Image
        cv2.rectangle(canvas, (40, top_y), (40 + panel_w, top_y + panel_h), CARD_BG, -1)
        cv2.putText(canvas, f"Uploaded: {Path(image_filename).name[:28]}", (55, top_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_WHITE, 1, cv2.LINE_AA)
        
        # Render with preserved aspect ratio
        q_img_resized = resize_preserve_aspect(img_bgr, panel_w - 30, panel_h - 60)
        canvas[top_y + 45 : top_y + 45 + (panel_h - 60), 55 : 55 + (panel_w - 30)] = q_img_resized
        
        # Right Panel: Best Matching Enrolled Image
        right_x = self.width - 40 - panel_w
        cv2.rectangle(canvas, (right_x, top_y), (right_x + panel_w, top_y + panel_h), CARD_BG, -1)
        cv2.putText(canvas, f"Best Match Enrolled Angle: Sector #{best_idx} ({results['best_match_filename']})",
                    (right_x + 15, top_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, TEXT_WHITE, 1, cv2.LINE_AA)
        
        if results["best_match_bgr"] is not None:
            m_img_resized = resize_preserve_aspect(results["best_match_bgr"], panel_w - 30, panel_h - 60)
            canvas[top_y + 45 : top_y + 45 + (panel_h - 60), right_x + 15 : right_x + 15 + (panel_w - 30)] = m_img_resized

        # 3. Verdict & Stats Bottom Panel
        bottom_y = top_y + panel_h + 20
        bottom_h = self.height - bottom_y - 30
        cv2.rectangle(canvas, (40, bottom_y), (self.width - 40, bottom_y + bottom_h), CARD_BG, -1)

        # Verdict Badge
        verdict_str = "AUTHENTICATION SUCCESS (MATCH VERIFIED)" if is_match else "ACCESS DENIED (UNKNOWN / LOW SIMILARITY)"
        badge_color = GREEN_MATCH if is_match else RED_MISMATCH
        
        cv2.putText(canvas, verdict_str, (60, bottom_y + 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, badge_color, 2, cv2.LINE_AA)
                    
        # Metrics Breakdown
        match_pct = max_sim * 100.0
        avg_pct = avg_sim * 100.0
        
        cv2.putText(canvas, f"Max Similarity (Best Angle): {match_pct:.2f}%", (60, bottom_y + 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, TEXT_WHITE, 1, cv2.LINE_AA)
        cv2.putText(canvas, f"Mean Similarity (All Angles): {avg_pct:.2f}%", (60, bottom_y + 102),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_GRAY, 1, cv2.LINE_AA)

        # Draw similarity meter bar
        meter_x = 550
        meter_y = bottom_y + 45
        meter_w = 450
        meter_h = 24
        
        cv2.rectangle(canvas, (meter_x, meter_y), (meter_x + meter_w, meter_y + meter_h), (50, 50, 60), -1)
        fill_w = int(meter_w * min(1.0, max(0.0, max_sim)))
        cv2.rectangle(canvas, (meter_x, meter_y), (meter_x + fill_w, meter_y + meter_h), badge_color, -1)
        cv2.putText(canvas, f"Match Probability: {match_pct:.1f}%", (meter_x + 10, meter_y + 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0) if fill_w > 180 else TEXT_WHITE, 1, cv2.LINE_AA)

        # Draw sector similarity sparkline histogram across 60 angles
        hist_x = meter_x
        hist_y = bottom_y + 85
        hist_w = meter_w
        hist_h = 50
        cv2.rectangle(canvas, (hist_x, hist_y), (hist_x + hist_w, hist_y + hist_h), (25, 25, 35), -1)
        
        num_sectors = len(similarities)
        bar_step = hist_w / float(num_sectors)
        
        for i, sim in enumerate(similarities):
            h_bar = int(hist_h * max(0.0, sim))
            bx = int(hist_x + i * bar_step)
            by = hist_y + hist_h - h_bar
            b_color = GREEN_MATCH if i == best_idx else (120, 160, 200)
            cv2.rectangle(canvas, (bx, by), (int(bx + bar_step - 1), hist_y + hist_h), b_color, -1)

        cv2.putText(canvas, "Sector Angle Match Spectrum (0° - 360°)", (hist_x, hist_y + hist_h + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, TEXT_GRAY, 1, cv2.LINE_AA)
        
        # Footer Action instruction
        cv2.putText(canvas, "Press 'O' to Select Another Image | 'Q' to Quit", (40, self.height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, TEXT_GRAY, 1, cv2.LINE_AA)

        return canvas

    def run(self, initial_image=None):
        target_file = initial_image
        if not target_file:
            print("[+] Opening macOS file picker to select an image...")
            target_file = pick_file_macos()
            
        if not target_file:
            print("No image selected. Exiting.")
            return

        window_name = "Face ID - Vector Match & Probability Analyzer"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

        while True:
            print(f"\n[+] Analyzing image: '{target_file}'...")
            results = self.analyze_image(target_file)
            
            canvas = self.render_results_ui(results, target_file)
            cv2.imshow(window_name, canvas)
            
            # Wait loop to handle keys and window close button ('X')
            should_quit = False
            should_pick_new = False

            while True:
                # Check if window was closed via the 'X' button
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    should_quit = True
                    break

                key = cv2.waitKey(50) & 0xFF
                if key in [27, ord('q'), ord('Q')]:  # ESC, q, Q
                    should_quit = True
                    break
                elif key in [ord('o'), ord('O'), 13, 32]:  # 'o', 'O', ENTER, SPACE
                    should_pick_new = True
                    break

            if should_quit:
                print("Exiting Verifier App.")
                break

            if should_pick_new:
                new_file = pick_file_macos()
                if new_file:
                    target_file = new_file

        cv2.destroyAllWindows()
        cv2.waitKey(1)  # Ensure window is destroyed on macOS

if __name__ == "__main__":
    initial_img = sys.argv[1] if len(sys.argv) > 1 else None
    app = FaceIDVerificationUI()
    app.run(initial_img)
