from fastapi import APIRouter, Query, Body, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional

from app.services.consent_service import ConsentService, get_consent_service

router = APIRouter()

class CreateConsentRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user whose consent is required")
    chat_id: str = Field(..., description="Unique chat / session ID requesting generation")
    ttl_hours: float = Field(24.0, ge=0.1, le=720.0, description="Consent validity duration in hours")

class ApproveConsentRequest(BaseModel):
    chat_id: str = Field(..., description="Chat ID to approve")
    user_id: Optional[str] = Field(None, description="User ID who completed verification")
    ttl_hours: float = Field(24.0, ge=0.1, le=720.0, description="Validity duration in hours")

@router.post("/request", summary="Ask Consent (Push / Create Consent Request)")
async def request_consent(
    req_body: CreateConsentRequest,
    request: Request,
    service: ConsentService = Depends(get_consent_service),
):
    """
    Creates a pending consent request for a user & chat_id.
    Returns a secure portal URL for the user to complete their Face ID scan.
    """
    base_url = str(request.base_url).rstrip("/")
    result = service.create_request(
        user_id=req_body.user_id,
        chat_id=req_body.chat_id,
        ttl_hours=req_body.ttl_hours,
        base_url=base_url,
    )
    return result

@router.get("/check", summary="Check Consent Status (Allow or Block Generation)")
async def check_consent(
    chat_id: str = Query(..., description="Chat ID to check active consent for"),
    request: Request = None,
    service: ConsentService = Depends(get_consent_service),
):
    """
    Checks if a chat_id has active, unexpired consent.
    - If approved and active: returns consented=True (status: APPROVED).
    - If pending: returns consented=False (status: WAITING_FOR_CONSENT) with scan URL.
    - If expired: returns consented=False (status: EXPIRED) with scan URL.
    """
    base_url = str(request.base_url).rstrip("/") if request else ""
    result = service.check_consent(chat_id=chat_id, base_url=base_url)
    return result

@router.post("/approve", summary="Approve Consent (Mark Chat as Approved)")
async def approve_consent(
    body: ApproveConsentRequest,
    service: ConsentService = Depends(get_consent_service),
):
    """
    Called upon successful Face ID verification in web portal to approve chat_id for N hours.
    """
    result = service.approve_consent(
        chat_id=body.chat_id,
        user_id=body.user_id,
        ttl_hours=body.ttl_hours,
    )
    return result

@router.get("/list", summary="List All Consent Records")
async def list_consents(
    service: ConsentService = Depends(get_consent_service),
):
    """Returns recent consent records and their statuses."""
    return {
        "consents": service.list_consents()
    }
