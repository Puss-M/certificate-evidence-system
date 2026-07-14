from fastapi import APIRouter

from app.api.routes import (
    admin_students,
    certificate_batches,
    certificates,
    health,
    students,
    verification,
)


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(students.router, tags=["students"])
api_router.include_router(certificates.router, tags=["certificates"])
api_router.include_router(verification.router, tags=["verification"])
api_router.include_router(admin_students.router, tags=["admin-students"])
api_router.include_router(certificate_batches.router, tags=["admin-certificate-batches"])