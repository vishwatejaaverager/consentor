# Face ID & Quality Threshold Constants

NUM_TICKS = 60  # 60 sectors around 360 degrees

# Quality & Detector Thresholds
MIN_DET_SCORE_FRONTAL = 0.85  # Initial center/anchor face check
MIN_DET_SCORE_ANGLE = 0.70    # Angle / head rotation checks
MIN_BBOX_SIZE = 140           # Min bounding box width/height in px
MIN_COMPLETED_TICKS = 45      # Minimum required sectors out of 60 (~75% coverage)
MIN_SESSION_AVG_SCORE = 0.80  # Average quality across all sectors before S3 upload

# Verification Thresholds (Cosine Similarity)
VERIFY_MATCH_THRESHOLD = 0.45
VERIFY_HIGH_CONFIDENCE = 0.55
