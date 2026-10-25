from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.guest import router as guest_router
from app.api.v1.manager import router as manager_router
from app.api.v1.reception import router as reception_router
from app.api.v1.staff import router as staff_router
from app.api.v1.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(manager_router, prefix="/manager", tags=["housekeeping manager"])
api_router.include_router(staff_router, prefix="/staff", tags=["housekeeping staff"])
api_router.include_router(reception_router, prefix="/reception", tags=["reception"])
api_router.include_router(guest_router, prefix="/guest", tags=["guest"])
