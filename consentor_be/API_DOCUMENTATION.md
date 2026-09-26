# Consentor Biometric & Consent API Documentation

> **Base URL:** `http://localhost:8000`  
> **Interactive Swagger UI:** `http://localhost:8000/docs`  
> **ReDoc Documentation:** `http://localhost:8000/redoc`

---

## 1. Architecture Overview

Consentor provides an end-to-end consent gate for AI generation platforms (Telegram bots, Discord bots, AI character platforms, image/voice generation services).

```text
               AI Generation Protection Lifecycle
               
 [Enrolled Users] ──▶ 1. Match Face (1:N) ──▶ Identifies Target User
                              │
                              ▼
                      2. Ask Consent      ──▶ Generates Scan Link for Chat
                              │
                              ▼
                      3. User Verifies    ──▶ Stored in SQLite with Expiration
                              │
                              ▼
                      4. Check Consent    ──▶ ALLOW or BLOCK Generation
```

---

## 2. API Endpoints Reference

### Group A: Consent Management

#### 1. Check Consent Status
Checks whether a `chat_id` has an active, unexpired consent approval. Call this **before** generating any AI output.

* **Method:** `GET`
* **Path:** `/api/v1/consent/check`
* **Query Parameters:**
  * `chat_id` (string, required): The unique chat or session ID.

##### Example Request:
```bash
curl -X GET "http://localhost:8000/api/v1/consent/check?chat_id=tg_chat_8829"
```

##### Response — When Allowed (Active < 24h):
```json
{
  "consented": true,
  "status": "APPROVED",
  "chat_id": "tg_chat_8829",
  "user_id": "user_1415",
  "approved_at": "2026-09-27T00:55:00.123456+00:00",
  "expires_at": "2026-09-28T00:55:00.123456+00:00",
  "remaining_hours": 23.95,
  "message": "Consent is active. Generation permitted."
}
```

##### Response — When Blocked (Pending or Expired):
```json
{
  "consented": false,
  "status": "WAITING_FOR_CONSENT",
  "chat_id": "tg_chat_8829",
  "user_id": "user_1415",
  "consent_url": "http://localhost:8000/portal?user_id=user_1415&chat_id=tg_chat_8829",
  "message": "Consent request pending. Waiting for user to complete Face ID."
}
```

---

#### 2. Ask Consent (Push Request)
Creates a pending consent record in the database for a `user_id` and `chat_id`, returning a unique Face ID verification link.

* **Method:** `POST`
* **Path:** `/api/v1/consent/request`
* **Content-Type:** `application/json`

##### Request Body:
```json
{
  "user_id": "user_1415",
  "chat_id": "tg_chat_8829",
  "ttl_hours": 24.0
}
```

##### Example Request:
```bash
curl -X POST "http://localhost:8000/api/v1/consent/request" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_1415",
    "chat_id": "tg_chat_8829",
    "ttl_hours": 24.0
  }'
```

##### Response:
```json
{
  "request_id": "req_821cc2737246",
  "user_id": "user_1415",
  "chat_id": "tg_chat_8829",
  "status": "PENDING",
  "created_at": "2026-09-27T00:53:00.000000+00:00",
  "expires_at": "2026-09-28T00:53:00.000000+00:00",
  "consent_url": "http://localhost:8000/portal?user_id=user_1415&chat_id=tg_chat_8829&request_id=req_821cc2737246",
  "message": "Consent request created. Provide consent_url to the user to complete verification."
}
```

---

#### 3. Approve Consent
Marks a `chat_id` as approved for N hours. This is called automatically when a user completes verification, or can be triggered by your backend.

* **Method:** `POST`
* **Path:** `/api/v1/consent/approve`
* **Content-Type:** `application/json`

##### Request Body:
```json
{
  "chat_id": "tg_chat_8829",
  "user_id": "user_1415",
  "ttl_hours": 24.0
}
```

##### Response:
```json
{
  "request_id": "req_821cc2737246",
  "chat_id": "tg_chat_8829",
  "user_id": "user_1415",
  "status": "APPROVED",
  "approved_at": "2026-09-27T00:55:00.000000+00:00",
  "expires_at": "2026-09-28T00:55:00.000000+00:00",
  "message": "Consent approved successfully for chat 'tg_chat_8829'. Valid for 24.0h."
}
```

---

#### 4. List All Consent Records
Returns recent consent records stored in SQLite for auditing and monitoring.

* **Method:** `GET`
* **Path:** `/api/v1/consent/list`

##### Response:
```json
{
  "consents": [
    {
      "request_id": "req_821cc2737246",
      "user_id": "user_1415",
      "chat_id": "tg_chat_8829",
      "status": "APPROVED",
      "created_at": "2026-09-27T00:53:00+00:00",
      "approved_at": "2026-09-27T00:55:00+00:00",
      "expires_at": "2026-09-28T00:55:00+00:00"
    }
  ]
}
```

---

### Group B: User Biometric Search (1:N Face Identification)

#### 5. 1:N Match Faces
Identifies which enrolled person matches a query photo.

* **Method:** `POST`
* **Path:** `/api/v1/users/match-faces`
* **Content-Type:** `multipart/form-data`
* **Parameters:**
  * `image` (file, required): The query photo to search.
  * `threshold` (float, optional, default: 0.45): Cosine similarity threshold for a match.
  * `top_k` (int, optional, default: 5): Maximum candidate matches to return.

##### Example Request:
```bash
curl -X POST "http://localhost:8000/api/v1/users/match-faces?threshold=0.45&top_k=5" \
  -F "image=@query_face.jpg"
```

##### Response:
```json
{
  "found": true,
  "total_enrolled_scanned": 12,
  "top_match": {
    "user_id": "user_1415",
    "similarity": 0.884,
    "is_match": true,
    "confidence_pct": "88.4%"
  },
  "matches": [
    {
      "user_id": "user_1415",
      "similarity": 0.884,
      "is_match": true,
      "confidence_pct": "88.4%"
    },
    {
      "user_id": "user_5621",
      "similarity": 0.281,
      "is_match": false,
      "confidence_pct": "28.1%"
    }
  ],
  "message": "Identified user_1415 (88.4%)"
}
```

---

#### 6. List Enrolled Users
Returns all enrolled user IDs in the biometric database.

* **Method:** `GET`
* **Path:** `/api/v1/users`

##### Response:
```json
{
  "total_enrolled": 2,
  "users": ["user_1415", "user_5657"]
}
```

---

### Group C: Face ID Enrollment & 1:1 Verification

#### 7. Batch Enrollment
Uploads 3 profile angle images (Center 0°, Right +20°, Left -20°). Extracts 512-D vectors and stores them.

* **Method:** `POST`
* **Path:** `/api/v1/enroll/batch`
* **Content-Type:** `multipart/form-data`
* **Form Data:**
  * `user_id` (string, required): Unique identifier for the user.
  * `images` (files, required): 3 image files (`pose_straight.jpg`, `pose_right.jpg`, `pose_left.jpg`).

##### Example Request:
```bash
curl -X POST "http://localhost:8000/api/v1/enroll/batch" \
  -F "user_id=user_1415" \
  -F "images=@pose_straight.jpg" \
  -F "images=@pose_right.jpg" \
  -F "images=@pose_left.jpg"
```

##### Response:
```json
{
  "status": "DONE",
  "det_score": 0.836,
  "s3_path": "in-memory://users/user_1415/active/embeddings",
  "session_summary": {
    "total_angles_saved": 3,
    "avg_det_score": 0.836,
    "total_vectors": 3
  },
  "message": "Face ID Batch Enrollment Complete! Biometric vectors secured."
}
```

---

#### 8. 1:1 Face Verification
Direct 1:1 comparison of a live query photo against a specific `user_id`'s enrolled vectors.

* **Method:** `POST`
* **Path:** `/api/v1/enroll/verify`
* **Content-Type:** `multipart/form-data`
* **Form Data:**
  * `user_id` (string, required): Enrolled user ID.
  * `image` (file, required): Live photo to verify.

##### Example Request:
```bash
curl -X POST "http://localhost:8000/api/v1/enroll/verify" \
  -F "user_id=user_1415" \
  -F "image=@live_selfie.jpg"
```

##### Response:
```json
{
  "verified": true,
  "similarity": 0.8524,
  "user_id": "user_1415",
  "message": "Face ID Verified (85.2%)"
}
```

---

## 3. Bot Integration Example (Python)

```python
import requests

CONSENTOR_URL = "http://localhost:8000"

def can_generate_for_chat(chat_id: str) -> bool:
    """Check if user in chat has active consent before generating AI content."""
    res = requests.get(f"{CONSENTOR_URL}/api/v1/consent/check", params={"chat_id": chat_id})
    data = res.json()
    
    if data.get("consented"):
        print(f"[✓] Consent active ({data.get('remaining_hours')}h remaining). Starting generation...")
        return True
    else:
        scan_link = data.get("consent_url")
        print(f"[!] Blocked: User has not consented yet. Send link: {scan_link}")
        return False
```
