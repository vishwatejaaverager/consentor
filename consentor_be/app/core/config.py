import os
from pathlib import Path
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "Consentor Biometric API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # AWS S3 Settings
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    S3_BUCKET_NAME: str = os.getenv("S3_CONSENTOR_BUCKET", "consentor-biometrics")
    
    # Storage Paths
    LOCAL_STORAGE_DIR: Path = Path("enrolled_face_data")

settings = Settings()
