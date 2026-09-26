from fastapi import APIRouter
from app.api.v1.endpoints import enrollment, users, consent

api_router = APIRouter()
api_router.include_router(enrollment.router, prefix="/enroll", tags=["Face ID Enrollment"])
api_router.include_router(users.router, prefix="/users", tags=["User Biometric Search"])
api_router.include_router(consent.router, prefix="/consent", tags=["Consent Management"])
