from fastapi import APIRouter
from app.api.v1 import health, chat, owl, hr_corner, rag

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(owl.router)
api_v1_router.include_router(hr_corner.router)
api_v1_router.include_router(rag.router)
