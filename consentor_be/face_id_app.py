#!/usr/bin/env python3
import sys
import os
import math
import cv2
import numpy as np
import time
from pathlib import Path

# Force workspace .venv python environment if available
VENV_PATH = Path(__file__).parent / ".venv" / "lib"
if VENV_PATH.exists():
    for site_pkg in VENV_PATH.glob("python*/site-packages"):
        if str(site_pkg) not in sys.path:
            sys.path.insert(0, str(site_pkg))

from face_id_embedder import FaceIDEmbedder

# Setup paths for captured face data
DATA_DIR = Path("enrolled_face_data")
DATA_DIR.mkdir(exist_ok=True)
ENROLLED_FACES_DIR = DATA_DIR / "images"
ENROLLED_FACES_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------
# Face ID UI Configuration (Apple-Style Aesthetics)
# ---------------------------------------------------------
NUM_TICKS = 60  # 60 tick marks around 360 degrees
BG_COLOR = (18, 18, 24)           # Dark charcoal/black background
TICK_INACTIVE = (65, 65, 75)      # Muted grey tick marks
TICK_ACTIVE = (95, 235, 110)      # Vibrant Apple green
TICK_ACTIVE_GLOW = (40, 160, 70)  # Subtle glow border

class FaceIDApp:
    def __init__(self, width=960, height=720):
        self.width = width
        self.height = height
        
        # Center circle geometry
        self.center_x = width // 2
        self.center_y = height // 2 - 30
        self.radius = 170
        self.tick_length = 18
        self.tick_inner_r = self.radius + 15
        self.tick_outer_r = self.tick_inner_r + self.tick_length
        
        # Ticks activation state (60 sectors)
        self.ticks_completed = [False] * NUM_TICKS
        self.captured_images = {}
        
        # App State
        self.state = "ENROLLING"  # "ENROLLING", "COMPLETE", "VERIFYING"
        self.verification_score = 0.0
        self.verification_status = ""
        
        # Initialize Embedder / Face Analyzer
        print("[+] Initializing InsightFace Engine...")
        self.embedder = FaceIDEmbedder(data_dir=DATA_DIR)
        print("[+] Engine Ready!")

    def calculate_head_pose_ratios(self, face):
        """Calculates normalized Yaw and Pitch pose ratios from facial keypoints"""
        kps = face.kps # 5 keypoints: left_eye, right_eye, nose, left_mouth, right_mouth
        left_eye, right_eye, nose = kps[0], kps[1], kps[2]
        
        eye_center_x = (left_eye[0] + right_eye[0]) / 2.0
        eye_center_y = (left_eye[1] + right_eye[1]) / 2.0
        
        eye_dist = math.sqrt((right_eye[0] - left_eye[0])**2 + (right_eye[1] - left_eye[1])**2)
        if eye_dist == 0:
            return 0.0, 0.0
            
        # Yaw ratio (horizontal offset of nose relative to eyes)
        yaw_ratio = (nose[0] - eye_center_x) / eye_dist
        
        # Pitch ratio (vertical offset of nose relative to eye line)
        pitch_ratio = (nose[1] - eye_center_y) / eye_dist - 0.55
        
        return yaw_ratio, pitch_ratio

    def draw_apple_ui(self, canvas, frame, face_detected, yaw_ratio, pitch_ratio):
        canvas[:] = BG_COLOR
        
        # 1. Composite Circular Camera View
        mask = np.zeros((self.height, self.width), dtype=np.uint8)
        cv2.circle(mask, (self.center_x, self.center_y), self.radius, 255, -1)
        
        frame_resized = cv2.resize(frame, (self.width, self.height))
        blurred_bg = cv2.GaussianBlur(frame_resized, (55, 55), 0)
        blurred_bg = (blurred_bg * 0.25).astype(np.uint8)
        
        inv_mask = cv2.bitwise_not(mask)
        bg_part = cv2.bitwise_and(blurred_bg, blurred_bg, mask=inv_mask)
        fg_part = cv2.bitwise_and(frame_resized, frame_resized, mask=mask)
        canvas[:] = cv2.add(bg_part, fg_part)
        
        # Inner ring border
        border_color = (100, 235, 120) if self.state == "COMPLETE" else (100, 100, 120)
        cv2.circle(canvas, (self.center_x, self.center_y), self.radius + 2, border_color, 2, cv2.LINE_AA)
        
        # 2. Draw 60 Radial Ticks (Face ID Ring)
        completed_count = sum(self.ticks_completed)
        progress_pct = int((completed_count / NUM_TICKS) * 100)
        
        for i in range(NUM_TICKS):
            angle_deg = (i * 360.0 / NUM_TICKS) - 90.0
            rad = math.radians(angle_deg)
            
            x1 = int(self.center_x + self.tick_inner_r * math.cos(rad))
            y1 = int(self.center_y + self.tick_inner_r * math.sin(rad))
            x2 = int(self.center_x + self.tick_outer_r * math.cos(rad))
            y2 = int(self.center_y + self.tick_outer_r * math.sin(rad))
            
            is_active = self.ticks_completed[i]
            
            if is_active:
                cv2.line(canvas, (x1, y1), (x2, y2), TICK_ACTIVE_GLOW, 6, cv2.LINE_AA)
                cv2.line(canvas, (x1, y1), (x2, y2), TICK_ACTIVE, 3, cv2.LINE_AA)
            else:
                cv2.line(canvas, (x1, y1), (x2, y2), TICK_INACTIVE, 2, cv2.LINE_AA)

        # 3. Typography & Header
        cv2.putText(canvas, "Face ID", (self.center_x - 60, 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Status Messages
        if self.state == "ENROLLING":
            if not face_detected:
                msg = "Position your face in the frame"
                color = (100, 150, 255)
            else:
                msg = f"Enrolling Face ID... ({progress_pct}%)"
                color = (255, 255, 255)
            sub = "Move your head slowly in a circle to illuminate green ticks"
        elif self.state == "COMPLETE":
            msg = "Face ID Enrollment Complete!"
            sub = "Press 'V' to test Live Verification mode | 'R' to Reset"
            color = (100, 255, 120)
        elif self.state == "VERIFYING":
            if self.verification_status == "ACCESS GRANTED":
                msg = f"Face ID Verified (Similarity: {self.verification_score:.1f}%)"
                color = (100, 255, 120)
            elif self.verification_status == "ACCESS DENIED":
                msg = f"Face Not Recognized (Similarity: {self.verification_score:.1f}%)"
                color = (80, 80, 255)
            else:
                msg = "Analyzing face..."
                color = (255, 215, 0)
            sub = "Press 'E' to return to Enrollment mode | 'R' to Reset"
            
        cv2.putText(canvas, msg, (self.center_x - (len(msg) * 7), self.height - 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)
        cv2.putText(canvas, sub, (self.center_x - (len(sub) * 5), self.height - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 170), 1, cv2.LINE_AA)

        # 4. Progress bar at bottom
        bar_w = 320
        bar_h = 6
        bar_x = self.center_x - bar_w // 2
        bar_y = self.height - 115
        
        cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 60), -1)
        fill_w = int(bar_w * (completed_count / NUM_TICKS))
        if fill_w > 0:
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), TICK_ACTIVE, -1)

    def process_rotation_and_capture(self, frame, yaw_ratio, pitch_ratio):
        mag = math.sqrt(yaw_ratio**2 + pitch_ratio**2)
        
        if mag > 0.15:  # Head is rotated away from center line
            angle_deg = (math.degrees(math.atan2(yaw_ratio, -pitch_ratio)) + 360.0) % 360.0
            tick_idx = int((angle_deg / 360.0) * NUM_TICKS) % NUM_TICKS
            
            for idx in [tick_idx, (tick_idx - 1) % NUM_TICKS, (tick_idx + 1) % NUM_TICKS]:
                if not self.ticks_completed[idx]:
                    self.ticks_completed[idx] = True
                    
                    h, w = frame.shape[:2]
                    crop_size = min(w, h)
                    crop_x = (w - crop_size) // 2
                    crop_y = (h - crop_size) // 2
                    face_crop = frame[crop_y:crop_y+crop_size, crop_x:crop_x+crop_size]
                    
                    filename = ENROLLED_FACES_DIR / f"sector_{idx:02d}.jpg"
                    cv2.imwrite(str(filename), face_crop)
                    self.captured_images[idx] = str(filename)

        if sum(self.ticks_completed) == NUM_TICKS and self.state == "ENROLLING":
            self.state = "COMPLETE"
            print("\n[+] 360-Degree Face Rotation Completed!")
            print("[+] Compiling InsightFace embedding database...")
            self.embedder.process_enrolled_dataset()

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not access camera.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        print("\n=======================================================")
        print("  Apple Face ID Python App Initialized")
        print("  Controls:")
        print("  - ESC / Q: Quit")
        print("  - R: Reset Enrollment")
        print("  - V: Toggle Verification Mode")
        print("  - E: Toggle Enrollment Mode")
        print("=======================================================\n")

        last_verify_time = 0

        window_name = "Apple Face ID - Python App"
        cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

        while True:
            # Check if user clicked window 'X' close button
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                print("Window closed by user.")
                break

            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            
            # Detect face & landmarks with InsightFace
            faces = self.embedder.app.get(frame)
            face_detected = len(faces) > 0
            yaw_ratio, pitch_ratio = 0.0, 0.0

            if face_detected:
                face = faces[0]
                yaw_ratio, pitch_ratio = self.calculate_head_pose_ratios(face)
                
                if self.state == "ENROLLING":
                    self.process_rotation_and_capture(frame, yaw_ratio, pitch_ratio)
                elif self.state == "VERIFYING":
                    curr_time = time.time()
                    if curr_time - last_verify_time > 0.4:
                        last_verify_time = curr_time
                        is_match, score, status = self.embedder.verify_live_face(frame)
                        self.verification_score = score * 100.0
                        self.verification_status = status

            self.draw_apple_ui(canvas, frame, face_detected, yaw_ratio, pitch_ratio)
            cv2.imshow(window_name, canvas)
            
            key = cv2.waitKey(1) & 0xFF
            if key in [27, ord('q'), ord('Q')]:
                break
            elif key in [ord('r'), ord('R')]:
                self.ticks_completed = [False] * NUM_TICKS
                self.state = "ENROLLING"
                print("Enrollment reset!")
            elif key in [ord('v'), ord('V')]:
                if (DATA_DIR / "embeddings.npy").exists():
                    self.state = "VERIFYING"
                else:
                    print("Please complete enrollment first before verification!")
            elif key in [ord('e'), ord('E')]:
                self.state = "ENROLLING"

        cap.release()
        cv2.destroyAllWindows()
        cv2.waitKey(1)

if __name__ == "__main__":
    app = FaceIDApp()
    app.run()
