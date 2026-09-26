import io
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import numpy as np

from app.core.config import settings

class BaseStorageService(ABC):
    """Abstract interface for biometric embedding storage."""

    @abstractmethod
    def save_embeddings(self, user_id: str, embeddings_matrix: np.ndarray) -> str:
        """Saves (N, 512) embeddings matrix and returns the storage URI."""
        pass

    @abstractmethod
    def load_embeddings(self, user_id: str) -> Optional[np.ndarray]:
        """Loads (N, 512) embeddings matrix for a user."""
        pass

    @abstractmethod
    def get_all_embeddings(self) -> dict:
        """Returns dict of {user_id: embeddings_matrix} for all enrolled users."""
        pass


class S3StorageService(BaseStorageService):
    """AWS S3 implementation with KMS/AES256 encryption and in-memory streaming."""

    def __init__(self, bucket_name: str, region: str):
        import boto3
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )

    def save_embeddings(self, user_id: str, embeddings_matrix: np.ndarray) -> str:
        buffer = io.BytesIO()
        np.save(buffer, embeddings_matrix)
        buffer.seek(0)

        s3_key = f"users/{user_id}/biometric/active/embeddings.npy"
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=buffer.getvalue(),
            ServerSideEncryption="AES256",
            ContentType="application/octet-stream",
        )
        return f"s3://{self.bucket_name}/{s3_key}"

    def load_embeddings(self, user_id: str) -> Optional[np.ndarray]:
        s3_key = f"users/{user_id}/biometric/active/embeddings.npy"
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            buffer = io.BytesIO(response["Body"].read())
            buffer.seek(0)
            return np.load(buffer)
        except Exception as e:
            print(f"[-] S3 download error for {user_id}: {e}")
            return None

    def get_all_embeddings(self) -> dict:
        results = {}
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix="users/"):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if key.endswith("/biometric/active/embeddings.npy"):
                        parts = key.split("/")
                        if len(parts) >= 2:
                            uid = parts[1]
                            emb = self.load_embeddings(uid)
                            if emb is not None:
                                results[uid] = emb
        except Exception as e:
            print(f"[-] S3 list_objects error: {e}")
        return results


class LocalStorageService(BaseStorageService):
    """Local filesystem storage for offline development and testing."""

    def __init__(self, base_dir: Path = settings.LOCAL_STORAGE_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_embeddings(self, user_id: str, embeddings_matrix: np.ndarray) -> str:
        user_dir = self.base_dir / "users" / user_id / "biometric" / "active"
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / "embeddings.npy"
        np.save(str(file_path), embeddings_matrix)
        return str(file_path.resolve())

    def load_embeddings(self, user_id: str) -> Optional[np.ndarray]:
        file_path = self.base_dir / "users" / user_id / "biometric" / "active" / "embeddings.npy"
        if file_path.exists():
            return np.load(str(file_path))
        return None

    def get_all_embeddings(self) -> dict:
        results = {}
        users_dir = self.base_dir / "users"
        if users_dir.exists():
            for u_dir in users_dir.iterdir():
                if u_dir.is_dir():
                    emb_file = u_dir / "biometric" / "active" / "embeddings.npy"
                    if emb_file.exists():
                        try:
                            results[u_dir.name] = np.load(str(emb_file))
                        except Exception:
                            pass
        return results


class InMemoryStorageService(BaseStorageService):
    """In-memory storage with optional disk mirror for session persistence."""

    def __init__(self, persist_dir: Path = settings.LOCAL_STORAGE_DIR):
        self._store = {}
        self.persist_dir = Path(persist_dir)
        # Preload any existing vectors from local disk so they remain available after server restart
        if self.persist_dir.exists():
            users_dir = self.persist_dir / "users"
            if users_dir.exists():
                for u_dir in users_dir.iterdir():
                    if u_dir.is_dir():
                        emb_file = u_dir / "biometric" / "active" / "embeddings.npy"
                        if emb_file.exists():
                            try:
                                self._store[u_dir.name] = np.load(str(emb_file))
                            except Exception:
                                pass
        if self._store:
            print(f"[*] Preloaded {len(self._store)} enrolled users into memory cache.")

    def save_embeddings(self, user_id: str, embeddings_matrix: np.ndarray) -> str:
        self._store[user_id] = embeddings_matrix
        # Persist to disk mirror for restart survivability
        try:
            user_dir = self.persist_dir / "users" / user_id / "biometric" / "active"
            user_dir.mkdir(parents=True, exist_ok=True)
            np.save(str(user_dir / "embeddings.npy"), embeddings_matrix)
        except Exception:
            pass
        return f"in-memory://users/{user_id}/active/embeddings"

    def load_embeddings(self, user_id: str) -> Optional[np.ndarray]:
        return self._store.get(user_id)

    def get_all_embeddings(self) -> dict:
        return self._store.copy()


_in_memory_instance = InMemoryStorageService()

def get_storage_service() -> BaseStorageService:
    """Returns storage service instance."""
    if settings.AWS_ACCESS_KEY_ID and settings.S3_BUCKET_NAME:
        try:
            return S3StorageService(bucket_name=settings.S3_BUCKET_NAME, region=settings.AWS_REGION)
        except Exception as e:
            print(f"[-] Failed to initialize S3StorageService: {e}. Falling back to in-memory.")
    return _in_memory_instance
