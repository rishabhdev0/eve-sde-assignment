from fastapi import APIRouter
from app.api.v1 import auth, centres, tests, slots, bookings, payments, webhooks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(centres.router)
api_router.include_router(tests.router)
api_router.include_router(slots.router)
api_router.include_router(bookings.router)
api_router.include_router(payments.router)
api_router.include_router(webhooks.router)