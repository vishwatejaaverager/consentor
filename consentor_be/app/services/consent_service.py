import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

DB_PATH = Path(__file__).resolve().parents[2] / "consentor.db"

class ConsentService:
    """Manages chat_id consent lifecycle, TTL expirations, and SQLite persistence."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consent_requests (
                    request_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    expires_at TEXT
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_consent_chat ON consent_requests(chat_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_requests(user_id);")
            conn.commit()

    def create_request(
        self,
        user_id: str,
        chat_id: str,
        ttl_hours: float = 24.0,
        base_url: str = ""
    ) -> Dict[str, Any]:
        """Creates a pending consent request and returns the portal scan link."""
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO consent_requests (request_id, user_id, chat_id, status, created_at, expires_at)
                VALUES (?, ?, ?, 'PENDING', ?, ?)
            """, (request_id, user_id, chat_id, now.isoformat(), expires_at.isoformat()))
            conn.commit()

        portal_path = f"/portal?user_id={user_id}&chat_id={chat_id}&request_id={request_id}"
        full_url = f"{base_url.rstrip('/')}{portal_path}" if base_url else portal_path

        return {
            "request_id": request_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "status": "PENDING",
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "consent_url": full_url,
            "message": "Consent request created. Provide consent_url to the user to complete verification.",
        }

    def approve_consent(
        self,
        chat_id: str,
        user_id: Optional[str] = None,
        ttl_hours: float = 24.0
    ) -> Dict[str, Any]:
        """Approves consent for a chat_id with expiration timestamp."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Check for existing request for this chat_id
            cursor.execute("""
                SELECT request_id, user_id FROM consent_requests 
                WHERE chat_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (chat_id,))
            row = cursor.fetchone()

            if row:
                req_id = row["request_id"]
                uid = user_id or row["user_id"]
                cursor.execute("""
                    UPDATE consent_requests 
                    SET status = 'APPROVED', approved_at = ?, expires_at = ?, user_id = ?
                    WHERE request_id = ?
                """, (now.isoformat(), expires_at.isoformat(), uid, req_id))
            else:
                req_id = f"req_{uuid.uuid4().hex[:12]}"
                uid = user_id or "unknown_user"
                cursor.execute("""
                    INSERT INTO consent_requests (request_id, user_id, chat_id, status, created_at, approved_at, expires_at)
                    VALUES (?, ?, ?, 'APPROVED', ?, ?, ?)
                """, (req_id, uid, chat_id, now.isoformat(), now.isoformat(), expires_at.isoformat()))

            conn.commit()

        return {
            "request_id": req_id,
            "chat_id": chat_id,
            "user_id": uid,
            "status": "APPROVED",
            "approved_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "message": f"Consent approved successfully for chat '{chat_id}'. Valid for {ttl_hours}h.",
        }

    def check_consent(self, chat_id: str, base_url: str = "") -> Dict[str, Any]:
        """Checks if a chat_id has active, unexpired consent."""
        now = datetime.now(timezone.utc)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT request_id, user_id, chat_id, status, created_at, approved_at, expires_at 
                FROM consent_requests 
                WHERE chat_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (chat_id,))
            row = cursor.fetchone()

            if not row:
                return {
                    "consented": False,
                    "status": "NOT_REQUESTED",
                    "chat_id": chat_id,
                    "message": "No consent request found for this chat ID.",
                }

            status = row["status"]
            user_id = row["user_id"]
            expires_at_str = row["expires_at"]
            expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else None

            portal_path = f"/portal?user_id={user_id}&chat_id={chat_id}"
            full_url = f"{base_url.rstrip('/')}{portal_path}" if base_url else portal_path

            if status == "APPROVED":
                if expires_at and now < expires_at:
                    remaining_hours = round((expires_at - now).total_seconds() / 3600.0, 2)
                    return {
                        "consented": True,
                        "status": "APPROVED",
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "approved_at": row["approved_at"],
                        "expires_at": expires_at.isoformat(),
                        "remaining_hours": remaining_hours,
                        "message": "Consent is active. Generation permitted.",
                    }
                else:
                    # Expired: update status in DB
                    cursor.execute("UPDATE consent_requests SET status = 'EXPIRED' WHERE request_id = ?", (row["request_id"],))
                    conn.commit()
                    return {
                        "consented": False,
                        "status": "EXPIRED",
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "consent_url": full_url,
                        "message": "Consent has expired. User must verify again.",
                    }

            return {
                "consented": False,
                "status": "WAITING_FOR_CONSENT",
                "chat_id": chat_id,
                "user_id": user_id,
                "consent_url": full_url,
                "message": "Consent request pending. Waiting for user to complete Face ID.",
            }

    def list_consents(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM consent_requests ORDER BY created_at DESC LIMIT 100")
            return [dict(r) for r in cursor.fetchall()]


_consent_service_instance = None

def get_consent_service() -> ConsentService:
    global _consent_service_instance
    if _consent_service_instance is None:
        _consent_service_instance = ConsentService()
    return _consent_service_instance
