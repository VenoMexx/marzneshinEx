from fastapi import APIRouter

from . import admin, node, service, inbounds, subscription, system, user, user_panel, security

api_router = APIRouter()

api_router.include_router(admin.router, prefix="/api")
api_router.include_router(node.router, prefix="/api")
api_router.include_router(service.router, prefix="/api")
api_router.include_router(inbounds.router, prefix="/api")
api_router.include_router(subscription.router)
api_router.include_router(system.router, prefix="/api")
api_router.include_router(user.router, prefix="/api")
api_router.include_router(user_panel.router)  # No prefix, routes define their own paths
api_router.include_router(security.router, prefix="/api")  # Centralized security management

__all__ = ["api_router"]
