from fastapi import APIRouter
from app.api.v1 import health, chat, owl, hr_corner, cineku, rag, recommendations, tools, knowledge, metrics

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(chat.router)
api_v1_router.include_router(owl.router)
api_v1_router.include_router(hr_corner.router)
api_v1_router.include_router(cineku.router)
api_v1_router.include_router(rag.router)
api_v1_router.include_router(recommendations.router)
api_v1_router.include_router(tools.router)
api_v1_router.include_router(knowledge.router)
api_v1_router.include_router(metrics.router)


