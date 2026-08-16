from fastapi import APIRouter

from app.api.v1 import admin, auth, dashboard, products, simulations

router = APIRouter()
router.include_router(auth.router)
router.include_router(products.router)
router.include_router(simulations.router)
router.include_router(dashboard.router)
router.include_router(admin.router)
